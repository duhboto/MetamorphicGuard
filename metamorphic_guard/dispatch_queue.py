from __future__ import annotations

import json
import queue
import threading
import time
import uuid
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from .monitoring import Monitor, MonitorRecord
from .dispatch import Dispatcher, RunCase
from .observability import (
    increment_queue_completed,
    increment_queue_dispatched,
    increment_queue_requeued,
    observe_queue_inflight,
    observe_queue_pending_tasks,
    observe_worker_count,
)
from .queue_adapter import (
    InMemoryQueueAdapter,
    QueueAdapter,
    QueueResult,
    QueueTask,
    RedisQueueAdapter,
)
from .queue_serialization import decode_args, prepare_payload

# Backwards compatibility for tests importing private classes
_Task = QueueTask
_Result = QueueResult
_decode_args = decode_args
_prepare_payload = prepare_payload




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
        else:
            from .plugins import dispatcher_plugins

            definition = dispatcher_plugins().get(backend_lower)
            if not definition:
                raise ValueError(f"Unsupported queue backend '{backend}'.")
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
        call_spec: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        monitors = list(monitors or [])
        job_id = str(uuid.uuid4())

        reset_adapter = getattr(self.adapter, "reset", None)
        if callable(reset_adapter):
            reset_adapter()

        threads: List[_LocalWorker] = []
        if self._spawn_local_workers:
            for _ in range(self.workers):
                worker = _LocalWorker(self.adapter, run_case)
                worker.start()
                threads.append(worker)
            # Wait briefly for at least one worker to register
            worker_ready_deadline = time.monotonic() + 5.0
            while time.monotonic() < worker_ready_deadline:
                if getattr(self.adapter, "worker_count", lambda: 0)() > 0:
                    break
                time.sleep(0.01)

        try:
            lease_seconds = float(self.config.get("lease_seconds", 30.0))
            enable_requeue = bool(self.config.get("enable_requeue", not self._spawn_local_workers))
            configured_batch_size = max(1, int(self.config.get("batch_size", 1)))
            compress_payloads = bool(self.config.get("compress", True))
            use_msgpack = bool(self.config.get("use_msgpack", False))
            heartbeat_timeout = float(self.config.get("heartbeat_timeout", 45.0))
            adaptive_batching = bool(self.config.get("adaptive_batching", True))
            adaptive_compress = bool(self.config.get("adaptive_compress", True))
            compression_threshold = int(self.config.get("compression_threshold_bytes", 512))
            inflight_factor = max(1, int(self.config.get("inflight_factor", 2)))
            max_batch_size = max(1, int(self.config.get("max_batch_size", max(configured_batch_size * 4, self.workers * configured_batch_size))))
            current_batch_size = max(1, int(self.config.get("initial_batch_size", configured_batch_size)))
            min_batch_size = max(1, int(self.config.get("min_batch_size", 1)))
            adjustment_window = max(1, int(self.config.get("adjustment_window", 10)))
            fast_threshold_ms = float(self.config.get("adaptive_fast_threshold_ms", 50.0))
            slow_threshold_ms = float(self.config.get("adaptive_slow_threshold_ms", 500.0))
            metrics_interval = float(self.config.get("metrics_interval", 1.0))
            overall_timeout = float(self.config.get("global_timeout", 120.0))
            overall_deadline = time.monotonic() + overall_timeout

            if not adaptive_batching:
                current_batch_size = configured_batch_size
                max_batch_size = configured_batch_size
                inflight_factor = max(inflight_factor, 1)

            target_inflight_cases = max(
                current_batch_size * self.workers * inflight_factor,
                current_batch_size,
            )

            tasks: Dict[str, QueueTask] = {}
            deadlines: Dict[str, float] = {}
            completed_cases: Dict[int, bool] = {}
            remaining_cases: Dict[str, set[int]] = {}
            outstanding_cases = 0
            next_index = 0
            avg_case_ms: Optional[float] = None
            cases_since_adjustment = 0
            last_metrics_sample = time.monotonic()

            def _publish_chunk(start_idx: int, size: int) -> None:
                nonlocal outstanding_cases
                chunk_end = min(len(test_inputs), start_idx + size)
                indices = list(range(start_idx, chunk_end))
                if not indices:
                    return
                args_chunk = [test_inputs[i] for i in indices]
                payload, compressed_flag, _, _ = prepare_payload(
                    args_chunk,
                    compress_default=compress_payloads,
                    adaptive=adaptive_compress,
                    threshold_bytes=compression_threshold,
                    use_msgpack=use_msgpack,
                )
                task_id = str(uuid.uuid4())
                task = QueueTask(
                    job_id=job_id,
                    task_id=task_id,
                    case_indices=indices,
                    role=role,
                    payload=payload,
                    call_spec=call_spec,
                    compressed=compressed_flag,
                    use_msgpack=use_msgpack,
                )
                tasks[task_id] = task
                deadlines[task_id] = time.monotonic() + lease_seconds
                remaining_cases[task_id] = set(indices)
                outstanding_cases += len(indices)
                self.adapter.publish_task(task)
                increment_queue_dispatched(len(indices))

            def _maybe_publish_batches() -> None:
                nonlocal next_index, current_batch_size, target_inflight_cases
                inflight_limit = len(test_inputs) if not adaptive_batching else target_inflight_cases
                while next_index < len(test_inputs) and outstanding_cases < inflight_limit:
                    batch = min(current_batch_size, len(test_inputs) - next_index)
                    _publish_chunk(next_index, batch)
                    next_index += batch

            ensure_queue = getattr(self.adapter, "ensure_result_queue", None)
            if ensure_queue is not None:
                ensure_queue(job_id)

            _maybe_publish_batches()

            results: List[Dict[str, Any]] = [{} for _ in range(len(test_inputs))]
            received = 0
            poll_timeout = float(self.config.get("result_poll_timeout", 1.0))

            while received < len(test_inputs):
                now = time.monotonic()
                if now - last_metrics_sample >= metrics_interval:
                    observe_queue_pending_tasks(getattr(self.adapter, "pending_count", lambda: 0)())
                    observe_queue_inflight(outstanding_cases)
                    observe_worker_count(len(self.adapter.worker_heartbeats()))
                    last_metrics_sample = now

                if enable_requeue:
                    # Use enhanced heartbeat manager if available
                    lost_workers = set()
                    if hasattr(self.adapter, "check_stale_workers"):
                        lost_workers = self.adapter.check_stale_workers()
                    
                    heartbeats = self.adapter.worker_heartbeats()
                    for task_id, deadline in list(deadlines.items()):
                        task = tasks[task_id]
                        outstanding = remaining_cases.get(task_id, set())
                        if not outstanding:
                            continue
                        assigned = self.adapter.get_assignment(task_id)
                        heartbeat_age = None
                        worker_is_lost = False
                        
                        if assigned:
                            # Check if worker is marked as lost
                            if hasattr(self.adapter, "is_worker_lost"):
                                worker_is_lost = self.adapter.is_worker_lost(assigned)
                            
                            if not worker_is_lost:
                                heartbeat = heartbeats.get(assigned)
                                if heartbeat is not None:
                                    heartbeat_age = now - heartbeat
                            
                            # Mark as lost if in lost_workers set
                            if assigned in lost_workers:
                                worker_is_lost = True
                        
                        if now > deadline or worker_is_lost or (heartbeat_age is not None and heartbeat_age > heartbeat_timeout):
                            self.adapter.pop_assignment(task_id)
                            sorted_indices = sorted(outstanding)
                            args_chunk = [test_inputs[i] for i in sorted_indices]
                            payload, compressed_flag, _, _ = prepare_payload(
                                args_chunk,
                                compress_default=compress_payloads,
                                adaptive=adaptive_compress,
                                threshold_bytes=compression_threshold,
                            )
                            task.case_indices = sorted_indices
                            task.payload = payload
                            task.compressed = compressed_flag
                            self.adapter.publish_task(task)
                            deadlines[task_id] = now + lease_seconds
                            increment_queue_requeued(len(sorted_indices))
                            if adaptive_batching and current_batch_size > min_batch_size:
                                current_batch_size = max(min_batch_size, current_batch_size - 1)
                                target_inflight_cases = max(
                                    current_batch_size * self.workers * inflight_factor,
                                    current_batch_size,
                                )

                remaining_time = overall_deadline - now
                if remaining_time <= 0:
                    raise TimeoutError(f"Queue dispatcher exceeded global timeout ({overall_timeout}s)")

                timeout = min(poll_timeout, max(0.1, remaining_time))
                message = self.adapter.consume_result(job_id, timeout=timeout)
                if message is None:
                    _maybe_publish_batches()
                    continue

                idx = message.case_index
                self.adapter.pop_assignment(message.task_id)
                outstanding = remaining_cases.get(message.task_id)
                if outstanding is not None:
                    if idx in outstanding:
                        outstanding.discard(idx)
                        outstanding_cases = max(0, outstanding_cases - 1)
                if outstanding is not None and not outstanding:
                    remaining_cases.pop(message.task_id, None)
                    deadlines.pop(message.task_id, None)
                    tasks.pop(message.task_id, None)

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
                completed_cases[idx] = True
                increment_queue_completed()

                if adaptive_batching and duration > 0:
                    cases_since_adjustment += 1
                    if avg_case_ms is None:
                        avg_case_ms = duration
                    else:
                        avg_case_ms = 0.8 * avg_case_ms + 0.2 * duration

                    if cases_since_adjustment >= adjustment_window:
                        pending_tasks = getattr(self.adapter, "pending_count", lambda: 0)()
                        if avg_case_ms is not None and avg_case_ms < fast_threshold_ms and pending_tasks <= self.workers:
                            if current_batch_size < max_batch_size:
                                current_batch_size += 1
                        elif avg_case_ms is not None and (avg_case_ms > slow_threshold_ms or pending_tasks > self.workers * 4):
                            if current_batch_size > min_batch_size:
                                current_batch_size -= 1
                        target_inflight_cases = max(
                            current_batch_size * self.workers * inflight_factor,
                            current_batch_size,
                        )
                        cases_since_adjustment = 0

                _maybe_publish_batches()

            return results
        finally:
            if self._spawn_local_workers:
                self.adapter.signal_shutdown()
                for worker in threads:
                    worker.stop()
                for worker in threads:
                    worker.join(timeout=1.0)


class _LocalWorker(threading.Thread):
    """Worker that consumes tasks from the adapter and executes run_case."""

    def __init__(self, adapter: QueueAdapter, run_case: RunCase) -> None:
        super().__init__(daemon=True)
        self.adapter = adapter
        self.run_case = run_case
        self._stop_event = threading.Event()
        self.worker_id = f"local-{uuid.uuid4()}"

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        self.adapter.register_worker(self.worker_id)
        while not self._stop_event.is_set():
            self.adapter.register_worker(self.worker_id)
            task = self.adapter.consume_task(self.worker_id, timeout=0.5)
            if task is None:
                continue
            if task.job_id == "__shutdown__":
                break

            args_list = decode_args(
                task.payload,
                compress=task.compressed,
                use_msgpack=task.use_msgpack,
            )
            for idx, args in zip(task.case_indices, args_list):
                result = self.run_case(idx, args)
                self.adapter.publish_result(
                    QueueResult(
                        job_id=task.job_id,
                        task_id=task.task_id,
                        case_index=idx,
                        role=task.role,
                        result=result,
                    )
                )



