"""
Task distribution and batching logic for queue dispatcher.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from ..errors import QueueSerializationError
from ..queue_adapter import QueueAdapter, QueueTask
from ..queue_serialization import prepare_payload
from ..observability import increment_queue_dispatched, increment_queue_requeued
from ..types import JSONDict


class TaskDistributionManager:
    """Manages task distribution, batching, and adaptive behavior."""

    def __init__(
        self,
        adapter: QueueAdapter,
        config: Dict[str, Any],
        workers: int,
        test_inputs: List[Tuple[Any, ...]],
        job_id: str,
        role: str,
        call_spec: Optional[JSONDict],
    ) -> None:
        self.adapter = adapter
        self.config = config
        self.workers = workers
        self.test_inputs = test_inputs
        self.job_id = job_id
        self.role = role
        self.call_spec = call_spec

        # Configuration
        self.lease_seconds = float(config.get("lease_seconds", 30.0))
        self.configured_batch_size = max(1, int(config.get("batch_size", 1)))
        self.compress_payloads = bool(config.get("compress", True))
        self.use_msgpack = bool(config.get("use_msgpack", False))
        self.heartbeat_timeout = float(config.get("heartbeat_timeout", 45.0))
        self.adaptive_batching = bool(config.get("adaptive_batching", True))
        self.adaptive_compress = bool(config.get("adaptive_compress", True))
        self.compression_threshold = int(config.get("compression_threshold_bytes", 512))
        self.inflight_factor = max(1, int(config.get("inflight_factor", 2)))
        max_batch_size = max(
            1,
            int(
                config.get(
                    "max_batch_size",
                    max(self.configured_batch_size * 4, self.workers * self.configured_batch_size),
                )
            ),
        )
        self.max_batch_size = max_batch_size
        
        # Performance tracking for improved heuristics
        self.avg_case_ms: Optional[float] = None
        self.variance_ms: float = 0.0
        self.current_batch_size = max(1, int(config.get("initial_batch_size", self.configured_batch_size)))
        self.min_batch_size = max(1, int(config.get("min_batch_size", 1)))
        self.adjustment_window = max(1, int(config.get("adjustment_window", 10)))
        self.fast_threshold_ms = float(config.get("adaptive_fast_threshold_ms", 50.0))
        self.slow_threshold_ms = float(config.get("adaptive_slow_threshold_ms", 500.0))

        if not self.adaptive_batching:
            self.current_batch_size = self.configured_batch_size
            self.max_batch_size = self.configured_batch_size

        self.target_inflight_cases = max(
            self.current_batch_size * self.workers * self.inflight_factor,
            self.current_batch_size,
        )

        # State
        self.tasks: Dict[str, QueueTask] = {}
        self.deadlines: Dict[str, float] = {}
        self.remaining_cases: Dict[str, Set[int]] = {}
        self.outstanding_cases = 0
        self.next_index = 0
        self.cases_since_adjustment = 0
        
        # Enhanced fault tolerance: track requeue attempts
        self.requeue_count: Dict[str, int] = {}  # task_id -> requeue count
        self.max_requeue_attempts = int(config.get("max_requeue_attempts", 3))
        
        # Load balancing: track worker load
        self.worker_load: Dict[str, int] = {}  # worker_id -> number of assigned tasks

    def publish_chunk(self, start_idx: int, size: int) -> None:
        """Publish a chunk of test cases as a task."""
        chunk_end = min(len(self.test_inputs), start_idx + size)
        indices = list(range(start_idx, chunk_end))
        if not indices:
            return
        args_chunk = [self.test_inputs[i] for i in indices]
        try:
            payload, compressed_flag, _, _ = prepare_payload(
                args_chunk,
                compress_default=self.compress_payloads,
                adaptive=self.adaptive_compress,
                threshold_bytes=self.compression_threshold,
                use_msgpack=self.use_msgpack,
            )
        except QueueSerializationError as exc:
            details = dict(exc.details)
            details["case_indices"] = indices
            raise QueueSerializationError(
                exc.args[0],
                details=details,
                original=exc.original or exc,
            ) from exc

        task_id = str(uuid.uuid4())
        task = QueueTask(
            job_id=self.job_id,
            task_id=task_id,
            case_indices=indices,
            role=self.role,
            payload=payload,
            call_spec=self.call_spec,
            compressed=compressed_flag,
            use_msgpack=self.use_msgpack,
        )
        self.tasks[task_id] = task
        self.deadlines[task_id] = time.monotonic() + self.lease_seconds
        self.remaining_cases[task_id] = set(indices)
        self.outstanding_cases += len(indices)
        self.adapter.publish_task(task)
        increment_queue_dispatched(len(indices))

    def maybe_publish_batches(self) -> None:
        """Publish batches of tasks if capacity allows."""
        inflight_limit = len(self.test_inputs) if not self.adaptive_batching else self.target_inflight_cases
        while self.next_index < len(self.test_inputs) and self.outstanding_cases < inflight_limit:
            batch = min(self.current_batch_size, len(self.test_inputs) - self.next_index)
            self.publish_chunk(self.next_index, batch)
            self.next_index += batch

    def update_adaptive_batching(self, duration_ms: float, pending_tasks: int) -> None:
        """Update batch size based on observed performance with improved heuristics."""
        if not self.adaptive_batching or duration_ms <= 0:
            return

        self.cases_since_adjustment += 1
        
        # Use exponential moving average with adaptive alpha based on variance
        if self.avg_case_ms is None:
            self.avg_case_ms = duration_ms
            self.variance_ms = 0.0
        else:
            # Adaptive smoothing: use higher alpha when variance is low (stable performance)
            alpha = 0.3 if self.variance_ms < (self.avg_case_ms * 0.1) else 0.2
            old_avg = self.avg_case_ms
            self.avg_case_ms = (1 - alpha) * self.avg_case_ms + alpha * duration_ms
            # Update variance estimate
            self.variance_ms = 0.9 * self.variance_ms + 0.1 * ((duration_ms - old_avg) ** 2)

        if self.cases_since_adjustment >= self.adjustment_window:
            # Improved heuristics:
            # 1. Consider queue depth relative to workers
            queue_ratio = pending_tasks / max(self.workers, 1)
            
            # 2. Consider throughput (cases per second)
            throughput = 1000.0 / self.avg_case_ms if self.avg_case_ms > 0 else 0.0
            
            # 3. Increase batch size if:
            #    - Fast execution AND low queue depth AND stable performance
            if (
                self.avg_case_ms is not None
                and self.avg_case_ms < self.fast_threshold_ms
                and queue_ratio < 1.5  # Queue not backing up
                and self.variance_ms < (self.avg_case_ms * 0.2)  # Stable performance
            ):
                # Aggressive increase when conditions are good
                increment = max(1, int(self.current_batch_size * 0.2))
                self.current_batch_size = min(self.max_batch_size, self.current_batch_size + increment)
            
            # 4. Decrease batch size if:
            #    - Slow execution OR high queue depth OR unstable performance
            elif (
                self.avg_case_ms is not None
                and (
                    self.avg_case_ms > self.slow_threshold_ms
                    or queue_ratio > 3.0  # Queue backing up significantly
                    or self.variance_ms > (self.avg_case_ms * 0.5)  # Unstable performance
                )
            ):
                # More conservative decrease
                decrement = max(1, int(self.current_batch_size * 0.15))
                self.current_batch_size = max(self.min_batch_size, self.current_batch_size - decrement)
            
            # Update target inflight cases based on throughput
            # Aim for 2-3x worker capacity for good pipeline utilization
            ideal_inflight = max(
                self.current_batch_size * self.workers * self.inflight_factor,
                int(throughput * self.avg_case_ms / 1000.0 * self.workers * 1.5) if throughput > 0 else self.current_batch_size,
            )
            self.target_inflight_cases = max(self.current_batch_size, min(ideal_inflight, len(self.test_inputs)))
            
            self.cases_since_adjustment = 0

    def requeue_stale_task(
        self,
        task_id: str,
        now: float,
        enable_requeue: bool,
        heartbeats: Dict[str, float],
        assigned_worker: Optional[str],
        lost_workers: Set[str],
    ) -> bool:
        """
        Requeue a stale task if needed.

        Returns:
            True if task was requeued, False otherwise
        """
        if not enable_requeue:
            return False

        outstanding = self.remaining_cases.get(task_id, set())
        if not outstanding:
            return False

        task = self.tasks[task_id]
        deadline = self.deadlines.get(task_id, 0.0)
        worker_is_lost = assigned_worker in lost_workers if assigned_worker else False

        heartbeat_age: Optional[float] = None
        if assigned_worker and not worker_is_lost:
            heartbeat = heartbeats.get(assigned_worker)
            if heartbeat is not None:
                heartbeat_age = now - heartbeat

        should_requeue = (
            now > deadline
            or worker_is_lost
            or (heartbeat_age is not None and heartbeat_age > self.heartbeat_timeout)
        )

        if not should_requeue:
            return False

        # Enhanced fault tolerance: check requeue limit
        requeue_count = self.requeue_count.get(task_id, 0)
        if requeue_count >= self.max_requeue_attempts:
            # Task has been requeued too many times - mark as failed
            # Remove from tracking but don't requeue
            self.tasks.pop(task_id, None)
            self.deadlines.pop(task_id, None)
            self.remaining_cases.pop(task_id, None)
            self.requeue_count.pop(task_id, None)
            self.outstanding_cases -= len(outstanding)
            return False

        # Increment requeue count
        self.requeue_count[task_id] = requeue_count + 1

        # Clear worker assignment
        self.adapter.pop_assignment(task_id)
        if assigned_worker:
            # Update worker load tracking
            self.worker_load[assigned_worker] = max(0, self.worker_load.get(assigned_worker, 0) - 1)

        sorted_indices = sorted(outstanding)
        args_chunk = [self.test_inputs[i] for i in sorted_indices]
        payload, compressed_flag, _, _ = prepare_payload(
            args_chunk,
            compress_default=self.compress_payloads,
            adaptive=self.adaptive_compress,
            threshold_bytes=self.compression_threshold,
        )
        task.case_indices = sorted_indices
        task.payload = payload
        task.compressed = compressed_flag
        self.adapter.publish_task(task)
        self.deadlines[task_id] = now + self.lease_seconds
        increment_queue_requeued(len(sorted_indices))

        if self.adaptive_batching and self.current_batch_size > self.min_batch_size:
            self.current_batch_size = max(self.min_batch_size, self.current_batch_size - 1)
            self.target_inflight_cases = max(
                self.current_batch_size * self.workers * self.inflight_factor,
                self.current_batch_size,
            )

        return True

    def mark_case_complete(self, task_id: str, case_index: int) -> None:
        """Mark a case as complete and clean up if task is done."""
        outstanding = self.remaining_cases.get(task_id)
        if outstanding is not None:
            if case_index in outstanding:
                outstanding.discard(case_index)
                self.outstanding_cases = max(0, self.outstanding_cases - 1)
        if outstanding is not None and not outstanding:
            self.remaining_cases.pop(task_id, None)
            self.deadlines.pop(task_id, None)
            self.tasks.pop(task_id, None)



