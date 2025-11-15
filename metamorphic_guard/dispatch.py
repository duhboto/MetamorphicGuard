from abc import ABC, abstractmethod
import pickle
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .monitoring import Monitor, MonitorRecord
from .plugins import dispatcher_plugins

RunCase = Callable[[int, Tuple[Any, ...]], Dict[str, Any]]


class Dispatcher(ABC):
    """Abstract base class for dispatching evaluation tasks."""

    def __init__(self, workers: int = 1, *, kind: str = "local") -> None:
        self.workers = max(1, workers)
        self.kind = kind

    @abstractmethod
    def execute(
        self,
        *,
        test_inputs: Sequence[Tuple[Any, ...]],
        run_case: RunCase,
        role: str,
        monitors: Sequence[Monitor] | None = None,
        call_spec: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Execute the provided run_case function against all inputs."""


class LocalDispatcher(Dispatcher):
    """
    Local dispatcher that executes evaluations using threads or processes.
    
    By default uses threads (ThreadPoolExecutor) for I/O-bound tasks like
    sandbox execution. Can be configured to use processes (ProcessPoolExecutor)
    for CPU-bound tasks, though this requires all callables to be picklable.
    """

    def __init__(self, workers: int = 1, *, use_process_pool: bool = False, auto_workers: bool = False) -> None:
        super().__init__(workers, kind="local")
        self.use_process_pool = use_process_pool
        self.auto_workers = auto_workers

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
        # Pre-allocate results list for memory efficiency
        # Use None initially to reduce memory footprint for large test suites
        results: List[Dict[str, Any]] = [None] * len(test_inputs)  # type: ignore[list-item]

        def _invoke(index: int, args: Tuple[Any, ...]) -> Dict[str, Any]:
            result = run_case(index, args)
            duration = float(result.get("duration_ms") or 0.0)
            success = bool(result.get("success"))
            record = MonitorRecord(
                case_index=index,
                role=role,
                duration_ms=duration,
                success=success,
                result=result,
            )
            for monitor in monitors:
                monitor.record(record)
            
            # Export trace to OpenTelemetry if enabled
            trace_test_case = None
            is_telemetry_enabled = None
            try:
                from .telemetry import (
                    trace_test_case as _trace_test_case,
                    is_telemetry_enabled as _is_telemetry_enabled,
                )
                trace_test_case = _trace_test_case
                is_telemetry_enabled = _is_telemetry_enabled
            except ImportError:
                trace_test_case = None
                is_telemetry_enabled = None

            if trace_test_case is not None and is_telemetry_enabled is not None:
                try:
                    if is_telemetry_enabled():
                        tokens = result.get("tokens_total")
                        cost_usd = result.get("cost_usd")
                        trace_test_case(
                            case_index=index,
                            role=role,
                            duration_ms=duration,
                            success=success,
                            tokens=tokens,
                            cost_usd=cost_usd,
                        )
                except Exception:
                    # Silently fail if telemetry export fails
                    pass
            
            return result

        # Auto-detect optimal worker count if enabled
        effective_workers = self.workers
        if self.auto_workers and self.workers == 1:
            import os
            # For I/O-bound tasks (sandbox execution), use more workers
            # Default to CPU count * 2 for I/O-bound, or CPU count for CPU-bound
            cpu_count = os.cpu_count() or 4
            effective_workers = cpu_count * 2 if not self.use_process_pool else cpu_count
        
        if effective_workers <= 1:
            for idx, args in enumerate(test_inputs):
                results[idx] = _invoke(idx, args)
            return results

        # Use process pool if requested, otherwise use thread pool
        # Note: Process pools require picklable functions, which may not work
        # with closures that capture non-picklable state (e.g., monitors)
        executor_class = ProcessPoolExecutor if self.use_process_pool else ThreadPoolExecutor
        
        try:
            with executor_class(max_workers=effective_workers) as pool:
                future_map = {
                    pool.submit(_invoke, idx, args): idx
                    for idx, args in enumerate(test_inputs)
                }
                for future in as_completed(future_map):
                    idx = future_map[future]
                    result = future.result()
                    results[idx] = result
                    # Allow garbage collection of future object immediately
                    del future_map[future]
        except (AttributeError, TypeError, pickle.PickleError) as e:
            # If process pool fails due to pickling issues, fall back to threads
            if self.use_process_pool:
                import warnings
                warnings.warn(
                    f"Process pool failed ({e}), falling back to thread pool. "
                    "This may occur if run_case or monitors are not picklable.",
                    UserWarning,
                )
                with ThreadPoolExecutor(max_workers=self.workers) as pool:
                    future_map = {
                        pool.submit(_invoke, idx, args): idx
                        for idx, args in enumerate(test_inputs)
                    }
                    for future in as_completed(future_map):
                        idx = future_map[future]
                        results[idx] = future.result()
            else:
                raise
        return results


# The queue-based dispatcher is defined in dispatch/queue_dispatcher.py to avoid circular imports.
# Import it lazily using absolute import to avoid circular dependency issues.
def _lazy_import_queue_dispatcher():
    """Lazy import of QueueDispatcher to avoid circular imports."""
    from .dispatch.queue_dispatcher import QueueDispatcher  # noqa: E402  # isort:skip
    return QueueDispatcher

# Store the function but don't call it yet - actual imports happen at runtime
# QueueDispatcher will be imported when needed via ensure_dispatcher
QueueDispatcher = None  # type: ignore[assignment,misc]  # Set lazily to avoid circular import


def ensure_dispatcher(
    dispatcher: str | Dispatcher | None,
    workers: int,
    queue_config: Dict[str, Any] | None = None,
    *,
    use_process_pool: bool = False,
    auto_workers: bool = False,
) -> Dispatcher:
    """
    Return an appropriate dispatcher instance based on user input.
    
    Args:
        dispatcher: Dispatcher name or instance
        workers: Number of worker threads/processes
        queue_config: Configuration for queue dispatcher
        use_process_pool: If True, use ProcessPoolExecutor for LocalDispatcher
                         (requires picklable callables)
    """
    if isinstance(dispatcher, Dispatcher):
        dispatcher.workers = max(1, workers)
        return dispatcher

    name = (dispatcher or "local").lower()
    if name in {"local", "threaded"}:
        return LocalDispatcher(workers, use_process_pool=use_process_pool, auto_workers=auto_workers)
    if name == "process":
        # Explicit process pool dispatcher
        return LocalDispatcher(workers, use_process_pool=True, auto_workers=auto_workers)
    if name in {"queue", "distributed"}:
        QueueDispatcher = _lazy_import_queue_dispatcher()  # Lazy import to avoid circular dependency
        return QueueDispatcher(workers, queue_config)

    plugin_registry = dispatcher_plugins()
    definition = plugin_registry.get(name)
    if definition is not None:
        factory = definition.factory
        instance = factory(workers=workers, config=queue_config)
        if not isinstance(instance, Dispatcher):
            raise TypeError(f"Dispatcher plugin '{name}' must return a Dispatcher instance.")
        return instance

    raise ValueError(f"Unknown dispatcher '{dispatcher}'. Available plugins: {list(plugin_registry.keys())}")

