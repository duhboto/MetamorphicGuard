"""
Executor plugins for different execution backends (local, docker, LLM, etc.).
"""

from __future__ import annotations

import random
import time
from typing import Any, Dict, Optional, Sequence

from .circuit_breaker import CircuitBreaker, CircuitBreakerOpenError

__all__ = ["Executor", "LLMExecutor"]


class Executor:
    """Base class for execution backends."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}

    def execute(
        self,
        file_path: str,
        func_name: str,
        args: tuple,
        timeout_s: float = 2.0,
        mem_mb: int = 512,
    ) -> Dict[str, Any]:
        """
        Execute the requested function.

        Returns a dictionary with execution metadata:
        - success: bool
        - duration_ms: float
        - stdout: str
        - stderr: str
        - result: Any (on success)
        - error: str (on failure)
        - error_type: str (optional)
        - error_code: str (optional)
        """
        raise NotImplementedError


class LLMExecutor(Executor):
    """Base class for LLM API executors."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config)
        cfg = config or {}
        self.provider = cfg.get("provider", "openai")
        self.model = cfg.get("model", "gpt-3.5-turbo")
        self.max_tokens = cfg.get("max_tokens", 512)
        self.temperature = cfg.get("temperature", 0.0)
        self.seed = cfg.get("seed")
        self.system_prompt = cfg.get("system_prompt")
        self.max_retries = int(cfg.get("max_retries", 3))
        self.retry_backoff_base = float(cfg.get("retry_backoff_base", 0.5))
        self.retry_backoff_cap = float(cfg.get("retry_backoff_cap", 8.0))
        self.retry_jitter = float(cfg.get("retry_jitter", 0.1))
        retry_statuses = cfg.get("retry_statuses", (429, 500, 502, 503, 504))
        if isinstance(retry_statuses, Sequence):
            self.retry_statuses = {int(code) for code in retry_statuses}
        else:
            self.retry_statuses = {429, 500, 502, 503, 504}
        retry_exceptions = cfg.get(
            "retry_exceptions",
            ("RateLimitError", "ServiceUnavailableError", "Timeout", "APIError"),
        )
        self.retry_exception_tokens = tuple(str(name).lower() for name in retry_exceptions)

        # Initialize circuit breaker (disabled by default, enabled via config)
        enable_circuit_breaker = cfg.get("enable_circuit_breaker", True)
        if enable_circuit_breaker:
            circuit_breaker_config = cfg.get("circuit_breaker", {})
            self.circuit_breaker = CircuitBreaker(
                failure_threshold=int(circuit_breaker_config.get("failure_threshold", 5)),
                success_threshold=int(circuit_breaker_config.get("success_threshold", 2)),
                timeout_seconds=float(circuit_breaker_config.get("timeout_seconds", 60.0)),
                failure_timeout_seconds=circuit_breaker_config.get("failure_timeout_seconds"),
            )
        else:
            self.circuit_breaker = None

    def execute(
        self,
        file_path: str,
        func_name: str,
        args: tuple,
        timeout_s: float = 2.0,
        mem_mb: int = 512,
    ) -> Dict[str, Any]:
        """
        Execute an LLM call.

        For LLM executors, file_path is the prompt template path or prompt string,
        func_name is the model identifier, and args contain the prompt variables.
        """
        raise NotImplementedError

    def _call_llm(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Make an LLM API call and return structured result.

        Returns:
            {
                "content": str,
                "tokens_prompt": int,
                "tokens_completion": int,
                "tokens_total": int,
                "cost_usd": float,
                "finish_reason": str,
            }
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Retry helpers shared by concrete executors

    def _should_retry(self, exc: Exception, attempt: int) -> bool:
        """Determine whether another retry should be attempted for the given exception."""
        if self.max_retries <= 0 or attempt >= self.max_retries:
            return False

        status_code = getattr(exc, "status_code", None)
        if status_code is not None and status_code in self.retry_statuses:
            return True
        if status_code is not None:
            try:
                status_int = int(status_code)
            except (TypeError, ValueError):
                status_int = None
            if status_int is not None and 400 <= status_int < 500:
                # Explicitly avoid retrying non-429 client errors
                return False

        exc_name = type(exc).__name__.lower()
        if any(token in exc_name for token in self.retry_exception_tokens):
            return True

        message = str(exc).lower()
        if any(token in message for token in self.retry_exception_tokens):
            return True

        return False

    def _sleep_with_backoff(self, attempt: int, retry_after: Optional[float] = None) -> None:
        """
        Sleep with exponential backoff, optionally respecting Retry-After header.
        
        Args:
            attempt: Current retry attempt number (0-indexed)
            retry_after: Optional seconds to wait from Retry-After header
        """
        if retry_after is not None and retry_after > 0:
            # Respect Retry-After header if provided (common in rate limit responses)
            delay = retry_after
            # Add small jitter to avoid thundering herd
            if self.retry_jitter > 0:
                delay += random.uniform(0, min(self.retry_jitter, delay * 0.1))
        elif self.retry_backoff_base <= 0:
            return
        else:
            # Exponential backoff: base * 2^attempt
            delay = self.retry_backoff_base * (2 ** attempt)
            if self.retry_backoff_cap > 0:
                delay = min(delay, self.retry_backoff_cap)
            if self.retry_jitter > 0:
                delay += random.uniform(0, self.retry_jitter)
        
        time.sleep(max(delay, 0.0))
    
    def _extract_retry_after(self, exc: Exception) -> Optional[float]:
        """
        Extract Retry-After value from exception (if available).
        
        Many API clients include Retry-After in response headers for rate limits.
        This method attempts to extract it from the exception or response object.
        
        Args:
            exc: The exception that occurred
            
        Returns:
            Seconds to wait, or None if not available
        """
        # Check if exception has response attribute (common in HTTP clients)
        response = getattr(exc, "response", None)
        if response is not None:
            # Try to get Retry-After header
            headers = getattr(response, "headers", None)
            if headers is not None:
                retry_after = headers.get("Retry-After") or headers.get("retry-after")
                if retry_after:
                    try:
                        # Retry-After can be seconds (int) or HTTP date
                        return float(retry_after)
                    except (ValueError, TypeError):
                        pass
        
        # Check if exception has retry_after attribute directly
        retry_after = getattr(exc, "retry_after", None)
        if retry_after is not None:
            try:
                return float(retry_after)
            except (ValueError, TypeError):
                pass
        
        return None

    def _attach_retry_metadata(self, payload: Dict[str, Any], attempts: int) -> Dict[str, Any]:
        payload["retries"] = max(0, attempts)
        payload.setdefault("retry_limit", self.max_retries)
        return payload

