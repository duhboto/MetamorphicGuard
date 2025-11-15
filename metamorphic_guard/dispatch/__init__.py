"""
Queue-based dispatch execution.

This package provides queue-based dispatcher capabilities split across modules:
- queue_dispatcher: Main QueueDispatcher class
- worker_manager: Local worker thread management
- task_distribution: Task batching and distribution logic
"""

# Import from dispatch.py file (sibling file, not this package)
import importlib.util
from pathlib import Path

# Load the dispatch.py file to get Dispatcher and LocalDispatcher
_dispatch_file_path = Path(__file__).parent.parent / 'dispatch.py'
_spec = importlib.util.spec_from_file_location('metamorphic_guard._dispatch_file', _dispatch_file_path)
if _spec and _spec.loader:
    _dispatch_file = importlib.util.module_from_spec(_spec)
    # Need to set the module's __package__ so relative imports work
    _dispatch_file.__package__ = 'metamorphic_guard'
    _spec.loader.exec_module(_dispatch_file)
    Dispatcher = _dispatch_file.Dispatcher  # type: ignore[attr-defined]
    LocalDispatcher = _dispatch_file.LocalDispatcher  # type: ignore[attr-defined]
    RunCase = _dispatch_file.RunCase  # type: ignore[attr-defined]
    ensure_dispatcher = _dispatch_file.ensure_dispatcher  # type: ignore[attr-defined]
else:
    raise ImportError("Could not load dispatch.py file")

# Lazy import to avoid circular dependencies
def __getattr__(name: str):
    if name == "QueueDispatcher":
        from .queue_dispatcher import QueueDispatcher
        return QueueDispatcher
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["Dispatcher", "LocalDispatcher", "RunCase", "ensure_dispatcher", "QueueDispatcher"]


