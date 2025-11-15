"""
RabbitMQ queue adapter for distributed task execution.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

from ..queue_adapter import QueueAdapter, QueueResult, QueueTask
from ..types import JSONDict


class RabbitMQQueueAdapter(QueueAdapter):
    """
    RabbitMQ-backed queue adapter.
    
    Requires pika to be installed: pip install pika
    
    Configuration:
        {
            "host": "localhost",
            "port": 5672,
            "virtual_host": "/",
            "username": "guest",
            "password": "guest",
            "exchange": "metamorphic_guard",  # Optional exchange name
            "task_queue": "mg_tasks",
            "result_queue_prefix": "mg_results",
            "durable": True,  # Make queues durable
            "prefetch_count": 1,  # Messages per worker
        }
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        try:
            import pika
            self.pika = pika
        except ImportError as e:
            raise ImportError(
                "pika is required for RabbitMQ adapter. Install with: pip install pika"
            ) from e

        self.config = config
        self.host = config.get("host", "localhost")
        self.port = int(config.get("port", 5672))
        self.virtual_host = config.get("virtual_host", "/")
        self.username = config.get("username", "guest")
        self.password = config.get("password", "guest")
        self.exchange = config.get("exchange", "metamorphic_guard")
        self.task_queue = config.get("task_queue", "mg_tasks")
        self.result_queue_prefix = config.get("result_queue_prefix", "mg_results")
        self.durable = bool(config.get("durable", True))
        self.prefetch_count = int(config.get("prefetch_count", 1))

        # Connection and channels
        credentials = self.pika.PlainCredentials(self.username, self.password)
        parameters = self.pika.ConnectionParameters(
            host=self.host,
            port=self.port,
            virtual_host=self.virtual_host,
            credentials=credentials,
        )
        self.connection = pika.BlockingConnection(parameters)
        self.task_channel = self.connection.channel()
        self.result_channel = self.connection.channel()

        # Declare exchange (topic exchange for routing)
        self.task_channel.exchange_declare(
            exchange=self.exchange, exchange_type="topic", durable=self.durable
        )

        # Declare task queue
        self.task_channel.queue_declare(queue=self.task_queue, durable=self.durable)
        self.task_channel.queue_bind(
            exchange=self.exchange, queue=self.task_queue, routing_key="task.*"
        )
        self.task_channel.basic_qos(prefetch_count=self.prefetch_count)

        # Worker tracking
        self._heartbeats: Dict[str, float] = {}
        self._assignments: Dict[str, str] = {}
        self._result_queues: Dict[str, str] = {}  # job_id -> queue_name

    def _get_result_queue(self, job_id: str) -> str:
        """Get or create result queue for a job."""
        if job_id not in self._result_queues:
            queue_name = f"{self.result_queue_prefix}_{job_id}"
            self.result_channel.queue_declare(queue=queue_name, durable=self.durable)
            self.result_channel.queue_bind(
                exchange=self.exchange, queue=queue_name, routing_key=f"result.{job_id}"
            )
            self._result_queues[job_id] = queue_name
        return self._result_queues[job_id]

    def publish_task(self, task: QueueTask) -> None:
        """Publish a task to RabbitMQ."""
        message_body = json.dumps(
            {
                "job_id": task.job_id,
                "task_id": task.task_id,
                "case_indices": task.case_indices,
                "role": task.role,
                "payload": task.payload.hex() if isinstance(task.payload, bytes) else task.payload,
                "compressed": task.compressed,
                "use_msgpack": task.use_msgpack,
                "call_spec": task.call_spec,
            }
        )

        properties = self.pika.BasicProperties(
            delivery_mode=2 if self.durable else 1,  # 2 = persistent
            message_id=task.task_id,
            headers={"job_id": task.job_id, "role": task.role},
        )

        self.task_channel.basic_publish(
            exchange=self.exchange,
            routing_key=f"task.{task.role}",
            body=message_body,
            properties=properties,
        )

    def consume_task(self, worker_id: str, timeout: float | None = None) -> Optional[QueueTask]:
        """Consume a task from RabbitMQ."""
        method_frame, header_frame, body = self.task_channel.basic_get(
            queue=self.task_queue, auto_ack=False
        )

        if method_frame is None:
            return None

        delivery_tag = method_frame.delivery_tag
        body_dict = json.loads(body)

        task = QueueTask(
            job_id=body_dict["job_id"],
            task_id=body_dict["task_id"],
            case_indices=body_dict["case_indices"],
            role=body_dict["role"],
            payload=bytes.fromhex(body_dict["payload"])
            if isinstance(body_dict["payload"], str)
            else body_dict["payload"],
            compressed=body_dict.get("compressed", True),
            use_msgpack=body_dict.get("use_msgpack", False),
            call_spec=body_dict.get("call_spec"),
        )

        # Store delivery tag for acknowledgment
        self._assignments[task.task_id] = str(delivery_tag)

        return task

    def acknowledge_task(self, task_id: str) -> None:
        """Acknowledge task completion."""
        delivery_tag = self._assignments.pop(task_id, None)
        if delivery_tag:
            self.task_channel.basic_ack(delivery_tag=int(delivery_tag))

    def publish_result(self, result: QueueResult) -> None:
        """Publish a result to RabbitMQ."""
        message_body = json.dumps(
            {
                "job_id": result.job_id,
                "task_id": result.task_id,
                "case_index": result.case_index,
                "role": result.role,
                "result": result.result,
            }
        )

        properties = self.pika.BasicProperties(
            delivery_mode=2 if self.durable else 1,
            message_id=f"{result.task_id}:{result.case_index}",
            headers={"job_id": result.job_id},
        )

        queue_name = self._get_result_queue(result.job_id)
        self.result_channel.basic_publish(
            exchange=self.exchange,
            routing_key=f"result.{result.job_id}",
            body=message_body,
            properties=properties,
        )

    def consume_result(self, job_id: str, timeout: float | None = None) -> Optional[QueueResult]:
        """Consume a result from RabbitMQ."""
        queue_name = self._get_result_queue(job_id)

        method_frame, header_frame, body = self.result_channel.basic_get(
            queue=queue_name, auto_ack=True
        )

        if method_frame is None:
            return None

        body_dict = json.loads(body)

        # Filter by job_id
        if body_dict.get("job_id") != job_id:
            return None

        result = QueueResult(
            job_id=body_dict["job_id"],
            task_id=body_dict["task_id"],
            case_index=body_dict["case_index"],
            role=body_dict["role"],
            result=body_dict["result"],
        )

        return result

    def signal_shutdown(self) -> None:
        """Send shutdown signal to workers."""
        shutdown_task = QueueTask(
            job_id="__shutdown__",
            task_id="__shutdown__",
            case_indices=[],
            role="",
            payload=b"",
            call_spec=None,
        )
        self.publish_task(shutdown_task)

    def register_worker(self, worker_id: str) -> None:
        """Register worker heartbeat."""
        self._heartbeats[worker_id] = time.monotonic()

    def worker_heartbeats(self) -> Dict[str, float]:
        """Return worker heartbeat timestamps."""
        return dict(self._heartbeats)

    def get_assignment(self, task_id: str) -> Optional[str]:
        """Get delivery tag for a task."""
        return self._assignments.get(task_id)

    def pop_assignment(self, task_id: str) -> Optional[str]:
        """Acknowledge and remove assignment."""
        delivery_tag = self._assignments.pop(task_id, None)
        if delivery_tag:
            self.acknowledge_task(task_id)
        return delivery_tag

    def pending_count(self) -> int:
        """Get approximate number of pending messages."""
        try:
            method = self.task_channel.queue_declare(queue=self.task_queue, passive=True)
            return method.method.message_count
        except Exception:
            return 0

    def check_stale_workers(self) -> set[str]:
        """Check for stale workers based on heartbeats."""
        timeout = float(self.config.get("heartbeat_timeout", 45.0))
        now = time.monotonic()
        stale = {wid for wid, last in self._heartbeats.items() if now - last > timeout}
        for wid in stale:
            self._heartbeats.pop(wid, None)
        return stale

    def close(self) -> None:
        """Close connections."""
        if self.connection and not self.connection.is_closed:
            self.connection.close()

