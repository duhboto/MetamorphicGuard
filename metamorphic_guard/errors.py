"""
Domain-specific exception types for Metamorphic Guard.
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from datetime import datetime


@dataclass
class ErrorContext:
    """Structured context for transport-safe error reporting."""

    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    error_code: Optional[str] = None
    stack_trace: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Add timestamp if not present."""
        if "timestamp" not in self.metadata:
            self.metadata["timestamp"] = datetime.utcnow().isoformat()

    def as_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        payload: Dict[str, Any] = {"message": self.message}
        if self.error_code:
            payload["error_code"] = self.error_code
        if self.details:
            payload["details"] = self.details
        if self.stack_trace:
            payload["stack_trace"] = self.stack_trace
        if self.metadata:
            payload["metadata"] = self.metadata
        return payload


class MetamorphicGuardError(RuntimeError):
    """Base exception for all Metamorphic Guard errors."""

    def __init__(
        self,
        message: str,
        *,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        original: Exception | None = None,
        include_traceback: bool = False,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        self.original = original
        self.include_traceback = include_traceback

    def to_context(self) -> ErrorContext:
        """Convert to ErrorContext for structured error reporting."""
        ctx = dict(self.details)
        if self.original is not None:
            ctx["cause"] = self.original.__class__.__name__
            ctx["cause_message"] = str(self.original)
        
        stack_trace: Optional[str] = None
        if self.include_traceback:
            # Truncate traceback to last 10 lines for security
            tb_lines = traceback.format_exc().split('\n')
            stack_trace = '\n'.join(tb_lines[-10:])
        
        return ErrorContext(
            message=str(self),
            error_code=self.error_code,
            details=ctx,
            stack_trace=stack_trace,
        )


class SandboxError(MetamorphicGuardError):
    """Raised when sandbox execution fails."""

    ERROR_CODES = {
        "SANDBOX_TIMEOUT": "Test case exceeded timeout limit",
        "SANDBOX_MEMORY": "Test case exceeded memory limit",
        "SANDBOX_PROCESS_EXIT": "Test process exited unexpectedly",
        "SANDBOX_IMPORT_ERROR": "Failed to import required modules",
        "SANDBOX_NETWORK_DENIED": "Network access denied in sandbox",
    }


class ExecutorError(MetamorphicGuardError):
    """Raised when executor fails."""

    ERROR_CODES = {
        "EXECUTOR_AUTH_FAILED": "Authentication failed",
        "EXECUTOR_RATE_LIMIT": "Rate limit exceeded",
        "EXECUTOR_INVALID_REQUEST": "Invalid request to executor",
        "EXECUTOR_SERVER_ERROR": "Executor server error",
        "EXECUTOR_TIMEOUT": "Executor request timed out",
    }


class PolicyError(MetamorphicGuardError):
    """Raised when policy parsing or validation fails."""

    ERROR_CODES = {
        "POLICY_LOAD_ERROR": "Failed to load policy file",
        "POLICY_PARSE_ERROR": "Failed to parse policy",
        "POLICY_VALIDATION_ERROR": "Policy validation failed",
    }


class HarnessError(MetamorphicGuardError):
    """Raised when harness execution fails."""

    ERROR_CODES = {
        "HARNESS_INVALID_SPEC": "Invalid task specification",
        "HARNESS_EXECUTION_ERROR": "Error during test execution",
        "HARNESS_STATISTICS_ERROR": "Error computing statistics",
    }


class QueueSerializationError(MetamorphicGuardError):
    """Raised when queue payloads cannot be encoded or decoded."""

    def __init__(
        self,
        message: str,
        *,
        details: Optional[Dict[str, Any]] = None,
        original: Exception | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code="QUEUE_SERIALIZATION_ERROR",
            details=details or {},
            original=original,
        )


__all__ = [
    "QueueSerializationError",
    "ErrorContext",
    "MetamorphicGuardError",
    "SandboxError",
    "ExecutorError",
    "PolicyError",
    "HarnessError",
]

