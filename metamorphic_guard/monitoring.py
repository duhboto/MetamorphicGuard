from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Sequence, List

from .plugins import monitor_plugins


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


def resolve_monitors(specs: Sequence[str]) -> List[Monitor]:
    """Instantiate monitors based on CLI-style specifications."""

    registry = {
        "latency": LatencyMonitor,
        "success_rate": SuccessRateMonitor,
        "trend": TrendMonitor,
    }
    registry.update(monitor_plugins())

    monitors: List[Monitor] = []
    for spec in specs:
        name, params = _parse_monitor_spec(spec)
        factory = registry.get(name)
        if factory is None:
            raise ValueError(f"Unknown monitor '{name}'. Available: {list(registry.keys())}")
        monitor = factory(**params)
        monitors.append(monitor)
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

