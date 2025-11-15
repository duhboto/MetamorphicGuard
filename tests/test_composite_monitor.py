"""
Tests for CompositeMonitor functionality.
"""

from __future__ import annotations

import pytest

from metamorphic_guard.monitoring import (
    CompositeMonitor,
    LLMCostMonitor,
    LatencyMonitor,
    MonitorContext,
    MonitorRecord,
    create_composite_monitor,
)


def test_composite_monitor_identifier():
    """Test composite monitor identifier generation."""
    m1 = LatencyMonitor()
    m2 = LLMCostMonitor()
    composite = CompositeMonitor([m1, m2])
    
    identifier = composite.identifier()
    assert "composite" in identifier.lower()
    assert "latency" in identifier.lower() or "LatencyMonitor" in identifier


def test_composite_monitor_start():
    """Test that composite monitor starts all sub-monitors."""
    m1 = LatencyMonitor()
    m2 = LLMCostMonitor()
    composite = CompositeMonitor([m1, m2])
    
    context = MonitorContext(task="test", total_cases=10)
    composite.start(context)
    
    # Both monitors should have received the context
    assert m1._context == context
    assert m2._context == context


def test_composite_monitor_record():
    """Test that composite monitor records to all sub-monitors."""
    m1 = LatencyMonitor()
    m2 = LLMCostMonitor()
    composite = CompositeMonitor([m1, m2])
    
    record = MonitorRecord(
        case_index=0,
        role="baseline",
        duration_ms=100.0,
        success=True,
        result={"tokens_total": 50, "cost_usd": 0.001},
    )
    
    composite.record(record)
    
    # Both monitors should have recorded the data
    m1_final = m1.finalize()
    m2_final = m2.finalize()
    
    # LatencyMonitor tracks count
    assert m1_final["summary"]["baseline"]["count"] == 1
    # LLMCostMonitor tracks tokens/costs, verify it has baseline data
    assert "baseline" in m2_final["summary"]
    assert m2_final["summary"]["baseline"]["tokens_total"]["count"] == 1
    assert m2_final["summary"]["baseline"]["cost_usd"]["count"] == 1


def test_composite_monitor_finalize():
    """Test that composite monitor aggregates results from all sub-monitors."""
    m1 = LatencyMonitor()
    m2 = LLMCostMonitor()
    composite = CompositeMonitor([m1, m2])
    
    # Record some data
    for i in range(5):
        record = MonitorRecord(
            case_index=i,
            role="baseline",
            duration_ms=100.0 + i,
            success=True,
            result={"tokens_total": 50, "cost_usd": 0.001},
        )
        composite.record(record)
    
    result = composite.finalize()
    
    assert result["type"] == "composite"
    assert "monitors" in result
    assert "alerts" in result
    assert "summary" in result
    assert result["summary"]["total_monitors"] == 2
    assert len(result["monitors"]) == 2


def test_composite_monitor_alerts():
    """Test that composite monitor aggregates alerts from sub-monitors."""
    m1 = LatencyMonitor(alert_ratio=1.1)  # Low threshold to trigger alerts
    m2 = LLMCostMonitor(alert_cost_ratio=1.1)  # Low threshold
    
    composite = CompositeMonitor([m1, m2])
    
    # Record baseline (fast, cheap)
    for i in range(10):
        record = MonitorRecord(
            case_index=i,
            role="baseline",
            duration_ms=100.0,
            success=True,
            result={"tokens_total": 50, "cost_usd": 0.001},
        )
        composite.record(record)
    
    # Record candidate (slow, expensive) - should trigger alerts
    for i in range(10):
        record = MonitorRecord(
            case_index=i,
            role="candidate",
            duration_ms=150.0,
            success=True,
            result={"tokens_total": 100, "cost_usd": 0.002},
        )
        composite.record(record)
    
    result = composite.finalize()
    
    # Should have aggregated alerts from both monitors
    alerts = result.get("alerts", [])
    assert len(alerts) > 0
    
    # Each alert should have a monitor identifier
    for alert in alerts:
        assert "monitor" in alert


def test_create_composite_monitor_helper():
    """Test the create_composite_monitor helper function."""
    m1 = LatencyMonitor()
    m2 = LLMCostMonitor()
    
    composite = create_composite_monitor([m1, m2])
    
    assert isinstance(composite, CompositeMonitor)
    assert len(composite._monitors) == 2


def test_composite_monitor_empty():
    """Test composite monitor with no sub-monitors."""
    composite = CompositeMonitor([])
    
    result = composite.finalize()
    assert result["summary"]["total_monitors"] == 0
    assert len(result["alerts"]) == 0

