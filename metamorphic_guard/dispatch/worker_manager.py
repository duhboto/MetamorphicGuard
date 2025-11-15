"""
Local worker thread management for queue dispatcher.
"""

from __future__ import annotations

import threading
import uuid
from typing import Any, Callable, Dict

from ..errors import QueueSerializationError
from ..queue_adapter import QueueAdapter, QueueResult, QueueTask
from ..queue_serialization import decode_args
from ..dispatch import RunCase


class LocalWorker(threading.Thread):
    """Worker that consumes tasks from the adapter and executes run_case."""

    def __init__(self, adapter: QueueAdapter, run_case: RunCase) -> None:
        super().__init__(daemon=True)
        self.adapter = adapter
        self.run_case = run_case
        self._stop_event = threading.Event()
        self.worker_id = f"local-{uuid.uuid4()}"

    def stop(self) -> None:
        """Signal the worker to stop."""
        self._stop_event.set()

    def run(self) -> None:
        """Main worker loop: consume tasks and execute them."""
        self.adapter.register_worker(self.worker_id)
        while not self._stop_event.is_set():
            self.adapter.register_worker(self.worker_id)
            task = self.adapter.consume_task(self.worker_id, timeout=0.5)
            if task is None:
                continue
            if task.job_id == "__shutdown__":
                break

            try:
                args_list = decode_args(
                    task.payload,
                    compress=task.compressed,
                    use_msgpack=task.use_msgpack,
                )
            except QueueSerializationError as exc:
                self._emit_serialization_error(task, exc)
                continue

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

    def _emit_serialization_error(self, task: QueueTask, error: QueueSerializationError) -> None:
        """Emit serialization error as result for all cases in the task."""
        context = error.to_context().as_dict()
        for idx in task.case_indices:
            self.adapter.publish_result(
                QueueResult(
                    job_id=task.job_id,
                    task_id=task.task_id,
                    case_index=idx,
                    role=task.role,
                    result={"success": False, "error": context},
                )
            )



