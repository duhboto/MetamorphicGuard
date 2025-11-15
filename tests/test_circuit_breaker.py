"""
Comprehensive tests for circuit breaker functionality.

Tests state transitions, failure thresholds, sliding windows, and recovery.
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from metamorphic_guard.executors.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
)


class TestCircuitBreakerStateTransitions:
    """Test circuit breaker state transitions."""

    def test_initial_state_closed(self):
        """Test that circuit breaker starts in CLOSED state."""
        cb = CircuitBreaker()
        assert cb.get_state() == CircuitState.CLOSED
        assert cb.allow_request() is True

    def test_closed_to_open_on_failures(self):
        """Test transition from CLOSED to OPEN after failure threshold."""
        cb = CircuitBreaker(failure_threshold=3, timeout_seconds=1.0)
        
        # Record failures up to threshold
        for _ in range(2):
            cb.record_failure()
            assert cb.get_state() == CircuitState.CLOSED
        
        # Third failure should open circuit
        cb.record_failure()
        assert cb.get_state() == CircuitState.OPEN
        assert cb.allow_request() is False

    def test_open_to_half_open_after_timeout(self):
        """Test transition from OPEN to HALF_OPEN after timeout."""
        cb = CircuitBreaker(failure_threshold=2, timeout_seconds=1.0)
        
        # Open circuit
        cb.record_failure()
        cb.record_failure()
        assert cb.get_state() == CircuitState.OPEN
        
        # Manually advance time by patching time.monotonic
        import time as time_module
        original_monotonic = time_module.monotonic
        start_time = original_monotonic()
        
        def mock_monotonic():
            return start_time + 1.1  # Past timeout
        
        with patch.object(time_module, 'monotonic', side_effect=mock_monotonic):
            # Should transition to HALF_OPEN when allow_request is called
            allowed = cb.allow_request()
            assert allowed is True
            # State transition happens inside allow_request
            assert cb.get_state() == CircuitState.HALF_OPEN

    def test_half_open_to_closed_on_success(self):
        """Test transition from HALF_OPEN to CLOSED after success threshold."""
        cb = CircuitBreaker(
            failure_threshold=2,
            success_threshold=2,
            timeout_seconds=1.0,
        )
        
        # Open circuit
        cb.record_failure()
        cb.record_failure()
        assert cb.get_state() == CircuitState.OPEN
        
        # Manually advance time to trigger HALF_OPEN
        import time as time_module
        start_time = time_module.monotonic()
        
        def mock_monotonic():
            return start_time + 1.1  # Past timeout
        
        with patch.object(time_module, 'monotonic', side_effect=mock_monotonic):
            # allow_request triggers transition to HALF_OPEN
            allowed = cb.allow_request()
            assert allowed is True
            # Check state after allow_request
            state_after_allow = cb.get_state()
            assert state_after_allow == CircuitState.HALF_OPEN
        
        # Record one success (not enough)
        cb.record_success()
        assert cb.get_state() == CircuitState.HALF_OPEN
        
        # Second success should close circuit
        cb.record_success()
        assert cb.get_state() == CircuitState.CLOSED

    def test_half_open_to_open_on_failure(self):
        """Test transition from HALF_OPEN to OPEN on any failure."""
        cb = CircuitBreaker(
            failure_threshold=2,
            success_threshold=2,
            timeout_seconds=1.0,
        )
        
        # Open circuit
        cb.record_failure()
        cb.record_failure()
        
        # Manually advance time to trigger HALF_OPEN
        import time as time_module
        start_time = time_module.monotonic()
        
        def mock_monotonic():
            return start_time + 1.1  # Past timeout
        
        with patch.object(time_module, 'monotonic', side_effect=mock_monotonic):
            # allow_request triggers transition to HALF_OPEN
            allowed = cb.allow_request()
            assert allowed is True
            # Verify we're in HALF_OPEN
            assert cb.get_state() == CircuitState.HALF_OPEN
        
        # Any failure in HALF_OPEN should immediately open circuit
        cb.record_failure()
        assert cb.get_state() == CircuitState.OPEN
        assert cb.allow_request() is False


class TestCircuitBreakerFailureCounting:
    """Test failure counting mechanisms."""

    def test_consecutive_failures(self):
        """Test consecutive failure counting."""
        cb = CircuitBreaker(failure_threshold=3, failure_timeout_seconds=None)
        
        assert cb.get_stats()["failure_count"] == 0
        
        cb.record_failure()
        assert cb.get_stats()["failure_count"] == 1
        
        cb.record_failure()
        assert cb.get_stats()["failure_count"] == 2
        
        cb.record_failure()
        assert cb.get_stats()["failure_count"] == 3
        assert cb.get_state() == CircuitState.OPEN

    def test_sliding_window_failures(self):
        """Test sliding window failure counting."""
        cb = CircuitBreaker(
            failure_threshold=3,
            failure_timeout_seconds=0.5,  # 500ms window
        )
        
        # Record failures
        cb.record_failure()
        cb.record_failure()
        assert cb.get_stats()["failure_count"] == 2
        
        # Wait for window to expire
        time.sleep(0.6)
        
        # Old failures should be removed
        cb.record_failure()
        assert cb.get_stats()["failure_count"] == 1  # Only the new failure
        
        # Add more failures
        cb.record_failure()
        cb.record_failure()
        assert cb.get_stats()["failure_count"] == 3
        assert cb.get_state() == CircuitState.OPEN

    def test_success_resets_failures(self):
        """Test that success resets failure count in CLOSED state."""
        cb = CircuitBreaker(failure_threshold=3)
        
        cb.record_failure()
        cb.record_failure()
        assert cb.get_stats()["failure_count"] == 2
        
        # Success should reset
        cb.record_success()
        assert cb.get_stats()["failure_count"] == 0
        assert cb.get_state() == CircuitState.CLOSED


class TestCircuitBreakerCallMethod:
    """Test the call() method wrapper."""

    def test_call_success(self):
        """Test successful call through circuit breaker."""
        cb = CircuitBreaker()
        
        def success_func(x: int) -> int:
            return x * 2
        
        result = cb.call(success_func, 5)
        assert result == 10
        assert cb.get_state() == CircuitState.CLOSED

    def test_call_failure_records(self):
        """Test that call() records failures."""
        cb = CircuitBreaker(failure_threshold=2)
        
        def failing_func() -> None:
            raise ValueError("Test error")
        
        with pytest.raises(ValueError, match="Test error"):
            cb.call(failing_func)
        
        assert cb.get_stats()["failure_count"] == 1
        
        # Second failure should open circuit
        with pytest.raises(ValueError, match="Test error"):
            cb.call(failing_func)
        
        assert cb.get_state() == CircuitState.OPEN

    def test_call_blocks_when_open(self):
        """Test that call() blocks when circuit is open."""
        cb = CircuitBreaker(failure_threshold=1, timeout_seconds=1.0)
        
        # Open circuit
        cb.record_failure()
        assert cb.get_state() == CircuitState.OPEN
        
        def any_func() -> str:
            return "success"
        
        # Should raise CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError):
            cb.call(any_func)

    def test_call_allows_after_timeout(self):
        """Test that call() allows requests after timeout."""
        cb = CircuitBreaker(failure_threshold=1, timeout_seconds=1.0)
        
        # Open circuit
        cb.record_failure()
        assert cb.get_state() == CircuitState.OPEN
        
        # Manually advance time to trigger HALF_OPEN
        import time as time_module
        start_time = time_module.monotonic()
        
        def mock_monotonic():
            return start_time + 1.1  # Past timeout
        
        def test_func() -> str:
            return "test"
        
        with patch.object(time_module, 'monotonic', side_effect=mock_monotonic):
            # Should allow request (enters HALF_OPEN during allow_request check)
            result = cb.call(test_func)
            assert result == "test"
            # After successful call, state should be HALF_OPEN (or CLOSED if success_threshold=1)
            state = cb.get_state()
            assert state in (CircuitState.HALF_OPEN, CircuitState.CLOSED)


class TestCircuitBreakerEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_minimum_thresholds(self):
        """Test that minimum thresholds are enforced."""
        cb = CircuitBreaker(failure_threshold=0, success_threshold=0, timeout_seconds=0.0)
        
        # Should be clamped to minimums
        assert cb.failure_threshold >= 1
        assert cb.success_threshold >= 1
        assert cb.timeout_seconds >= 1.0

    def test_reset_manual(self):
        """Test manual reset of circuit breaker."""
        cb = CircuitBreaker(failure_threshold=2)
        
        # Open circuit
        cb.record_failure()
        cb.record_failure()
        assert cb.get_state() == CircuitState.OPEN
        
        # Manual reset
        cb.reset()
        assert cb.get_state() == CircuitState.CLOSED
        assert cb.get_stats()["failure_count"] == 0
        assert cb.get_stats()["consecutive_successes"] == 0

    def test_stats_information(self):
        """Test that stats provide useful information."""
        cb = CircuitBreaker(failure_threshold=2, timeout_seconds=10.0)
        
        stats = cb.get_stats()
        assert "state" in stats
        assert "consecutive_failures" in stats
        assert "consecutive_successes" in stats
        assert "failure_count" in stats
        assert "last_failure_time" in stats
        assert "state_since" in stats
        assert "next_attempt_time" in stats
        
        assert stats["state"] == "closed"
        assert stats["failure_count"] == 0

    def test_next_attempt_time(self):
        """Test next attempt time calculation."""
        cb = CircuitBreaker(failure_threshold=1, timeout_seconds=5.0)
        
        # Initially closed
        assert cb._next_attempt_time() == 0.0
        
        # Open circuit
        cb.record_failure()
        next_time = cb._next_attempt_time()
        assert next_time > 0
        assert next_time <= time.monotonic() + 5.0

    def test_thread_safety(self):
        """Test that circuit breaker is thread-safe."""
        import threading
        
        cb = CircuitBreaker(failure_threshold=10)
        results = []
        
        def record_failures():
            for _ in range(5):
                cb.record_failure()
                results.append(cb.get_state())
        
        threads = [threading.Thread(target=record_failures) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should have recorded all failures correctly
        assert cb.get_stats()["failure_count"] == 10
        assert cb.get_state() == CircuitState.OPEN


class TestCircuitBreakerIntegration:
    """Integration tests for circuit breaker with realistic scenarios."""

    def test_rate_limit_scenario(self):
        """Test circuit breaker behavior with rate limit errors."""
        cb = CircuitBreaker(failure_threshold=3, timeout_seconds=1.0)
        
        # Simulate rate limit errors
        for _ in range(3):
            cb.record_failure()
        
        assert cb.get_state() == CircuitState.OPEN
        
        # Circuit blocks requests
        assert cb.allow_request() is False
        
        # Manually advance time to trigger HALF_OPEN
        import time as time_module
        start_time = time_module.monotonic()
        
        def mock_monotonic():
            return start_time + 1.1  # Past timeout
        
        with patch.object(time_module, 'monotonic', side_effect=mock_monotonic):
            # Should allow test request (transitions to HALF_OPEN)
            allowed = cb.allow_request()
            assert allowed is True
            assert cb.get_state() == CircuitState.HALF_OPEN
        
        # Successful recovery
        cb.record_success()
        cb.record_success()
        assert cb.get_state() == CircuitState.CLOSED

    def test_intermittent_failures(self):
        """Test circuit breaker with intermittent failures."""
        cb = CircuitBreaker(
            failure_threshold=5,
            success_threshold=2,
            timeout_seconds=0.1,
            failure_timeout_seconds=0.3,  # Sliding window
        )
        
        # Record some failures
        for _ in range(3):
            cb.record_failure()
        
        # Success resets in CLOSED state
        cb.record_success()
        assert cb.get_stats()["failure_count"] == 0
        
        # More failures
        for _ in range(5):
            cb.record_failure()
        
        assert cb.get_state() == CircuitState.OPEN
        
        # Wait for timeout
        time.sleep(0.15)
        cb.allow_request()  # Enter HALF_OPEN
        
        # Intermittent: one success, one failure
        cb.record_success()
        cb.record_failure()  # Should immediately open again
        
        assert cb.get_state() == CircuitState.OPEN

    def test_rapid_recovery(self):
        """Test rapid recovery scenario."""
        cb = CircuitBreaker(
            failure_threshold=2,
            success_threshold=1,  # Only need 1 success
            timeout_seconds=1.0,
        )
        
        # Open circuit
        cb.record_failure()
        cb.record_failure()
        
        # Manually advance time to trigger HALF_OPEN
        import time as time_module
        start_time = time_module.monotonic()
        
        def mock_monotonic():
            return start_time + 1.1  # Past timeout
        
        with patch.object(time_module, 'monotonic', side_effect=mock_monotonic):
            # allow_request enters HALF_OPEN
            allowed = cb.allow_request()
            assert allowed is True
            assert cb.get_state() == CircuitState.HALF_OPEN
        
        # Single success closes circuit
        cb.record_success()
        assert cb.get_state() == CircuitState.CLOSED

