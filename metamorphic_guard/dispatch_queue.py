from __future__ import annotations

import base64
import json
import pickle
import queue
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .monitoring import Monitor, MonitorRecord
from .dispatch import Dispatcher, RunCase


@dataclass
class _Task:
    job_id: str
    case_indices: List[int]
    role: str
    payload: bytes
    call_spec: Optional[Dict[str, Any]] = None
    compressed: bool = True


@dataclass
class _Result:
    job_id: str
    case_index: int
    role: str
    result: Dict[str, Any]


class QueueAdapter:
    """Abstract queue interface."""

    def publish_task(self, task: _Task) -> None:
        raise NotImplementedError

    def consume_task(self, timeout: float | None = None) -> Optional[_Task]:
        raise NotImplementedError

    def publish_result(self, result: _Result) -> None:
        raise NotImplementedError

    def consume_result(self, job_id: str, timeout: float | None = None) -> Optional[_Result]:
        raise NotImplementedError

    def signal_shutdown(self) -> None:
        """Request consumers to stop."""


class InMemoryQueueAdapter(QueueAdapter):
    """Queue adapter backed by in-process queues."""

    def __init__(self) -> None:
        self._task_queue: "queue.Queue[_Task]" = queue.Queue()
        self._result_queues: Dict[str, "queue.Queue[_Result]"] = {}
        self._lock = threading.Lock()
        self._shutdown = False

    def publish_task(self, task: _Task) -> None:
        self._task_queue.put(task)

    def consume_task(self, timeout: float | None = None) -> Optional[_Task]:
        if self._shutdown:
            return None
        try:
            data = self._task_queue.get(timeout=timeout)
            if isinstance(data, _Task):
                return data
            return None
        except queue.Empty:
            return None

    def publish_result(self, result: _Result) -> None:
        with self._lock:
            result_queue = self._result_queues.setdefault(result.job_id, queue.Queue())
        result_queue.put(result)

    def consume_result(self, job_id: str, timeout: float | None = None) -> Optional[_Result]:
        with self._lock:
            result_queue = self._result_queues.setdefault(job_id, queue.Queue())
        try:
            return result_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def signal_shutdown(self) -> None:
        self._shutdown = True
        self._task_queue.put_nowait(
            _Task(job_id="__shutdown__", case_indices=[], role="", payload=b"", call_spec=None, compressed=False)
        )


class RedisQueueAdapter(QueueAdapter):
    """Redis-backed adapter using simple list semantics."""

    def __init__(self, config: Dict[str, Any]) -> None:
        try:
            import redis  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "Redis queue backend requires the 'redis' package."
            ) from exc

        url = config.get("url", "redis://localhost:6379/0")
        self.redis = redis.Redis.from_url(url)
        self.task_key = config.get("task_key", "metaguard:tasks")
        self.result_prefix = config.get("result_prefix", "metaguard:results:")
        self.shutdown_key = f"{self.task_key}:shutdown"

    def publish_task(self, task: _Task) -> None:
        payload = {
            "job_id": task.job_id,
            "case_indices": task.case_indices,
            "role": task.role,
            "payload": task.payload.decode("ascii"),
            "call_spec": task.call_spec,
            "compressed": task.compressed,
        }
        self.redis.rpush(self.task_key, json.dumps(payload))

    def consume_task(self, timeout: float | None = None) -> Optional[_Task]:
        timeout_sec = 0 if timeout is None else max(int(timeout), 1)
        data = self.redis.blpop(self.task_key, timeout=timeout_sec)
        if not data:
            return None
        _, raw = data
        payload = json.loads(raw)
        case_indices = payload.get("case_indices")
        if case_indices is None and "case_index" in payload:
            case_indices = [int(payload["case_index"])]
        return _Task(
            job_id=payload["job_id"],
            case_indices=[int(idx) for idx in case_indices or []],
            role=payload.get("role", ""),
            payload=payload.get("payload", "").encode("ascii"),
            call_spec=payload.get("call_spec"),
            compressed=payload.get("compressed", True),
        )

    def publish_result(self, result: _Result) -> None:
        key = self._result_key(result.job_id)
        payload = json.dumps(
            {
                "job_id": result.job_id,
                "case_index": result.case_index,
                "role": result.role,
                "result": result.result,
            }
        )
        self.redis.rpush(key, payload)

    def consume_result(self, job_id: str, timeout: float | None = None) -> Optional[_Result]:
        key = self._result_key(job_id)
        timeout_sec = 0 if timeout is None else max(int(timeout), 1)
        data = self.redis.blpop(key, timeout=timeout_sec)
        if not data:
            return None
        _, raw = data
        payload = json.loads(raw)
        return _Result(
            job_id=payload["job_id"],
            case_index=int(payload["case_index"]),
            role=payload.get("role", ""),
            result=payload.get("result", {}),
        )

    def signal_shutdown(self) -> None:
        self.redis.set(self.shutdown_key, "1", ex=60)
        sentinel = json.dumps(
            {
                "job_id": "__shutdown__",
                "case_indices": [],
                "role": "",
                "payload": "",
                "call_spec": None,
                "compressed": False,
            }
        )
        self.redis.rpush(self.task_key, sentinel)

    def _result_key(self, job_id: str) -> str:
        return f"{self.result_prefix}{job_id}"


class QueueDispatcher(Dispatcher):
    """Queue-backed dispatcher with optional local worker threads."""

    def __init__(self, workers: int, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(workers, kind="queue")
        self.config = config or {}
        backend = self.config.get("backend", "memory")
        if backend == "memory":
            self.adapter: QueueAdapter = InMemoryQueueAdapter()
        else:
            raise ValueError(f"Unsupported queue backend '{backend}'.")

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

        threads: List[_LocalWorker] = []
        if self._spawn_local_workers:
            for _ in range(self.workers):
                worker = _LocalWorker(self.adapter, run_case)
                worker.start()
                threads.append(worker)

        try:
            lease_seconds = float(self.config.get("lease_seconds", 30.0))
            enable_requeue = bool(self.config.get("enable_requeue", not self._spawn_local_workers))
            batch_size = max(1, int(self.config.get("batch_size", 1)))
            compress_payloads = bool(self.config.get("compress", True))

            tasks: List[_Task] = []
            deadlines: Dict[int, float] = {}
            completed_cases: Dict[int, bool] = {}

            for start in range(0, len(test_inputs), batch_size):
                end = min(len(test_inputs), start + batch_size)
                indices = list(range(start, end))
                args_chunk = [test_inputs[i] for i in indices]
                payload = _encode_payload(args_chunk, compress_payloads)
                task = _Task(
                    job_id=job_id,
                    case_indices=indices,
                    role=role,
                    payload=payload,
                    call_spec=call_spec,
                    compressed=self._compress,
                )
                task_id = len(tasks)
                tasks.append(task)
                deadlines[task_id] = time.monotonic() + lease_seconds
                self.adapter.publish_task(task)

            results: List[Dict[str, Any]] = [{} for _ in range(len(test_inputs))]
            received = 0
            timeout = self.config.get("result_poll_timeout", 1.0)

            while received < len(test_inputs):
                now = time.monotonic()
                if enable_requeue:
                    for task_id, deadline in list(deadlines.items()):
                        task = tasks[task_id]
                        if all(completed_cases.get(idx) for idx in task.case_indices):
                            continue
                        if now > deadline:
                            self.adapter.publish_task(task)
                            deadlines[task_id] = now + lease_seconds

                message = self.adapter.consume_result(job_id, timeout=timeout)
                if message is None:
                    continue

                idx = message.case_index
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

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        while not self._stop_event.is_set():
            task = self.adapter.consume_task(timeout=0.5)
            if task is None:
                continue
            if task.job_id == "__shutdown__":
                break

            args_list = _decode_payload(task.payload, compress=task.compressed)
            for idx, args in zip(task.case_indices, args_list):
                result = self.run_case(idx, args)
                self.adapter.publish_result(
                    _Result(
                        job_id=task.job_id,
                        case_index=idx,
                        role=task.role,
                        result=result,
                    )
                )


def _encode_payload(args_list: List[Tuple[Any, ...]], compress: bool) -> bytes:
    raw = pickle.dumps(args_list)
    if compress:
        import gzip

        raw = gzip.compress(raw)
    return base64.b64encode(raw)


def _decode_payload(payload: bytes, compress: Optional[bool] = None) -> List[Tuple[Any, ...]]:
    raw = base64.b64decode(payload)
    if compress is None:
        try:
            import gzip

            raw = gzip.decompress(raw)
        except OSError:
            pass
    elif compress:
        import gzip

        raw = gzip.decompress(raw)
    return pickle.loads(raw)

