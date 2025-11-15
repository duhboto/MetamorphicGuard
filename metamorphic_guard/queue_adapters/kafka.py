"""
Apache Kafka queue adapter for distributed task execution.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

from ..queue_adapter import QueueAdapter, QueueResult, QueueTask
from ..types import JSONDict


class KafkaQueueAdapter(QueueAdapter):
    """
    Apache Kafka-backed queue adapter.
    
    Requires kafka-python to be installed: pip install kafka-python
    
    Configuration:
        {
            "bootstrap_servers": "localhost:9092",
            "task_topic": "metamorphic_guard_tasks",
            "result_topic_prefix": "metamorphic_guard_results",
            "consumer_group": "metamorphic_guard_workers",
            "auto_offset_reset": "earliest",  # or "latest"
            "enable_auto_commit": False,  # Manual commit for reliability
            "max_poll_records": 1,  # Process one message at a time
            "session_timeout_ms": 30000,
            "heartbeat_interval_ms": 3000,
        }
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        try:
            from kafka import KafkaProducer, KafkaConsumer
            from kafka.errors import KafkaError
            self.KafkaProducer = KafkaProducer
            self.KafkaConsumer = KafkaConsumer
            self.KafkaError = KafkaError
        except ImportError as e:
            raise ImportError(
                "kafka-python is required for Kafka adapter. Install with: pip install kafka-python"
            ) from e

        self.config = config
        self.bootstrap_servers = config.get("bootstrap_servers", "localhost:9092")
        self.task_topic = config.get("task_topic", "metamorphic_guard_tasks")
        self.result_topic_prefix = config.get("result_topic_prefix", "metamorphic_guard_results")
        self.consumer_group = config.get("consumer_group", "metamorphic_guard_workers")
        self.auto_offset_reset = config.get("auto_offset_reset", "earliest")
        self.enable_auto_commit = bool(config.get("enable_auto_commit", False))
        self.max_poll_records = int(config.get("max_poll_records", 1))
        self.session_timeout_ms = int(config.get("session_timeout_ms", 30000))
        self.heartbeat_interval_ms = int(config.get("heartbeat_interval_ms", 3000))

        # Create producer for publishing
        self.producer = self.KafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
        )

        # Consumer will be created per job for result consumption
        self._consumers: Dict[str, Any] = {}

        # Worker tracking
        self._heartbeats: Dict[str, float] = {}
        self._assignments: Dict[str, str] = {}  # task_id -> partition:offset

    def _get_result_topic(self, job_id: str) -> str:
        """Get result topic name for a job."""
        return f"{self.result_topic_prefix}_{job_id}"

    def publish_task(self, task: QueueTask) -> None:
        """Publish a task to Kafka."""
        message = {
            "job_id": task.job_id,
            "task_id": task.task_id,
            "case_indices": task.case_indices,
            "role": task.role,
            "payload": task.payload.hex() if isinstance(task.payload, bytes) else task.payload,
            "compressed": task.compressed,
            "use_msgpack": task.use_msgpack,
            "call_spec": task.call_spec,
        }

        # Use job_id as key for partitioning (ensures same job goes to same partition)
        future = self.producer.send(
            self.task_topic,
            key=task.job_id,
            value=message,
        )

        # Wait for send to complete (with timeout)
        try:
            future.get(timeout=10)
        except Exception as e:
            raise RuntimeError(f"Failed to publish task to Kafka: {e}") from e

    def consume_task(self, worker_id: str, timeout: float | None = None) -> Optional[QueueTask]:
        """Consume a task from Kafka."""
        # Create consumer if it doesn't exist
        if worker_id not in self._consumers:
            consumer = self.KafkaConsumer(
                self.task_topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.consumer_group,
                auto_offset_reset=self.auto_offset_reset,
                enable_auto_commit=self.enable_auto_commit,
                max_poll_records=self.max_poll_records,
                session_timeout_ms=self.session_timeout_ms,
                heartbeat_interval_ms=self.heartbeat_interval_ms,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            )
            self._consumers[worker_id] = consumer
        else:
            consumer = self._consumers[worker_id]

        # Poll for messages
        timeout_ms = int((timeout or 1.0) * 1000)
        messages = consumer.poll(timeout_ms=timeout_ms)

        if not messages:
            return None

        # Get first message from any partition
        for topic_partition, message_list in messages.items():
            if message_list:
                msg = message_list[0]
                body = msg.value

                # Handle shutdown signal
                if body.get("job_id") == "__shutdown__":
                    return QueueTask(
                        job_id="__shutdown__",
                        task_id="__shutdown__",
                        case_indices=[],
                        role="",
                        payload=b"",
                        call_spec=None,
                    )

                task = QueueTask(
                    job_id=body["job_id"],
                    task_id=body["task_id"],
                    case_indices=body["case_indices"],
                    role=body["role"],
                    payload=bytes.fromhex(body["payload"])
                    if isinstance(body["payload"], str)
                    else body["payload"],
                    compressed=body.get("compressed", True),
                    use_msgpack=body.get("use_msgpack", False),
                    call_spec=body.get("call_spec"),
                )

                # Store partition and offset for commit
                assignment_key = f"{topic_partition.partition}:{msg.offset}"
                self._assignments[task.task_id] = assignment_key

                # Commit offset if auto-commit is disabled
                if not self.enable_auto_commit:
                    consumer.commit()

                return task

        return None

    def acknowledge_task(self, task_id: str) -> None:
        """Acknowledge task completion (commit offset)."""
        # Offset is already committed in consume_task, but we can track it here
        self._assignments.pop(task_id, None)

    def publish_result(self, result: QueueResult) -> None:
        """Publish a result to Kafka."""
        topic = self._get_result_topic(result.job_id)
        message = {
            "job_id": result.job_id,
            "task_id": result.task_id,
            "case_index": result.case_index,
            "role": result.role,
            "result": result.result,
        }

        # Use job_id as key for partitioning
        future = self.producer.send(
            topic,
            key=result.job_id,
            value=message,
        )

        try:
            future.get(timeout=10)
        except Exception as e:
            raise RuntimeError(f"Failed to publish result to Kafka: {e}") from e

    def consume_result(self, job_id: str, timeout: float | None = None) -> Optional[QueueResult]:
        """Consume a result from Kafka."""
        topic = self._get_result_topic(job_id)

        # Create consumer for this job if it doesn't exist
        consumer_key = f"result_{job_id}"
        if consumer_key not in self._consumers:
            consumer = self.KafkaConsumer(
                topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id=f"{self.consumer_group}_results",
                auto_offset_reset="earliest",
                enable_auto_commit=True,  # Auto-commit for results
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                consumer_timeout_ms=int((timeout or 1.0) * 1000),
            )
            self._consumers[consumer_key] = consumer
        else:
            consumer = self._consumers[consumer_key]

        # Poll for messages
        timeout_ms = int((timeout or 1.0) * 1000)
        messages = consumer.poll(timeout_ms=timeout_ms)

        if not messages:
            return None

        # Get first message
        for topic_partition, message_list in messages.items():
            if message_list:
                msg = message_list[0]
                body = msg.value

                # Filter by job_id
                if body.get("job_id") != job_id:
                    continue

                result = QueueResult(
                    job_id=body["job_id"],
                    task_id=body["task_id"],
                    case_index=body["case_index"],
                    role=body["role"],
                    result=body["result"],
                )

                return result

        return None

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
        """Get partition:offset for a task."""
        return self._assignments.get(task_id)

    def pop_assignment(self, task_id: str) -> Optional[str]:
        """Remove assignment after task completion."""
        return self._assignments.pop(task_id, None)

    def pending_count(self) -> int:
        """Get approximate number of pending messages (not directly available in Kafka)."""
        # Kafka doesn't provide a direct way to get queue depth
        # This would require admin client and topic metadata
        # For now, return 0 (unknown)
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
        """Close all consumers and producer."""
        for consumer in self._consumers.values():
            try:
                consumer.close()
            except Exception:
                pass
        self._consumers.clear()

        if self.producer:
            try:
                self.producer.close()
            except Exception:
                pass

