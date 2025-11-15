"""
Queue-based dispatch execution.

This module is maintained for backward compatibility.
All functionality has been moved to the dispatch package.
"""

# Re-export from the refactored module structure
from .dispatch import QueueDispatcher

# Backwards compatibility exports
from .queue_adapter import (
    QueueAdapter,
    InMemoryQueueAdapter,
    RedisQueueAdapter,
    QueueTask,
    QueueResult,
)
from .queue_serialization import decode_args, prepare_payload
from .observability import increment_queue_requeued

_Task = QueueTask
_Result = QueueResult
_decode_args = decode_args
_prepare_payload = prepare_payload

__all__ = [
    "QueueDispatcher",
    "QueueAdapter",
    "InMemoryQueueAdapter",
    "RedisQueueAdapter",
    "QueueTask",
    "QueueResult",
    "_Task",
    "_Result",
    "_decode_args",
    "_prepare_payload",
    "increment_queue_requeued",
]
