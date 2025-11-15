"""
Queue adapter implementations shared by QueueDispatcher.
"""

from __future__ import annotations

import json
import queue
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from .types import JSONDict


@dataclass
class QueueTask:
    job_id: str
    task_id: str
    case_indices: List[int]
    role: str
    payload: bytes
    call_spec: Optional[JSONDict] = None
    compressed: bool = True
    use_msgpack: bool = False


@dataclass
class QueueResult:
    job_id: str
    task_id: str
    case_index: int
    role: str
    result: JSONDict


class QueueAdapter:
    """Abstract queue interface."""

    def publish_task(self, task: QueueTask) -> None:
        raise NotImplementedError

    def consume_task(self, worker_id: str, timeout: float | None = None) -> Optional[QueueTask]:
        raise NotImplementedError

    def publish_result(self, result: QueueResult) -> None:
        raise NotImplementedError

    def consume_result(self, job_id: str, timeout: float | None = None) -> Optional[QueueResult]:
        raise NotImplementedError

    def signal_shutdown(self) -> None:
        """Request consumers to stop."""

    def register_worker(self, worker_id: str) -> None:
        """Register or refresh worker heartbeat."""

    def worker_assign(self, worker_id: str, task_id: str) -> None:
        """Record that a worker claimed a task."""

    def worker_heartbeats(self) -> Dict[str, float]:
        """Return last heartbeat timestamps for workers."""
        return {}

    def get_assignment(self, task_id: str) -> Optional[str]:
        """Return worker assigned to a task if known."""
        return None

    def pop_assignment(self, task_id: str) -> Optional[str]:
        """Remove and return assigned worker for a completed task."""
        return None

    def pending_count(self) -> int:
        """Return total number of pending queue tasks."""
        return 0


class InMemoryQueueAdapter(QueueAdapter):
    """Queue adapter backed by in-process queues."""

    def __init__(self, heartbeat_config: Optional[Dict[str, Any]] = None) -> None:
        self._task_queue: "queue.Queue[QueueTask]" = queue.Queue()
        self._result_queues: Dict[str, "queue.Queue[QueueResult]"] = {}
        self._result_lock = threading.Lock()
        self._assignment_lock = threading.Lock()
        self._heartbeat_lock = threading.Lock()
        self._shutdown = False
        self._heartbeats: Dict[str, float] = {}
        self._assignments: Dict[str, str] = {}

        self._heartbeat_manager = None
        if heartbeat_config:
            from .heartbeat_manager import HeartbeatConfig, HeartbeatManager

            config = HeartbeatConfig(
                timeout_seconds=heartbeat_config.get("timeout_seconds", 45.0),
                circuit_breaker_threshold=heartbeat_config.get("circuit_breaker_threshold", 3),
                check_interval=heartbeat_config.get("check_interval", 5.0),
            )
            self._heartbeat_manager = HeartbeatManager(config)

    def publish_task(self, task: QueueTask) -> None:
        if self._shutdown:
            return
        self._task_queue.put(task)

    def consume_task(self, worker_id: str, timeout: float | None = None) -> Optional[QueueTask]:
        if self._shutdown:
            return None
        try:
            data = self._task_queue.get(timeout=timeout)
        except queue.Empty:
            return None

        if not isinstance(data, QueueTask):
            return None

        if data.job_id != "__shutdown__":
            with self._assignment_lock:
                self._assignments[data.task_id] = worker_id
        return data

    def ensure_result_queue(self, job_id: str) -> None:
        with self._result_lock:
            self._result_queues.setdefault(job_id, queue.Queue())

    def publish_result(self, result: QueueResult) -> None:
        with self._result_lock:
            result_queue = self._result_queues.get(result.job_id)
            if result_queue is None:
                result_queue = queue.Queue()
                self._result_queues[result.job_id] = result_queue
        result_queue.put(result)

    def consume_result(self, job_id: str, timeout: float | None = None) -> Optional[QueueResult]:
        with self._result_lock:
            result_queue = self._result_queues.get(job_id)
        if result_queue is None:
            return None
        try:
            return result_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def signal_shutdown(self) -> None:
        self._shutdown = True
        self._task_queue.put_nowait(
            QueueTask(
                job_id="__shutdown__",
                task_id="__shutdown__",
                case_indices=[],
                role="",
                payload=b"",
                call_spec=None,
                compressed=False,
            )
        )

    def reset(self) -> None:
        self._shutdown = False
        with self._result_lock:
            self._result_queues = {}
        with self._assignment_lock:
            self._assignments.clear()
        with self._heartbeat_lock:
            self._heartbeats.clear()

    def register_worker(self, worker_id: str) -> None:
        with self._heartbeat_lock:
            self._heartbeats[worker_id] = time.monotonic()

        if self._heartbeat_manager:
            self._heartbeat_manager.register_worker(worker_id)

    def worker_assign(self, worker_id: str, task_id: str) -> None:
        with self._assignment_lock:
            self._assignments[task_id] = worker_id

        if self._heartbeat_manager:
            self._heartbeat_manager.record_task_assignment(worker_id, task_id)

    def worker_heartbeats(self) -> Dict[str, float]:
        with self._heartbeat_lock:
            return dict(self._heartbeats)

    def get_assignment(self, task_id: str) -> Optional[str]:
        with self._assignment_lock:
            return self._assignments.get(task_id)

    def pop_assignment(self, task_id: str) -> Optional[str]:
        with self._assignment_lock:
            return self._assignments.pop(task_id, None)

    def pending_count(self) -> int:
        return self._task_queue.qsize()

    def worker_count(self) -> int:
        with self._heartbeat_lock:
            return len(self._heartbeats)

    def check_stale_workers(self) -> set[str]:
        if self._heartbeat_manager:
            return self._heartbeat_manager.check_stale_workers()
        return set()

    def is_worker_lost(self, worker_id: str) -> bool:
        if self._heartbeat_manager:
            return self._heartbeat_manager.is_worker_lost(worker_id)
        return False

    def get_lost_workers(self) -> set[str]:
        if self._heartbeat_manager:
            return self._heartbeat_manager.get_lost_workers()
        return set()


class RedisQueueAdapter(QueueAdapter):
    """Redis-backed adapter using simple list semantics."""

    def __init__(self, config: Dict[str, Any]) -> None:
        try:
            import redis
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "Redis queue backend requires the 'redis' package."
            ) from exc

        url = config.get("url", "redis://localhost:6379/0")
        self.redis = redis.Redis.from_url(url)
        self.task_key = config.get("task_key", "metaguard:tasks")
        self.result_prefix = config.get("result_prefix", "metaguard:results:")
        self.shutdown_key = f"{self.task_key}:shutdown"
        self.worker_key = config.get("worker_key", "metaguard:workers")
        self.assignment_key = config.get("assignment_key", "metaguard:assignments")

    def publish_task(self, task: QueueTask) -> None:
        payload = {
            "job_id": task.job_id,
            "task_id": task.task_id,
            "case_indices": task.case_indices,
            "role": task.role,
            "payload": task.payload.decode("ascii"),
            "call_spec": task.call_spec,
            "compressed": task.compressed,
            "use_msgpack": task.use_msgpack,
        }
        self.redis.rpush(self.task_key, json.dumps(payload))

    def consume_task(self, worker_id: str, timeout: float | None = None) -> Optional[QueueTask]:
        timeout_sec = 0 if timeout is None else max(int(timeout), 1)
        data = self.redis.blpop(self.task_key, timeout=timeout_sec)
        if not data:
            return None
        _, raw = data
        payload = json.loads(raw)
        case_indices = payload.get("case_indices")
        if case_indices is None and "case_index" in payload:
            case_indices = [int(payload["case_index"])]
        task_id = payload.get("task_id") or str(uuid.uuid4())
        task = QueueTask(
            job_id=payload["job_id"],
            task_id=task_id,
            case_indices=[int(idx) for idx in case_indices or []],
            role=payload.get("role", ""),
            payload=payload.get("payload", "").encode("ascii"),
            call_spec=payload.get("call_spec"),
            compressed=payload.get("compressed", True),
            use_msgpack=payload.get("use_msgpack", False),
        )
        if task.job_id != "__shutdown__":
            self.worker_assign(worker_id, task.task_id)
        return task

    def publish_result(self, result: QueueResult) -> None:
        key = self._result_key(result.job_id)
        payload = json.dumps(
            {
                "job_id": result.job_id,
                "task_id": result.task_id,
                "case_index": result.case_index,
                "role": result.role,
                "result": result.result,
            }
        )
        self.redis.rpush(key, payload)

    def consume_result(self, job_id: str, timeout: float | None = None) -> Optional[QueueResult]:
        key = self._result_key(job_id)
        timeout_sec = 0 if timeout is None else max(int(timeout), 1)
        data = self.redis.blpop(key, timeout=timeout_sec)
        if not data:
            return None
        _, raw = data
        payload = json.loads(raw)
        return QueueResult(
            job_id=payload["job_id"],
            task_id=payload.get("task_id", ""),
            case_index=int(payload["case_index"]),
            role=payload.get("role", ""),
            result=payload.get("result", {}),
        )

    def signal_shutdown(self) -> None:
        self.redis.set(self.shutdown_key, "1", ex=60)
        sentinel = json.dumps(
            {
                "job_id": "__shutdown__",
                "task_id": "__shutdown__",
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

    def register_worker(self, worker_id: str) -> None:
        self.redis.hset(self.worker_key, worker_id, time.monotonic())

    def worker_assign(self, worker_id: str, task_id: str) -> None:
        self.redis.hset(self.assignment_key, task_id, worker_id)

    def worker_heartbeats(self) -> Dict[str, float]:
        data = self.redis.hgetall(self.worker_key)
        return {key.decode("utf-8"): float(val) for key, val in data.items()}

    def get_assignment(self, task_id: str) -> Optional[str]:
        val = self.redis.hget(self.assignment_key, task_id)
        return val.decode("utf-8") if val else None

    def pop_assignment(self, task_id: str) -> Optional[str]:
        with self.redis.pipeline() as pipe:
            while True:
                try:
                    pipe.watch(self.assignment_key)
                    worker = pipe.hget(self.assignment_key, task_id)
                    pipe.multi()
                    pipe.hdel(self.assignment_key, task_id)
                    pipe.execute()
                    return worker.decode("utf-8") if worker else None
                except self.redis.WatchError:
                    continue

    def pending_count(self) -> int:
        return int(self.redis.llen(self.task_key))


__all__ = [
    "QueueTask",
    "QueueResult",
    "QueueAdapter",
    "InMemoryQueueAdapter",
    "RedisQueueAdapter",
]

