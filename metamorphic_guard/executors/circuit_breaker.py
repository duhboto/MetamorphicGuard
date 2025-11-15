"""
Circuit breaker pattern for LLM executors to prevent cascading failures.
"""

from __future__ import annotations

import enum
import threading
import time
from typing import Dict, Optional


class CircuitState(enum.Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, allowing requests
    OPEN = "open"  # Service is failing, blocking requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker to prevent cascading failures in LLM API calls.

    The circuit breaker monitors failures and opens after a threshold,
    blocking requests until a recovery timeout expires. It then transitions
    to half-open to test if the service recovered.

    Attributes:
        failure_threshold: Number of consecutive failures before opening
        success_threshold: Number of successes needed in half-open to close
        timeout_seconds: Seconds to wait in open state before half-open
        failure_timeout_seconds: How long failures remain in count (sliding window)
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout_seconds: float = 60.0,
        failure_timeout_seconds: Optional[float] = None,
    ) -> None:
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Consecutive failures before opening circuit
            success_threshold: Successes needed in half-open to close
            timeout_seconds: Time to wait in open state before half-open
            failure_timeout_seconds: Window for counting failures (None = infinite)
        """
        self.failure_threshold = max(1, failure_threshold)
        self.success_threshold = max(1, success_threshold)
        self.timeout_seconds = max(1.0, timeout_seconds)
        self.failure_timeout_seconds = failure_timeout_seconds

        self._state = CircuitState.CLOSED
        self._lock = threading.Lock()
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._last_failure_time: Optional[float] = None
        self._state_transition_time: float = time.monotonic()
        self._failure_history: list[float] = []  # For sliding window

    def call(self, func, *args, **kwargs):
        """
        Execute a function call through the circuit breaker.

        Raises:
            CircuitBreakerOpenError: If circuit is open and timeout hasn't expired
        """
        if not self.allow_request():
            raise CircuitBreakerOpenError(
                f"Circuit breaker is {self._state.value}. "
                f"Next attempt allowed after {self._next_attempt_time():.1f}s"
            )

        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as exc:
            self.record_failure()
            raise exc

    def allow_request(self) -> bool:
        """
        Check if a request should be allowed through the circuit breaker.

        Returns:
            True if request should be allowed, False otherwise
        """
        with self._lock:
            now = time.monotonic()

            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                elapsed = now - self._state_transition_time
                if elapsed >= self.timeout_seconds:
                    # Transition to half-open
                    self._state = CircuitState.HALF_OPEN
                    self._state_transition_time = now
                    self._consecutive_successes = 0
                    return True
                return False

            # HALF_OPEN state - allow test requests
            return True

    def record_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._consecutive_successes += 1
                if self._consecutive_successes >= self.success_threshold:
                    # Close circuit after enough successes
                    self._state = CircuitState.CLOSED
                    self._consecutive_failures = 0
                    self._consecutive_successes = 0
                    self._failure_history.clear()
                    self._state_transition_time = time.monotonic()
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._consecutive_failures = 0
                self._failure_history.clear()

    def record_failure(self) -> None:
        """Record a failed call."""
        with self._lock:
            now = time.monotonic()
            self._last_failure_time = now

            if self.failure_timeout_seconds:
                # Sliding window: remove old failures
                cutoff = now - self.failure_timeout_seconds
                self._failure_history = [f for f in self._failure_history if f > cutoff]
                self._failure_history.append(now)
                failure_count = len(self._failure_history)
            else:
                # Consecutive failures
                self._consecutive_failures += 1
                failure_count = self._consecutive_failures

            if self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open opens the circuit immediately
                self._state = CircuitState.OPEN
                self._state_transition_time = now
                self._consecutive_successes = 0
                if self.failure_timeout_seconds:
                    self._failure_history.clear()
                    self._failure_history.append(now)
                else:
                    self._consecutive_failures = 1
            elif self._state == CircuitState.CLOSED:
                if failure_count >= self.failure_threshold:
                    # Open circuit after threshold
                    self._state = CircuitState.OPEN
                    self._state_transition_time = now

    def _next_attempt_time(self) -> float:
        """Get the next time a request will be allowed (if circuit is open)."""
        if self._state == CircuitState.OPEN:
            return self._state_transition_time + self.timeout_seconds
        return 0.0

    def get_state(self) -> CircuitState:
        """Get current circuit state."""
        with self._lock:
            return self._state

    def get_stats(self) -> Dict[str, object]:
        """Get circuit breaker statistics."""
        with self._lock:
            return {
                "state": self._state.value,
                "consecutive_failures": self._consecutive_failures,
                "consecutive_successes": self._consecutive_successes,
                "failure_count": (
                    len(self._failure_history)
                    if self.failure_timeout_seconds
                    else self._consecutive_failures
                ),
                "last_failure_time": self._last_failure_time,
                "state_since": self._state_transition_time,
                "next_attempt_time": self._next_attempt_time(),
            }

    def reset(self) -> None:
        """Manually reset the circuit breaker to closed state."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._consecutive_failures = 0
            self._consecutive_successes = 0
            self._failure_history.clear()
            self._state_transition_time = time.monotonic()


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and blocking requests."""

    pass



