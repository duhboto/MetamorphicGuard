"""Shim module exposing logging helpers for backwards compatibility."""

from __future__ import annotations

from typing import Any

from .observability import (
    add_log_context,
    close_logging,
    configure_logging,
    log_event,
)

__all__ = [
    "add_log_context",
    "close_logging",
    "configure_logging",
    "log_event",
]


def emit(event: str, **payload: Any) -> None:
    """Alias for log_event for compatibility with legacy code."""

    log_event(event, **payload)
