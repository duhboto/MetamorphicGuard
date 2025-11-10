from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, Optional

_PROM_AVAILABLE = False
_PROM_REGISTRY = None
_METRICS: Dict[str, Any] = {}

if os.getenv("METAMORPHIC_GUARD_PROMETHEUS") == "1":
    try:
        from prometheus_client import CollectorRegistry, Counter  # type: ignore

        _PROM_AVAILABLE = True
        _PROM_REGISTRY = CollectorRegistry()
        _METRICS = {
            "cases_total": Counter(
                "metamorphic_cases_total",
                "Total evaluation cases processed",
                ["role", "status"],
                registry=_PROM_REGISTRY,
            ),
        }
    except Exception:  # pragma: no cover - optional dependency
        _PROM_AVAILABLE = False
        _PROM_REGISTRY = None
        _METRICS = {}


def log_enabled() -> bool:
    return os.getenv("METAMORPHIC_GUARD_LOG_JSON") == "1"


def log_event(event: str, **payload: Any) -> None:
    if not log_enabled():
        return
    record = {
        "event": event,
        "payload": payload,
    }
    sys.stdout.write(json.dumps(record, default=_serialize) + "\n")
    sys.stdout.flush()


def increment_metric(role: str, status: str) -> None:
    if not _PROM_AVAILABLE or "cases_total" not in _METRICS:
        return
    _METRICS["cases_total"].labels(role=role, status=status).inc()


def prometheus_registry():
    return _PROM_REGISTRY


def _serialize(value: Any) -> Any:
    if isinstance(value, (set, tuple)):
        return list(value)
    return value

