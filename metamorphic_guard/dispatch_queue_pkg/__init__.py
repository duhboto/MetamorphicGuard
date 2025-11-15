"""
Queue-based dispatch execution.

This package provides queue-based dispatcher capabilities split across modules:
- queue_dispatcher: Main QueueDispatcher class
- worker_manager: Local worker thread management
- task_distribution: Task batching and distribution logic
"""

from .queue_dispatcher import QueueDispatcher

__all__ = ["QueueDispatcher"]

