"""
Domain-specific exception types for Metamorphic Guard.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ErrorContext:
    """Structured context for transport-safe error reporting."""

    message: str
    details: Dict[str, Any]

    def as_dict(self) -> Dict[str, Any]:
        payload = {"message": self.message}
        if self.details:
            payload["details"] = self.details
        return payload


class QueueSerializationError(RuntimeError):
    """Raised when queue payloads cannot be encoded or decoded."""

    def __init__(
        self,
        message: str,
        *,
        details: Optional[Dict[str, Any]] = None,
        original: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.details = details or {}
        self.original = original

    def to_context(self) -> ErrorContext:
        ctx = dict(self.details)
        if self.original is not None:
            ctx["cause"] = self.original.__class__.__name__
        return ErrorContext(str(self), ctx)


__all__ = ["QueueSerializationError", "ErrorContext"]

