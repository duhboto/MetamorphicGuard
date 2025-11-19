from abc import ABC, abstractmethod
import pickle
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from ..monitoring import Monitor, MonitorRecord
from ..plugins import dispatcher_plugins
from .base import Dispatcher, RunCase


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
        seed: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        monitors = list(monitors or [])
        # Pre-allocate results list for memory efficiency
        # Use None initially to reduce memory footprint for large test suites
        results: List[Dict[str, Any]] = [None] * len(test_inputs)  # type: ignore[list-item]

        # Initialize RNG if seed provided
        if seed is not None:
            import random
            # We can't easily seed the pool workers directly without initializer
            # But we can seed the main process if needed, or pass seed to _invoke
            pass

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
                from ..telemetry import (
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
                        result = future.result()
                    results[idx] = future.result()
            else:
                raise
        return results


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
        from .queue_dispatcher import QueueDispatcher
        return QueueDispatcher(workers, queue_config)

    if name == "shadow":
        from .shadow import ShadowDispatcher
        # Default to local delegate for simple shadow setup
        delegate = LocalDispatcher(workers, use_process_pool=use_process_pool, auto_workers=auto_workers)
        
        sample_rate = 1.0
        safe_mode = True
        
        # If queue_config is provided, try to read shadow settings from it
        if queue_config:
            sample_rate = float(queue_config.get("sample_rate", 1.0))
            safe_mode = bool(queue_config.get("safe_mode", True))
            
        return ShadowDispatcher(delegate, sample_rate=sample_rate, safe_mode=safe_mode)

    plugin_registry = dispatcher_plugins()
    definition = plugin_registry.get(name)
    if definition is not None:
        factory = definition.factory
        instance = factory(workers=workers, config=queue_config)
        if not isinstance(instance, Dispatcher):
            raise TypeError(f"Dispatcher plugin '{name}' must return a Dispatcher instance.")
        return instance

    raise ValueError(f"Unknown dispatcher '{dispatcher}'. Available plugins: {list(plugin_registry.keys())}")

