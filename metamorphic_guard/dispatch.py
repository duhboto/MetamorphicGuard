from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    """Threaded dispatcher that executes evaluations locally."""

    def __init__(self, workers: int = 1) -> None:
        super().__init__(workers, kind="local")

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
        results: List[Dict[str, Any]] = [{} for _ in range(len(test_inputs))]

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

        if self.workers <= 1:
            for idx, args in enumerate(test_inputs):
                results[idx] = _invoke(idx, args)
            return results

        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            future_map = {
                pool.submit(_invoke, idx, args): idx
                for idx, args in enumerate(test_inputs)
            }
            for future in as_completed(future_map):
                idx = future_map[future]
                results[idx] = future.result()
        return results


# The queue-based dispatcher is defined in the sibling module to avoid circular imports.
from .dispatch_queue import QueueDispatcher  # noqa: E402  # isort:skip


def ensure_dispatcher(
    dispatcher: str | Dispatcher | None,
    workers: int,
    queue_config: Dict[str, Any] | None = None,
) -> Dispatcher:
    """Return an appropriate dispatcher instance based on user input."""
    if isinstance(dispatcher, Dispatcher):
        dispatcher.workers = max(1, workers)
        return dispatcher

    name = (dispatcher or "local").lower()
    if name in {"local", "threaded"}:
        return LocalDispatcher(workers)
    if name in {"queue", "distributed"}:
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

