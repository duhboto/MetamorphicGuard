"""
AWS SQS queue adapter for distributed task execution.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

from ..queue_adapter import QueueAdapter, QueueResult, QueueTask
from ..types import JSONDict


class SQSQueueAdapter(QueueAdapter):
    """
    AWS SQS-backed queue adapter.
    
    Requires boto3 to be installed: pip install boto3
    
    Configuration:
        {
            "queue_url": "https://sqs.region.amazonaws.com/account/queue-name",
            "region_name": "us-east-1",  # Optional, defaults to queue URL region
            "visibility_timeout": 30,  # Seconds tasks are hidden after consumption
            "max_receive_count": 3,  # Max retries before moving to DLQ
            "wait_time_seconds": 20,  # Long polling wait time
        }
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        try:
            import boto3
        except ImportError as e:
            raise ImportError(
                "boto3 is required for SQS adapter. Install with: pip install boto3"
            ) from e

        self.config = config
        self.queue_url = config.get("queue_url")
        if not self.queue_url:
            raise ValueError("SQS adapter requires 'queue_url' in config")

        region_name = config.get("region_name")
        if not region_name and "sqs." in self.queue_url:
            # Extract region from queue URL
            parts = self.queue_url.split(".")
            if len(parts) >= 2:
                region_name = parts[1]

        self.sqs = boto3.client("sqs", region_name=region_name or "us-east-1")
        self.visibility_timeout = int(config.get("visibility_timeout", 30))
        self.max_receive_count = int(config.get("max_receive_count", 3))
        self.wait_time_seconds = int(config.get("wait_time_seconds", 20))

        # Separate queues for tasks and results
        self.task_queue_url = self.queue_url
        self.result_queue_url = config.get("result_queue_url") or self.queue_url

        # Worker tracking
        self._heartbeats: Dict[str, float] = {}
        self._assignments: Dict[str, str] = {}

    def _task_key(self, job_id: str) -> str:
        """Generate SQS message attribute key for task queue."""
        return f"mg:task:{job_id}"

    def _result_key(self, job_id: str) -> str:
        """Generate SQS message attribute key for result queue."""
        return f"mg:result:{job_id}"

    def publish_task(self, task: QueueTask) -> None:
        """Publish a task to SQS."""
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

        message_attributes = {
            "job_id": {"DataType": "String", "StringValue": task.job_id},
            "task_id": {"DataType": "String", "StringValue": task.task_id},
            "role": {"DataType": "String", "StringValue": task.role},
        }

        self.sqs.send_message(
            QueueUrl=self.task_queue_url,
            MessageBody=message_body,
            MessageAttributes=message_attributes,
        )

    def consume_task(self, worker_id: str, timeout: float | None = None) -> Optional[QueueTask]:
        """Consume a task from SQS."""
        wait_time = min(int(timeout or self.wait_time_seconds), 20)  # SQS max is 20

        response = self.sqs.receive_message(
            QueueUrl=self.task_queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=wait_time,
            VisibilityTimeout=self.visibility_timeout,
            MessageAttributeNames=["All"],
        )

        messages = response.get("Messages", [])
        if not messages:
            return None

        message = messages[0]
        receipt_handle = message["ReceiptHandle"]
        body = json.loads(message["Body"])

        # Handle SNS-wrapped messages
        if "Message" in body:
            body = json.loads(body["Message"])

        task = QueueTask(
            job_id=body["job_id"],
            task_id=body["task_id"],
            case_indices=body["case_indices"],
            role=body["role"],
            payload=bytes.fromhex(body["payload"]) if isinstance(body["payload"], str) else body["payload"],
            compressed=body.get("compressed", True),
            use_msgpack=body.get("use_msgpack", False),
            call_spec=body.get("call_spec"),
        )

        # Store receipt handle for later deletion
        self._assignments[task.task_id] = receipt_handle

        return task

    def publish_result(self, result: QueueResult) -> None:
        """Publish a result to SQS."""
        message_body = json.dumps(
            {
                "job_id": result.job_id,
                "task_id": result.task_id,
                "case_index": result.case_index,
                "role": result.role,
                "result": result.result,
            }
        )

        message_attributes = {
            "job_id": {"DataType": "String", "StringValue": result.job_id},
            "task_id": {"DataType": "String", "StringValue": result.task_id},
        }

        self.sqs.send_message(
            QueueUrl=self.result_queue_url,
            MessageBody=message_body,
            MessageAttributes=message_attributes,
        )

    def consume_result(self, job_id: str, timeout: float | None = None) -> Optional[QueueResult]:
        """Consume a result from SQS."""
        wait_time = min(int(timeout or self.wait_time_seconds), 20)

        response = self.sqs.receive_message(
            QueueUrl=self.result_queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=wait_time,
            MessageAttributeNames=["All"],
        )

        messages = response.get("Messages", [])
        if not messages:
            return None

        message = messages[0]
        body = json.loads(message["Body"])

        # Handle SNS-wrapped messages
        if "Message" in body:
            body = json.loads(body["Message"])

        # Filter by job_id if provided
        if job_id and body.get("job_id") != job_id:
            # Put message back
            self.sqs.change_message_visibility(
                QueueUrl=self.result_queue_url,
                ReceiptHandle=message["ReceiptHandle"],
                VisibilityTimeout=0,
            )
            return None

        result = QueueResult(
            job_id=body["job_id"],
            task_id=body["task_id"],
            case_index=body["case_index"],
            role=body["role"],
            result=body["result"],
        )

        # Delete message after processing
        self.sqs.delete_message(
            QueueUrl=self.result_queue_url, ReceiptHandle=message["ReceiptHandle"]
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
        """Register worker heartbeat (stored in memory, could use DynamoDB for distributed)."""
        self._heartbeats[worker_id] = time.monotonic()

    def worker_heartbeats(self) -> Dict[str, float]:
        """Return worker heartbeat timestamps."""
        return dict(self._heartbeats)

    def get_assignment(self, task_id: str) -> Optional[str]:
        """Get receipt handle for a task (for visibility timeout management)."""
        return self._assignments.get(task_id)

    def pop_assignment(self, task_id: str) -> Optional[str]:
        """Remove assignment after task completion."""
        return self._assignments.pop(task_id, None)

    def pending_count(self) -> int:
        """Get approximate number of pending messages."""
        try:
            response = self.sqs.get_queue_attributes(
                QueueUrl=self.task_queue_url, AttributeNames=["ApproximateNumberOfMessages"]
            )
            return int(response["Attributes"].get("ApproximateNumberOfMessages", 0))
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

