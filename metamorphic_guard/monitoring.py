from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
import multiprocessing as mp
import queue
from typing import Any, Dict, Sequence, List, DefaultDict, Callable
from collections import defaultdict

from .plugins import PluginDefinition, monitor_plugins


@dataclass(frozen=True)
class MonitorContext:
    task: str
    total_cases: int


@dataclass
class MonitorRecord:
    case_index: int
    role: str  # "baseline" or "candidate"
    duration_ms: float
    success: bool
    result: Dict[str, Any]


class Monitor(ABC):
    """Base class for advanced evaluation monitors."""

    def __init__(self) -> None:
        self._context: MonitorContext | None = None

    def identifier(self) -> str:
        return self.__class__.__name__

    def start(self, context: MonitorContext) -> None:
        self._context = context

    @abstractmethod
    def record(self, record: MonitorRecord) -> None:
        """Observe a single execution result."""

    @abstractmethod
    def finalize(self) -> Dict[str, Any]:
        """Return aggregated monitor output."""


class LatencyMonitor(Monitor):
    """Track latency distribution and flag regressions."""

    def __init__(self, percentile: float = 0.95, alert_ratio: float = 1.2) -> None:
        super().__init__()
        self.percentile = percentile
        self.alert_ratio = alert_ratio
        self._lock = threading.Lock()
        self._durations: Dict[str, List[float]] = {"baseline": [], "candidate": []}

    def record(self, record: MonitorRecord) -> None:
        with self._lock:
            bucket = self._durations.setdefault(record.role, [])
            bucket.append(float(record.duration_ms or 0.0))

    def finalize(self) -> Dict[str, Any]:
        summary: Dict[str, Dict[str, Any]] = {}
        for role, values in self._durations.items():
            if values:
                sorted_vals = sorted(values)
                idx = max(0, min(len(sorted_vals) - 1, int(self.percentile * len(sorted_vals)) - 1))
                mean = sum(sorted_vals) / len(sorted_vals)
                summary[role] = {
                    "count": len(sorted_vals),
                    "mean_ms": mean,
                    "p95_ms": sorted_vals[idx],
                }
            else:
                summary[role] = {"count": 0, "mean_ms": None, "p95_ms": None}

        alerts: List[Dict[str, Any]] = []
        baseline_info = summary.get("baseline", {})
        candidate_info = summary.get("candidate", {})
        baseline_p95 = baseline_info.get("p95_ms")
        candidate_p95 = candidate_info.get("p95_ms")
        if (
            baseline_p95
            and candidate_p95
            and baseline_p95 > 0
            and candidate_p95 > baseline_p95 * self.alert_ratio
        ):
            alerts.append(
                {
                    "type": "latency_regression",
                    "baseline_p95_ms": baseline_p95,
                    "candidate_p95_ms": candidate_p95,
                    "ratio": candidate_p95 / baseline_p95,
                    "threshold": self.alert_ratio,
                }
            )

        return {
            "id": self.identifier(),
            "type": "latency",
            "percentile": self.percentile,
            "summary": summary,
            "alerts": alerts,
        }


class SuccessRateMonitor(Monitor):
    """Compare baseline vs candidate success rates."""

    def __init__(self, alert_drop_ratio: float = 0.98) -> None:
        super().__init__()
        self.alert_drop_ratio = alert_drop_ratio
        self._lock = threading.Lock()
        self._counts = {
            "baseline": {"success": 0, "total": 0},
            "candidate": {"success": 0, "total": 0},
        }

    def record(self, record: MonitorRecord) -> None:
        with self._lock:
            bucket = self._counts.setdefault(record.role, {"success": 0, "total": 0})
            bucket["total"] += 1
            if record.success:
                bucket["success"] += 1

    def finalize(self) -> Dict[str, Any]:
        summary: Dict[str, Dict[str, float]] = {}
        for role, counts in self._counts.items():
            total = counts["total"] or 1
            summary[role] = {
                "success": counts["success"],
                "total": counts["total"],
                "rate": counts["success"] / total,
            }

        alerts: List[Dict[str, Any]] = []
        baseline_rate = summary.get("baseline", {}).get("rate")
        candidate_rate = summary.get("candidate", {}).get("rate")
        if (
            baseline_rate is not None
            and candidate_rate is not None
            and baseline_rate > 0
            and candidate_rate < baseline_rate * self.alert_drop_ratio
        ):
            alerts.append(
                {
                    "type": "success_rate_drop",
                    "baseline_rate": baseline_rate,
                    "candidate_rate": candidate_rate,
                    "threshold_ratio": self.alert_drop_ratio,
                }
            )

        return {
            "id": self.identifier(),
            "type": "success_rate",
            "summary": summary,
            "alerts": alerts,
        }


class TrendMonitor(Monitor):
    """Detect upward trends in duration."""

    def __init__(self, window: int = 10, alert_slope_ms: float = 1.0) -> None:
        super().__init__()
        self.window = max(2, window)
        self.alert_slope_ms = alert_slope_ms
        self._lock = threading.Lock()
        self._data: Dict[str, List[tuple[int, float]]] = {"baseline": [], "candidate": []}

    def record(self, record: MonitorRecord) -> None:
        with self._lock:
            bucket = self._data.setdefault(record.role, [])
            bucket.append((record.case_index, float(record.duration_ms or 0.0)))
            if len(bucket) > self.window:
                bucket.pop(0)

    def _slope(self, points: List[tuple[int, float]]) -> float:
        if len(points) < 2:
            return 0.0
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        n = len(points)
        mean_x = sum(xs) / n
        mean_y = sum(ys) / n
        num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
        den = sum((x - mean_x) ** 2 for x in xs)
        return num / den if den else 0.0

    def finalize(self) -> Dict[str, Any]:
        summary: Dict[str, Dict[str, float]] = {}
        alerts: List[Dict[str, Any]] = []

        for role, points in self._data.items():
            slope = self._slope(points)
            summary[role] = {"observations": len(points), "slope": slope}
            if slope > self.alert_slope_ms:
                alerts.append(
                    {
                        "type": "duration_trend",
                        "role": role,
                        "slope": slope,
                        "threshold": self.alert_slope_ms,
                    }
                )

        return {
            "id": self.identifier(),
            "type": "trend",
            "window": self.window,
            "summary": summary,
            "alerts": alerts,
        }


class FairnessGapMonitor(Monitor):
    """Compare acceptance rates across sensitive groups and flag gaps."""

    def __init__(self, max_gap: float = 0.05, field: str = "group") -> None:
        super().__init__()
        self.max_gap = max(0.0, float(max_gap))
        self.field = field
        self._lock = threading.Lock()
        self._counts: Dict[str, DefaultDict[str, Dict[str, int]]] = {
            "baseline": defaultdict(lambda: {"success": 0, "total": 0}),
            "candidate": defaultdict(lambda: {"success": 0, "total": 0}),
        }

    def record(self, record: MonitorRecord) -> None:
        group = record.result.get(self.field)
        if group is None:
            return
        with self._lock:
            bucket = self._counts.setdefault(record.role, defaultdict(lambda: {"success": 0, "total": 0}))
            stats = bucket[group]
            stats["total"] += 1
            if record.success:
                stats["success"] += 1

    def _rates(self, data: DefaultDict[str, Dict[str, int]]) -> Dict[str, float]:
        rates: Dict[str, float] = {}
        for group, stats in data.items():
            total = stats["total"]
            if total:
                rates[group] = stats["success"] / total
        return rates

    def finalize(self) -> Dict[str, Any]:
        alerts: List[Dict[str, Any]] = []
        baseline_rates = self._rates(self._counts.get("baseline", defaultdict(dict)))
        candidate_rates = self._rates(self._counts.get("candidate", defaultdict(dict)))
        combined_groups = set(baseline_rates) | set(candidate_rates)

        gaps: Dict[str, Dict[str, float]] = {}
        max_gap_detected = 0.0
        for group in combined_groups:
            base_rate = baseline_rates.get(group)
            cand_rate = candidate_rates.get(group)
            entry: Dict[str, float] = {}
            if base_rate is not None:
                entry["baseline_rate"] = base_rate
            if cand_rate is not None:
                entry["candidate_rate"] = cand_rate
            if base_rate is not None and cand_rate is not None:
                gap = abs(base_rate - cand_rate)
                entry["gap"] = gap
                max_gap_detected = max(max_gap_detected, gap)
                if gap > self.max_gap:
                    alerts.append(
                        {
                            "type": "fairness_gap",
                            "group": group,
                            "gap": gap,
                            "threshold": self.max_gap,
                            "baseline_rate": base_rate,
                            "candidate_rate": cand_rate,
                        }
                    )
            gaps[group] = entry

        return {
            "id": self.identifier(),
            "type": "fairness_gap",
            "field": self.field,
            "summary": {
                "baseline": baseline_rates,
                "candidate": candidate_rates,
                "max_gap": max_gap_detected,
                "groups": gaps,
            },
            "alerts": alerts,
        }


class ResourceUsageMonitor(Monitor):
    """Track resource consumption metrics surfaced by sandbox results."""

    def __init__(self, metric: str = "cpu_ms", alert_ratio: float = 1.5) -> None:
        super().__init__()
        self.metric = metric
        self.alert_ratio = max(0.0, float(alert_ratio))
        self._lock = threading.Lock()
        self._samples: Dict[str, List[float]] = {"baseline": [], "candidate": []}

    def record(self, record: MonitorRecord) -> None:
        usage = None
        metrics = record.result.get("resource_usage")
        if isinstance(metrics, dict) and self.metric in metrics:
            usage = metrics[self.metric]
        elif self.metric in record.result:
            usage = record.result[self.metric]
        if usage is None:
            return
        with self._lock:
            self._samples.setdefault(record.role, []).append(float(usage))

    def finalize(self) -> Dict[str, Any]:
        summary: Dict[str, Dict[str, float]] = {}
        for role, values in self._samples.items():
            if values:
                mean = sum(values) / len(values)
                summary[role] = {"count": len(values), "mean": mean}
            else:
                summary[role] = {"count": 0, "mean": None}

        alerts: List[Dict[str, Any]] = []
        baseline_mean = summary.get("baseline", {}).get("mean")
        candidate_mean = summary.get("candidate", {}).get("mean")
        if (
            baseline_mean is not None
            and baseline_mean > 0
            and candidate_mean is not None
            and candidate_mean > baseline_mean * self.alert_ratio
        ):
            alerts.append(
                {
                    "type": "resource_regression",
                    "metric": self.metric,
                    "baseline_mean": baseline_mean,
                    "candidate_mean": candidate_mean,
                    "ratio": candidate_mean / baseline_mean,
                    "threshold": self.alert_ratio,
                }
            )

        return {
            "id": self.identifier(),
            "type": "resource_usage",
            "metric": self.metric,
            "summary": summary,
            "alerts": alerts,
        }


class LLMCostMonitor(Monitor):
    """Track LLM token usage and cost metrics."""

    def __init__(self, alert_cost_ratio: float = 1.5) -> None:
        super().__init__()
        self.alert_cost_ratio = max(0.0, float(alert_cost_ratio))
        self._lock = threading.Lock()
        self._tokens: Dict[str, Dict[str, List[float]]] = {
            "baseline": {"prompt": [], "completion": [], "total": []},
            "candidate": {"prompt": [], "completion": [], "total": []},
        }
        self._costs: Dict[str, List[float]] = {"baseline": [], "candidate": []}

    def record(self, record: MonitorRecord) -> None:
        result = record.result
        with self._lock:
            role = record.role
            if "tokens_prompt" in result:
                self._tokens[role]["prompt"].append(float(result["tokens_prompt"]))
            if "tokens_completion" in result:
                self._tokens[role]["completion"].append(float(result["tokens_completion"]))
            if "tokens_total" in result:
                self._tokens[role]["total"].append(float(result["tokens_total"]))
            if "cost_usd" in result:
                self._costs[role].append(float(result["cost_usd"]))

    def finalize(self) -> Dict[str, Any]:
        summary: Dict[str, Dict[str, Any]] = {}
        for role in ["baseline", "candidate"]:
            role_tokens = self._tokens.get(role, {})
            role_costs = self._costs.get(role, [])
            summary[role] = {
                "tokens_prompt": {
                    "count": len(role_tokens.get("prompt", [])),
                    "total": sum(role_tokens.get("prompt", [])),
                    "mean": sum(role_tokens.get("prompt", [])) / len(role_tokens.get("prompt", []))
                    if role_tokens.get("prompt")
                    else 0.0,
                },
                "tokens_completion": {
                    "count": len(role_tokens.get("completion", [])),
                    "total": sum(role_tokens.get("completion", [])),
                    "mean": sum(role_tokens.get("completion", [])) / len(role_tokens.get("completion", []))
                    if role_tokens.get("completion")
                    else 0.0,
                },
                "tokens_total": {
                    "count": len(role_tokens.get("total", [])),
                    "total": sum(role_tokens.get("total", [])),
                    "mean": sum(role_tokens.get("total", [])) / len(role_tokens.get("total", []))
                    if role_tokens.get("total")
                    else 0.0,
                },
                "cost_usd": {
                    "count": len(role_costs),
                    "total": sum(role_costs),
                    "mean": sum(role_costs) / len(role_costs) if role_costs else 0.0,
                },
            }

        alerts: List[Dict[str, Any]] = []
        baseline_cost = summary.get("baseline", {}).get("cost_usd", {}).get("mean", 0.0)
        candidate_cost = summary.get("candidate", {}).get("cost_usd", {}).get("mean", 0.0)
        if baseline_cost > 0 and candidate_cost > baseline_cost * self.alert_cost_ratio:
            alerts.append(
                {
                    "type": "cost_regression",
                    "baseline_cost_usd": baseline_cost,
                    "candidate_cost_usd": candidate_cost,
                    "ratio": candidate_cost / baseline_cost,
                    "threshold": self.alert_cost_ratio,
                }
            )

        return {
            "id": self.identifier(),
            "type": "llm_cost",
            "summary": summary,
            "alerts": alerts,
        }


class CompositeMonitor(Monitor):
    """Monitor that combines multiple monitors into one."""
    
    def __init__(self, monitors: Sequence[Monitor]) -> None:
        super().__init__()
        self._monitors = list(monitors)
    
    def identifier(self) -> str:
        names = [m.identifier() for m in self._monitors]
        return f"composite({','.join(names)})"
    
    def start(self, context: MonitorContext) -> None:
        super().start(context)
        for monitor in self._monitors:
            monitor.start(context)
    
    def record(self, record: MonitorRecord) -> None:
        for monitor in self._monitors:
            monitor.record(record)
    
    def finalize(self) -> Dict[str, Any]:
        results = {}
        all_alerts = []
        for monitor in self._monitors:
            monitor_result = monitor.finalize()
            monitor_id = monitor.identifier()
            results[monitor_id] = monitor_result
            alerts = monitor_result.get("alerts", [])
            for alert in alerts:
                alert["monitor"] = monitor_id
                all_alerts.append(alert)
        
        return {
            "id": self.identifier(),
            "type": "composite",
            "monitors": results,
            "alerts": all_alerts,
            "summary": {
                "total_monitors": len(self._monitors),
                "total_alerts": len(all_alerts),
            },
        }


def create_composite_monitor(monitors: Sequence[Monitor]) -> CompositeMonitor:
    """Create a composite monitor from a sequence of monitors."""
    return CompositeMonitor(monitors)


def resolve_monitors(specs: Sequence[str], *, sandbox_plugins: bool = False, composite: bool = False) -> List[Monitor]:
    """
    Instantiate monitors based on CLI-style specifications.
    
    Args:
        specs: List of monitor specifications (e.g., ["latency", "llm_cost:alert_ratio=1.5"])
        sandbox_plugins: Whether to sandbox plugin monitors
        composite: If True, return a single CompositeMonitor containing all monitors
    
    Returns:
        List of Monitor instances, or a single CompositeMonitor if composite=True
    """
    builtin_registry = {
        "latency": LatencyMonitor,
        "success_rate": SuccessRateMonitor,
        "trend": TrendMonitor,
        "fairness": FairnessGapMonitor,
        "fairness_gap": FairnessGapMonitor,
        "resource": ResourceUsageMonitor,
        "resource_usage": ResourceUsageMonitor,
        "llm_cost": LLMCostMonitor,
        "llm_cost_monitor": LLMCostMonitor,
        "performance": None,  # Lazy import to avoid circular dependency
        "profiler": None,  # Lazy import
        "safety": None,  # Lazy import for SafetyMonitor
        "toxicity": None,  # Lazy import for ToxicityMonitor
        "bias": None,  # Lazy import for BiasMonitor
        "pii": None,  # Lazy import for PIIMonitor
    }

    plugin_registry = monitor_plugins()

    monitors: List[Monitor] = []
    for spec in specs:
        name, params = _parse_monitor_spec(spec)
        factory = builtin_registry.get(name)
        
        # Handle lazy imports for performance profiler
        if factory is None and name in ("performance", "profiler"):
            try:
                from .profiling import PerformanceProfiler
                factory = PerformanceProfiler
            except ImportError:
                raise ValueError(f"Failed to import PerformanceProfiler for monitor '{name}'")
        
        # Handle lazy imports for safety monitors
        if factory is None and name in ("safety", "toxicity", "bias", "pii"):
            try:
                from .safety_monitors import (
                    SafetyMonitor,
                    ToxicityMonitor,
                    BiasMonitor,
                    PIIMonitor,
                )
                if name == "safety":
                    factory = SafetyMonitor
                elif name == "toxicity":
                    factory = ToxicityMonitor
                elif name == "bias":
                    factory = BiasMonitor
                elif name == "pii":
                    factory = PIIMonitor
            except ImportError:
                raise ValueError(f"Failed to import safety monitors for '{name}'")
        
        if factory is not None:
            monitors.append(factory(**params))
            continue

        definition = plugin_registry.get(name)
        if definition is None:
            available = sorted(set(list(builtin_registry.keys()) + list(plugin_registry.keys())))
            raise ValueError(f"Unknown monitor '{name}'. Available: {available}")

        monitor = _instantiate_plugin_monitor(definition, params, sandbox_plugins)
        monitors.append(monitor)
    
    if composite and monitors:
        return [CompositeMonitor(monitors)]
    
    return monitors


def _parse_monitor_spec(spec: str) -> tuple[str, Dict[str, Any]]:
    if ":" not in spec:
        return spec.lower(), {}

    name, param_str = spec.split(":", 1)
    params: Dict[str, Any] = {}
    for piece in param_str.split(","):
        if "=" not in piece:
            raise ValueError(f"Invalid monitor parameter '{piece}' in '{spec}'")
        key, value = piece.split("=", 1)
        params[key.strip()] = _convert_value(value.strip())
    return name.lower(), params


def _convert_value(value: str) -> Any:
    for cast in (int, float):
        try:
            return cast(value)
        except ValueError:
            continue
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    return value


def _instantiate_plugin_monitor(
    definition: PluginDefinition,
    params: Dict[str, Any],
    sandbox_plugins: bool,
) -> Monitor:
    should_sandbox = sandbox_plugins or definition.metadata.sandbox
    factory = definition.factory

    if should_sandbox:
        return SandboxedMonitorProxy(definition, params)

    instance = factory(**params)
    if not isinstance(instance, Monitor):
        raise TypeError(
            f"Monitor plugin '{definition.name}' must return a Monitor instance, got {type(instance)!r}."
        )
    return instance


class SandboxedMonitorProxy(Monitor):
    """Proxy that isolates plugin monitor logic in a separate process."""

    def __init__(self, definition: PluginDefinition, params: Dict[str, Any]) -> None:
        super().__init__()
        self._definition = definition
        self._ctx = mp.get_context("spawn")
        self._requests: mp.Queue = self._ctx.Queue()
        self._responses: mp.Queue = self._ctx.Queue()
        self._process = self._ctx.Process(
            target=_sandboxed_monitor_worker,
            args=(definition.factory, params, self._requests, self._responses),
            daemon=True,
        )
        self._process.start()
        status, payload = self._responses.get()
        if status != "ok":
            self._cleanup(force=True)
            raise RuntimeError(
                f"Failed to initialise monitor plugin '{definition.name}': {payload}"
            )
        self._identifier_override = payload or definition.metadata.name or definition.name

    def identifier(self) -> str:
        return self._identifier_override

    def start(self, context: MonitorContext) -> None:
        super().start(context)
        self._send("start", context)

    def record(self, record: MonitorRecord) -> None:
        self._send("record", record)

    def finalize(self) -> Dict[str, Any]:
        status, payload = self._send("finalize", None, expect_response=True)
        if status != "ok":
            raise RuntimeError(f"Monitor plugin '{self._definition.name}' failed to finalize: {payload}")
        self._cleanup()
        return payload or {}

    def _send(self, command: str, payload: Any, *, expect_response: bool = False) -> Any:
        self._requests.put((command, payload))
        status, response = self._responses.get()
        if status != "ok":
            self._cleanup(force=True)
            raise RuntimeError(
                f"Monitor plugin '{self._definition.name}' raised an error during '{command}': {response}"
            )
        if expect_response:
            return status, response
        return None

    def _cleanup(self, force: bool = False) -> None:
        if getattr(self, "_process", None) is None:
            return

        if self._process.is_alive() and not force:
            self._requests.put(("stop", None))
            try:
                self._responses.get(timeout=0.5)
            except queue.Empty:  # pragma: no cover - defensive
                pass

        if self._process.is_alive():
            self._process.join(timeout=0.5)
        if self._process.is_alive():  # pragma: no cover - defensive
            self._process.kill()
        self._process = None

    def __del__(self) -> None:  # pragma: no cover - best effort cleanup
        try:
            self._cleanup()
        except Exception:
            return


def _sandboxed_monitor_worker(
    factory: Callable[..., Any],
    params: Dict[str, Any],
    requests: mp.Queue,
    responses: mp.Queue,
) -> None:
    try:
        monitor_obj = factory(**params)
        if not isinstance(monitor_obj, Monitor):
            raise TypeError(
                f"Plugin factory returned {type(monitor_obj)!r}, expected Monitor."
            )
        identifier = monitor_obj.identifier()
    except Exception as exc:  # pragma: no cover - defensive
        responses.put(("error", repr(exc)))
        return

    responses.put(("ok", identifier))

    while True:
        command, payload = requests.get()
        try:
            if command == "start":
                monitor_obj.start(payload)
                responses.put(("ok", None))
            elif command == "record":
                monitor_obj.record(payload)
                responses.put(("ok", None))
            elif command == "finalize":
                result = monitor_obj.finalize()
                responses.put(("ok", result))
            elif command == "stop":
                responses.put(("ok", None))
                break
            else:  # pragma: no cover - defensive
                responses.put(("error", f"Unknown command '{command}'"))
        except Exception as exc:  # pragma: no cover - defensive
            responses.put(("error", repr(exc)))

