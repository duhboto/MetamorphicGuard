from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional, TextIO

LOG_ENV_VAR = "METAMORPHIC_GUARD_LOG_JSON"
PROM_ENV_VAR = "METAMORPHIC_GUARD_PROMETHEUS"

_LOG_ENABLED = os.getenv(LOG_ENV_VAR) == "1"
_LOG_STREAM: TextIO = sys.stdout
_LOG_FILE_HANDLE: Optional[TextIO] = None
_LOG_CONTEXT: Dict[str, Any] = {}
_LOG_LOCK = threading.Lock()

_PROMETHEUS_IMPORTED = False
_PROM_IMPORT_ERROR: Exception | None = None
_PROM_REGISTRY = None
_PROM_COUNTERS: Dict[str, Any] = {}
_PROM_GAUGES: Dict[str, Any] = {}
_PROM_SERVER = None
_METRICS_ENABLED = os.getenv(PROM_ENV_VAR) == "1"

try:  # pragma: no cover - optional dependency import
    from prometheus_client import CollectorRegistry, Counter, Gauge, start_http_server  # type: ignore

    _PROMETHEUS_IMPORTED = True
except ImportError as exc:  # pragma: no cover - optional dependency
    CollectorRegistry = None  # type: ignore
    Counter = None  # type: ignore
    start_http_server = None  # type: ignore
    _PROM_IMPORT_ERROR = exc

if _METRICS_ENABLED and _PROMETHEUS_IMPORTED:
    _PROM_REGISTRY = CollectorRegistry()
    _PROM_COUNTERS = {
        "cases_total": Counter(  # type: ignore[call-arg]
            "metamorphic_cases_total",
            "Total evaluation cases processed",
            ["role", "status"],
            registry=_PROM_REGISTRY,
        ),
        "queue_dispatched": Counter(  # type: ignore[call-arg]
            "metamorphic_queue_cases_dispatched_total",
            "Total evaluation cases dispatched to the queue",
            registry=_PROM_REGISTRY,
        ),
        "queue_completed": Counter(  # type: ignore[call-arg]
            "metamorphic_queue_cases_completed_total",
            "Total evaluation cases completed by workers",
            registry=_PROM_REGISTRY,
        ),
        "queue_requeued": Counter(  # type: ignore[call-arg]
            "metamorphic_queue_cases_requeued_total",
            "Total evaluation cases requeued after lease expiry or heartbeat timeout",
            registry=_PROM_REGISTRY,
        ),
        "llm_retries": Counter(  # type: ignore[call-arg]
            "metamorphic_llm_retries_total",
            "Total retry attempts performed by LLM executors",
            ["provider", "role"],
            registry=_PROM_REGISTRY,
        ),
    }
    _PROM_GAUGES = {
        "queue_pending": Gauge(  # type: ignore[call-arg]
            "metamorphic_queue_pending_tasks",
            "Number of queue tasks pending dispatch",
            registry=_PROM_REGISTRY,
        ),
        "queue_inflight": Gauge(  # type: ignore[call-arg]
            "metamorphic_queue_inflight_cases",
            "Number of evaluation cases currently in flight",
            registry=_PROM_REGISTRY,
        ),
        "queue_workers": Gauge(  # type: ignore[call-arg]
            "metamorphic_queue_active_workers",
            "Number of active workers recently seen via heartbeats",
            registry=_PROM_REGISTRY,
        ),
    }
else:
    _METRICS_ENABLED = False


def configure_logging(
    enabled: Optional[bool] = None,
    *,
    stream: Optional[TextIO] = None,
    context: Optional[Dict[str, Any]] = None,
    path: Optional[str | Path] = None,
) -> None:
    """Configure structured logging behaviour at runtime."""

    global _LOG_ENABLED, _LOG_STREAM, _LOG_FILE_HANDLE
    if enabled is not None:
        _LOG_ENABLED = bool(enabled)
    if stream is not None:
        _LOG_STREAM = stream
    if path is not None:
        if _LOG_FILE_HANDLE is not None and not _LOG_FILE_HANDLE.closed:
            try:
                _LOG_FILE_HANDLE.flush()
            finally:
                _LOG_FILE_HANDLE.close()
        log_path = Path(path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        _LOG_FILE_HANDLE = log_path.open("a", encoding="utf-8")
        _LOG_STREAM = _LOG_FILE_HANDLE
    if context:
        add_log_context(**context)


def add_log_context(**kwargs: Any) -> None:
    """Attach key/value pairs that will be merged into every log event."""

    with _LOG_LOCK:
        _LOG_CONTEXT.update({k: v for k, v in kwargs.items() if v is not None})


def clear_log_context() -> None:
    """Clear all persistent log context."""

    with _LOG_LOCK:
        _LOG_CONTEXT.clear()


def close_logging() -> None:
    global _LOG_FILE_HANDLE
    if _LOG_FILE_HANDLE is not None and not _LOG_FILE_HANDLE.closed:
        try:
            _LOG_FILE_HANDLE.flush()
        finally:
            _LOG_FILE_HANDLE.close()
    _LOG_FILE_HANDLE = None


def log_event(event: str, **payload: Any) -> None:
    if not _LOG_ENABLED:
        return

    with _LOG_LOCK:
        record: Dict[str, Any] = {
            "timestamp": time.time(),
            "event": event,
        }
        if _LOG_CONTEXT:
            record.update(_LOG_CONTEXT)
        record.update(payload)

    try:
        _LOG_STREAM.write(json.dumps(record, default=_serialize) + "\n")
    except (OSError, ValueError, TypeError) as exc:  # pragma: no cover - best-effort logging
        sys.stderr.write(f"[metamorphic-guard] Failed to emit log event '{event}': {exc}\n")
        return
    _LOG_STREAM.flush()


def configure_metrics(
    enabled: Optional[bool] = None,
    *,
    port: Optional[int] = None,
    host: str = "0.0.0.0",
) -> None:
    """Enable or disable Prometheus counters and optionally expose an HTTP endpoint."""

    global _METRICS_ENABLED, _PROM_REGISTRY, _PROM_COUNTERS, _PROM_SERVER

    if enabled is not None:
        _METRICS_ENABLED = bool(enabled)

    if not _METRICS_ENABLED:
        return

    if not _PROMETHEUS_IMPORTED or CollectorRegistry is None or Counter is None:
        raise RuntimeError(
            "Prometheus support requires the 'prometheus_client' package."
        )

    if _PROM_REGISTRY is None:
        _PROM_REGISTRY = CollectorRegistry()
        _PROM_COUNTERS = {
            "cases_total": Counter(  # type: ignore[call-arg]
                "metamorphic_cases_total",
                "Total evaluation cases processed",
                ["role", "status"],
                registry=_PROM_REGISTRY,
            ),
            "queue_dispatched": Counter(  # type: ignore[call-arg]
                "metamorphic_queue_cases_dispatched_total",
                "Total evaluation cases dispatched to the queue",
                registry=_PROM_REGISTRY,
            ),
            "queue_completed": Counter(  # type: ignore[call-arg]
                "metamorphic_queue_cases_completed_total",
                "Total evaluation cases completed by workers",
                registry=_PROM_REGISTRY,
            ),
            "queue_requeued": Counter(  # type: ignore[call-arg]
                "metamorphic_queue_cases_requeued_total",
                "Total evaluation cases requeued after lease expiry or heartbeat timeout",
                registry=_PROM_REGISTRY,
            ),
        }
        _PROM_GAUGES = {
            "queue_pending": Gauge(  # type: ignore[call-arg]
                "metamorphic_queue_pending_tasks",
                "Number of queue tasks pending dispatch",
                registry=_PROM_REGISTRY,
            ),
            "queue_inflight": Gauge(  # type: ignore[call-arg]
                "metamorphic_queue_inflight_cases",
                "Number of evaluation cases currently in flight",
                registry=_PROM_REGISTRY,
            ),
            "queue_workers": Gauge(  # type: ignore[call-arg]
                "metamorphic_queue_active_workers",
                "Number of active workers recently seen via heartbeats",
                registry=_PROM_REGISTRY,
            ),
        }

    if port is not None and start_http_server is not None and _PROM_SERVER is None:
        _PROM_SERVER = start_http_server(port, addr=host, registry=_PROM_REGISTRY)  # type: ignore[arg-type]


def metrics_enabled() -> bool:
    return _METRICS_ENABLED and (_PROM_COUNTERS != {} or _PROM_GAUGES != {})


def increment_metric(role: str, status: str) -> None:
    if not metrics_enabled():
        return
    counter = _PROM_COUNTERS.get("cases_total")
    if counter is None:
        return
    counter.labels(role=role, status=status).inc()


def prometheus_registry():
    return _PROM_REGISTRY


def _serialize(value: Any) -> Any:
    if isinstance(value, (set, tuple)):
        return list(value)
    return value


def increment_queue_dispatched(count: int = 1) -> None:
    if not metrics_enabled() or count <= 0:
        return
    counter = _PROM_COUNTERS.get("queue_dispatched")
    if counter is not None:
        counter.inc(count)


def increment_queue_completed(count: int = 1) -> None:
    if not metrics_enabled() or count <= 0:
        return
    counter = _PROM_COUNTERS.get("queue_completed")
    if counter is not None:
        counter.inc(count)


def increment_queue_requeued(count: int = 1) -> None:
    if not metrics_enabled() or count <= 0:
        return
    counter = _PROM_COUNTERS.get("queue_requeued")
    if counter is not None:
        counter.inc(count)


def increment_llm_retries(provider: str, role: str, count: int) -> None:
    if not metrics_enabled() or count <= 0:
        return
    counter = _PROM_COUNTERS.get("llm_retries")
    if counter is None:
        return
    counter.labels(provider=provider, role=role).inc(count)


def observe_queue_pending_tasks(count: int) -> None:
    if not metrics_enabled():
        return
    gauge = _PROM_GAUGES.get("queue_pending")
    if gauge is not None:
        gauge.set(count)


def observe_queue_inflight(count: int) -> None:
    if not metrics_enabled():
        return
    gauge = _PROM_GAUGES.get("queue_inflight")
    if gauge is not None:
        gauge.set(count)


def observe_worker_count(count: int) -> None:
    if not metrics_enabled():
        return
    gauge = _PROM_GAUGES.get("queue_workers")
    if gauge is not None:
        gauge.set(count)

