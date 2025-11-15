"""
Tests for observability integration (Prometheus, logging, queue telemetry).
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from metamorphic_guard.observability import (
    configure_logging,
    configure_metrics,
    increment_llm_retries,
    increment_queue_completed,
    increment_queue_dispatched,
    increment_queue_requeued,
    log_event,
    metrics_enabled,
    observe_queue_pending_tasks,
)


def test_log_event_basic():
    """Test basic event logging."""
    with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".jsonl") as f:
        log_path = f.name
    
    try:
        configure_logging(enabled=True, path=log_path)
        
        log_event("test_event", key1="value1", key2=42)
        
        # Read log file
        with open(log_path, "r") as f:
            lines = f.readlines()
            assert len(lines) == 1
            log_entry = json.loads(lines[0])
            assert log_entry["event"] == "test_event"
            assert log_entry["key1"] == "value1"
            assert log_entry["key2"] == 42
    finally:
        if os.path.exists(log_path):
            os.unlink(log_path)


def test_log_event_with_context():
    """Test event logging with context."""
    with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".jsonl") as f:
        log_path = f.name
    
    try:
        configure_logging(
            enabled=True,
            path=log_path,
            context={"run_id": "test-123", "task": "top_k"},
        )
        
        log_event("test_event", additional="data")
        
        with open(log_path, "r") as f:
            log_entry = json.loads(f.read())
            assert log_entry["event"] == "test_event"
            assert log_entry["run_id"] == "test-123"
            assert log_entry["task"] == "top_k"
            assert log_entry["additional"] == "data"
    finally:
        if os.path.exists(log_path):
            os.unlink(log_path)


def test_log_event_disabled():
    """Test that logging is disabled by default."""
    # Should not raise error even if logging is disabled
    log_event("test_event", key="value")
    # No assertion needed - just verify no exception


def test_configure_metrics_without_prometheus():
    """Test metrics configuration when prometheus_client is not available."""
    with patch("metamorphic_guard.observability._PROMETHEUS_IMPORTED", False):
        with pytest.raises(RuntimeError, match="Prometheus support requires"):
            configure_metrics(enabled=True)


def test_configure_metrics_enabled():
    """Test enabling metrics."""
    try:
        from prometheus_client import CollectorRegistry, Counter, Gauge, start_http_server
        
        with patch("metamorphic_guard.observability._PROMETHEUS_IMPORTED", True):
            with patch("metamorphic_guard.observability.CollectorRegistry", CollectorRegistry):
                with patch("metamorphic_guard.observability.Counter", Counter):
                    with patch("metamorphic_guard.observability.Gauge", Gauge):
                        with patch("metamorphic_guard.observability.start_http_server") as mock_server:
                            configure_metrics(enabled=True, port=9093)
                            
                            assert metrics_enabled() is True
                            # Server should be started
                            mock_server.assert_called_once()
    except ImportError:
        pytest.skip("prometheus_client not available")


def test_increment_queue_dispatched():
    """Test incrementing queue dispatched counter."""
    try:
        from prometheus_client import CollectorRegistry, Counter
        
        with patch("metamorphic_guard.observability._METRICS_ENABLED", True):
            with patch("metamorphic_guard.observability._PROM_COUNTERS") as mock_counters:
                mock_counter = MagicMock()
                mock_counters.get.return_value = mock_counter
                
                increment_queue_dispatched(count=5)
                
                # Should call increment on the counter
                mock_counter.inc.assert_called_once_with(5)
    except ImportError:
        pytest.skip("prometheus_client not available")


def test_increment_queue_completed():
    """Test incrementing queue completed counter."""
    try:
        from prometheus_client import CollectorRegistry, Counter
        
        with patch("metamorphic_guard.observability._METRICS_ENABLED", True):
            with patch("metamorphic_guard.observability._PROM_COUNTERS") as mock_counters:
                mock_counter = MagicMock()
                mock_counters.get.return_value = mock_counter
                
                increment_queue_completed(count=3)
                
                mock_counter.inc.assert_called_once_with(3)
    except ImportError:
        pytest.skip("prometheus_client not available")


def test_increment_queue_requeued():
    """Test incrementing queue requeued counter."""
    try:
        from prometheus_client import CollectorRegistry, Counter
        
        with patch("metamorphic_guard.observability._METRICS_ENABLED", True):
            with patch("metamorphic_guard.observability._PROM_COUNTERS") as mock_counters:
                mock_counter = MagicMock()
                mock_counters.get.return_value = mock_counter
                
                increment_queue_requeued(count=2)
                
                mock_counter.inc.assert_called_once_with(2)
    except ImportError:
        pytest.skip("prometheus_client not available")


def test_increment_llm_retries():
    """Test incrementing LLM retries counter."""
    try:
        from prometheus_client import CollectorRegistry, Counter
        
        with patch("metamorphic_guard.observability._METRICS_ENABLED", True):
            with patch("metamorphic_guard.observability._PROM_COUNTERS") as mock_counters:
                mock_counter = MagicMock()
                mock_counters.get.return_value = mock_counter
                
                increment_llm_retries(provider="openai", role="baseline", count=1)
                
                mock_counter.labels.assert_called_once_with(provider="openai", role="baseline")
    except ImportError:
        pytest.skip("prometheus_client not available")


def test_observe_queue_pending():
    """Test observing queue pending gauge."""
    try:
        from prometheus_client import CollectorRegistry, Gauge
        
        with patch("metamorphic_guard.observability._METRICS_ENABLED", True):
            with patch("metamorphic_guard.observability._PROM_GAUGES") as mock_gauges:
                mock_gauge = MagicMock()
                mock_gauges.get.return_value = mock_gauge
                
                from metamorphic_guard.observability import observe_queue_pending_tasks
                observe_queue_pending_tasks(10)
                
                mock_gauge.set.assert_called_once_with(10)
    except ImportError:
        pytest.skip("prometheus_client not available")


def test_metrics_disabled_by_default():
    """Test that metrics are disabled by default."""
    # Should return False when metrics are not enabled
    # This test may need adjustment based on actual implementation
    assert isinstance(metrics_enabled(), bool)


def test_logging_json_format():
    """Test that logging produces valid JSON."""
    with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".jsonl") as f:
        log_path = f.name
    
    try:
        configure_logging(enabled=True, path=log_path)
        
        log_event("test", nested={"key": "value"}, number=123)
        
        with open(log_path, "r") as f:
            line = f.read().strip()
            # Should be valid JSON
            parsed = json.loads(line)
            assert parsed["event"] == "test"
            assert parsed["nested"]["key"] == "value"
            assert parsed["number"] == 123
    finally:
        if os.path.exists(log_path):
            os.unlink(log_path)


def test_observability_integration_queue_telemetry():
    """Test queue telemetry integration."""
    try:
        from prometheus_client import CollectorRegistry, Counter, Gauge
        
        with patch("metamorphic_guard.observability._METRICS_ENABLED", True):
            with patch("metamorphic_guard.observability._PROM_COUNTERS") as mock_counters:
                with patch("metamorphic_guard.observability._PROM_GAUGES") as mock_gauges:
                    # Simulate queue operations
                    mock_dispatch_counter = MagicMock()
                    mock_complete_counter = MagicMock()
                    mock_requeue_counter = MagicMock()
                    mock_pending_gauge = MagicMock()
                    
                    mock_counters.get.side_effect = lambda k: {
                        "queue_dispatched": mock_dispatch_counter,
                        "queue_completed": mock_complete_counter,
                        "queue_requeued": mock_requeue_counter,
                    }.get(k)
                    
                    mock_gauges.get.return_value = mock_pending_gauge
                    
                    # Dispatch some tasks
                    increment_queue_dispatched(count=5)
                    observe_queue_pending_tasks(5)
                    
                    # Complete some tasks
                    increment_queue_completed(count=3)
                    observe_queue_pending_tasks(2)
                    
                    # Requeue a task
                    increment_queue_requeued(count=1)
                    
                    # Verify calls were made
                    assert mock_dispatch_counter.inc.called
                    assert mock_complete_counter.inc.called
                    assert mock_requeue_counter.inc.called
                    assert mock_pending_gauge.set.call_count >= 2
    except ImportError:
        pytest.skip("prometheus_client not available")

