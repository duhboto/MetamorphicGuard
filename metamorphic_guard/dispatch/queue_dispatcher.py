"""
Queue-based dispatcher implementation.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Import Dispatcher and RunCase from parent dispatch.py module (file, not package)
# Need to import from the file, not the package - use importlib to break circular dependency
import importlib.util
from pathlib import Path

# Load dispatch.py file directly to avoid package/namespace conflict
_dispatch_file_path = Path(__file__).parent.parent / 'dispatch.py'
_spec = importlib.util.spec_from_file_location('metamorphic_guard._dispatch_file', _dispatch_file_path)
if _spec and _spec.loader:
    _dispatch_file = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_dispatch_file)
    Dispatcher = _dispatch_file.Dispatcher  # type: ignore[attr-defined]
    RunCase = _dispatch_file.RunCase  # type: ignore[attr-defined]
else:
    # Fallback: This shouldn't happen, but if it does, raise an error
    raise ImportError("Could not load dispatch.py file")
from ..errors import QueueSerializationError
from ..monitoring import Monitor, MonitorRecord
from ..observability import (
    increment_queue_completed,
    observe_queue_inflight,
    observe_queue_pending_tasks,
    observe_worker_count,
)
from ..queue_adapter import (
    InMemoryQueueAdapter,
    QueueAdapter,
    QueueResult,
    RedisQueueAdapter,
)
from ..types import JSONDict

from .task_distribution import TaskDistributionManager
from .worker_manager import LocalWorker

# Backwards compatibility for tests importing private classes
_Task = QueueResult  # Alias for backward compatibility
_Result = QueueResult  # Alias for backward compatibility


class QueueDispatcher(Dispatcher):
    """Queue-backed dispatcher with optional local worker threads."""

    def __init__(self, workers: int, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(workers, kind="queue")
        self.config = config or {}
        backend = self.config.get("backend", "memory")
        backend_lower = backend.lower()

        # Extract heartbeat config if provided
        heartbeat_config = None
        if "heartbeat_timeout" in self.config or "circuit_breaker_threshold" in self.config:
            heartbeat_config = {
                "timeout_seconds": self.config.get("heartbeat_timeout", 45.0),
                "circuit_breaker_threshold": self.config.get("circuit_breaker_threshold", 3),
                "check_interval": self.config.get("heartbeat_check_interval", 5.0),
            }

        if backend_lower == "memory":
            self.adapter = InMemoryQueueAdapter(heartbeat_config=heartbeat_config)
        elif backend_lower == "redis":
            self.adapter = RedisQueueAdapter(self.config)
        elif backend_lower == "sqs":
            from ..queue_adapters.sqs import SQSQueueAdapter
            self.adapter = SQSQueueAdapter(self.config)
        elif backend_lower == "rabbitmq":
            from ..queue_adapters.rabbitmq import RabbitMQQueueAdapter
            self.adapter = RabbitMQQueueAdapter(self.config)
        elif backend_lower == "kafka":
            from ..queue_adapters.kafka import KafkaQueueAdapter
            self.adapter = KafkaQueueAdapter(self.config)
        else:
            from ..plugins import dispatcher_plugins

            definition = dispatcher_plugins().get(backend_lower)
            if not definition:
                raise ValueError(f"Unsupported queue backend '{backend}'. Available: memory, redis, sqs, rabbitmq, kafka")
            factory = definition.factory
            self.adapter = factory(self.config)

        spawn_local_workers = self.config.get("spawn_local_workers")
        if spawn_local_workers is None:
            spawn_local_workers = backend == "memory"
        self._spawn_local_workers = bool(spawn_local_workers)
        self._compress = bool(self.config.get("compress", True))

    def execute(
        self,
        *,
        test_inputs: Sequence[Tuple[Any, ...]],
        run_case: RunCase,
        role: str,
        monitors: Sequence[Monitor] | None = None,
        call_spec: Optional[JSONDict] = None,
    ) -> List[JSONDict]:
        """Execute test cases using queue-based distribution."""
        monitors = list(monitors or [])
        job_id = str(uuid.uuid4())

        reset_adapter = getattr(self.adapter, "reset", None)
        if callable(reset_adapter):
            reset_adapter()

        threads: List[LocalWorker] = []
        if self._spawn_local_workers:
            for _ in range(self.workers):
                worker = LocalWorker(self.adapter, run_case)
                worker.start()
                threads.append(worker)
            # Wait briefly for at least one worker to register
            worker_ready_deadline = time.monotonic() + 5.0
            while time.monotonic() < worker_ready_deadline:
                if getattr(self.adapter, "worker_count", lambda: 0)() > 0:
                    break
                time.sleep(0.01)

        try:
            enable_requeue = bool(self.config.get("enable_requeue", not self._spawn_local_workers))
            metrics_interval = float(self.config.get("metrics_interval", 1.0))
            overall_timeout = float(self.config.get("global_timeout", 120.0))
            overall_deadline = time.monotonic() + overall_timeout
            poll_timeout = float(self.config.get("result_poll_timeout", 1.0))

            # Create task distribution manager
            task_manager = TaskDistributionManager(
                adapter=self.adapter,
                config=self.config,
                workers=self.workers,
                test_inputs=list(test_inputs),
                job_id=job_id,
                role=role,
                call_spec=call_spec,
            )

            ensure_queue = getattr(self.adapter, "ensure_result_queue", None)
            if ensure_queue is not None:
                ensure_queue(job_id)

            task_manager.maybe_publish_batches()

            results: List[JSONDict] = [{} for _ in range(len(test_inputs))]
            received = 0
            last_metrics_sample = time.monotonic()

            while received < len(test_inputs):
                now = time.monotonic()
                if now - last_metrics_sample >= metrics_interval:
                    observe_queue_pending_tasks(getattr(self.adapter, "pending_count", lambda: 0)())
                    observe_queue_inflight(task_manager.outstanding_cases)
                    observe_worker_count(len(self.adapter.worker_heartbeats()))
                    last_metrics_sample = now

                # Check for stale tasks and requeue
                if enable_requeue:
                    lost_workers = set()
                    if hasattr(self.adapter, "check_stale_workers"):
                        lost_workers = self.adapter.check_stale_workers()

                    heartbeats = self.adapter.worker_heartbeats()
                    
                    # Enhanced fault tolerance: check for stale workers
                    if hasattr(self.adapter, "check_stale_workers"):
                        detected_stale = self.adapter.check_stale_workers()
                        lost_workers.update(detected_stale)
                    
                    for task_id in list(task_manager.deadlines.keys()):
                        assigned = self.adapter.get_assignment(task_id)
                        was_requeued = task_manager.requeue_stale_task(
                            task_id=task_id,
                            now=now,
                            enable_requeue=enable_requeue,
                            heartbeats=heartbeats,
                            assigned_worker=assigned,
                            lost_workers=lost_workers,
                        )
                        
                        # Track worker load when task is assigned
                        if assigned and not was_requeued and hasattr(task_manager, 'worker_load'):
                            task_manager.worker_load[assigned] = task_manager.worker_load.get(assigned, 0) + 1

                remaining_time = overall_deadline - now
                if remaining_time <= 0:
                    raise TimeoutError(f"Queue dispatcher exceeded global timeout ({overall_timeout}s)")

                timeout = min(poll_timeout, max(0.1, remaining_time))
                message = self.adapter.consume_result(job_id, timeout=timeout)
                if message is None:
                    task_manager.maybe_publish_batches()
                    continue

                idx = message.case_index
                assigned_worker = self.adapter.pop_assignment(message.task_id)
                
                # Update worker load for load balancing
                if assigned_worker and hasattr(task_manager, 'worker_load'):
                    task_manager.worker_load[assigned_worker] = max(
                        0, task_manager.worker_load.get(assigned_worker, 0) - 1
                    )
                task_manager.mark_case_complete(message.task_id, idx)

                results[idx] = message.result
                duration = float(message.result.get("duration_ms") or 0.0)
                success = bool(message.result.get("success"))
                record = MonitorRecord(
                    case_index=idx,
                    role=role,
                    duration_ms=duration,
                    success=success,
                    result=message.result,
                )
                for monitor in monitors:
                    monitor.record(record)
                received += 1
                increment_queue_completed()

                # Update adaptive batching based on performance
                pending_tasks = getattr(self.adapter, "pending_count", lambda: 0)()
                task_manager.update_adaptive_batching(duration, pending_tasks)

                task_manager.maybe_publish_batches()

            return results
        finally:
            if self._spawn_local_workers:
                self.adapter.signal_shutdown()
                for worker in threads:
                    worker.stop()
                for worker in threads:
                    worker.join(timeout=1.0)


# Backward compatibility exports
_Task = QueueResult
_Result = QueueResult

