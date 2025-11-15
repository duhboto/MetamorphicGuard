"""
Tests for PerformanceProfiler.
"""

from __future__ import annotations

import pytest

from metamorphic_guard.monitoring import MonitorContext, MonitorRecord
from metamorphic_guard.profiling import PerformanceProfiler


def test_performance_profiler_basic():
    """Test basic performance profiler functionality."""
    profiler = PerformanceProfiler()
    
    context = MonitorContext(task="test", total_cases=10)
    profiler.start(context)
    
    # Record some baseline executions
    for i in range(5):
        record = MonitorRecord(
            case_index=i,
            role="baseline",
            duration_ms=100.0 + i * 10,
            success=True,
            result={},
        )
        profiler.record(record)
    
    # Record some candidate executions
    for i in range(5):
        record = MonitorRecord(
            case_index=i,
            role="candidate",
            duration_ms=120.0 + i * 10,
            success=True,
            result={},
        )
        profiler.record(record)
    
    result = profiler.finalize()
    
    assert result["type"] == "performance_profiler"
    assert "latency" in result
    assert "success_rate" in result
    assert "comparison" in result
    assert "alerts" in result


def test_performance_profiler_latency_stats():
    """Test latency statistics computation."""
    profiler = PerformanceProfiler()
    
    values = [50.0, 100.0, 150.0, 200.0, 250.0]
    for i, val in enumerate(values):
        record = MonitorRecord(
            case_index=i,
            role="baseline",
            duration_ms=val,
            success=True,
            result={},
        )
        profiler.record(record)
    
    result = profiler.finalize()
    latency = result["latency"]["baseline"]
    
    assert latency["count"] == 5
    assert latency["min_ms"] == 50.0
    assert latency["max_ms"] == 250.0
    assert latency["mean_ms"] == 150.0
    assert latency["median_ms"] == 150.0
    assert "percentiles" in latency


def test_performance_profiler_cost_tracking():
    """Test cost profiling."""
    profiler = PerformanceProfiler(enable_cost_profiling=True)
    
    for i in range(3):
        record = MonitorRecord(
            case_index=i,
            role="baseline",
            duration_ms=100.0,
            success=True,
            result={"cost_usd": 0.001 * (i + 1), "tokens_total": 100 * (i + 1)},
        )
        profiler.record(record)
    
    result = profiler.finalize()
    
    assert "cost" in result
    assert "tokens" in result
    
    cost = result["cost"]["baseline"]
    assert cost["count"] == 3
    assert cost["total_usd"] == 0.006  # 0.001 + 0.002 + 0.003
    assert cost["mean_usd"] == 0.002
    
    tokens = result["tokens"]["baseline"]
    assert tokens["count"] == 3
    assert tokens["total"] == 600  # 100 + 200 + 300


def test_performance_profiler_success_rate():
    """Test success rate tracking."""
    profiler = PerformanceProfiler()
    
    # Record 3 successes and 2 failures for baseline
    for i in range(3):
        record = MonitorRecord(
            case_index=i,
            role="baseline",
            duration_ms=100.0,
            success=True,
            result={},
        )
        profiler.record(record)
    
    for i in range(3, 5):
        record = MonitorRecord(
            case_index=i,
            role="baseline",
            duration_ms=100.0,
            success=False,
            result={},
        )
        profiler.record(record)
    
    result = profiler.finalize()
    success_rate = result["success_rate"]["baseline"]
    
    assert success_rate["total"] == 5
    assert success_rate["successes"] == 3
    assert success_rate["failures"] == 2
    assert success_rate["success_rate"] == 0.6


def test_performance_profiler_distribution():
    """Test latency distribution buckets."""
    profiler = PerformanceProfiler(enable_distribution=True)
    
    # Record values in different buckets
    test_values = [25.0, 75.0, 150.0, 300.0, 750.0, 1500.0]
    for i, val in enumerate(test_values):
        record = MonitorRecord(
            case_index=i,
            role="baseline",
            duration_ms=val,
            success=True,
            result={},
        )
        profiler.record(record)
    
    result = profiler.finalize()
    distribution = result["distribution"]["baseline"]
    
    assert len(distribution) > 0
    # Should have entries for different buckets
    assert any("0-50" in key for key in distribution.keys())
    assert any("50-100" in key for key in distribution.keys())


def test_performance_profiler_comparison():
    """Test comparative analysis."""
    profiler = PerformanceProfiler()
    
    # Baseline: faster, cheaper
    for i in range(5):
        record = MonitorRecord(
            case_index=i,
            role="baseline",
            duration_ms=100.0,
            success=True,
            result={"cost_usd": 0.001},
        )
        profiler.record(record)
    
    # Candidate: slower, more expensive
    for i in range(5):
        record = MonitorRecord(
            case_index=i,
            role="candidate",
            duration_ms=150.0,
            success=True,
            result={"cost_usd": 0.002},
        )
        profiler.record(record)
    
    result = profiler.finalize()
    comparison = result["comparison"]
    
    assert "latency" in comparison
    assert comparison["latency"]["delta_percent"] > 0  # Candidate is slower
    assert "cost" in comparison
    assert comparison["cost"]["delta_percent"] > 0  # Candidate is more expensive


def test_performance_profiler_alerts():
    """Test alert generation for regressions."""
    profiler = PerformanceProfiler()
    
    # Baseline: fast and cheap
    for i in range(10):
        record = MonitorRecord(
            case_index=i,
            role="baseline",
            duration_ms=100.0,
            success=True,
            result={"cost_usd": 0.001},
        )
        profiler.record(record)
    
    # Candidate: much slower (>20% regression)
    for i in range(10):
        record = MonitorRecord(
            case_index=i,
            role="candidate",
            duration_ms=130.0,  # 30% slower
            success=True,
            result={"cost_usd": 0.0015},  # 50% more expensive
        )
        profiler.record(record)
    
    result = profiler.finalize()
    alerts = result["alerts"]
    
    # Should have latency and cost regression alerts
    alert_types = [a["type"] for a in alerts]
    assert "latency_regression" in alert_types
    assert "cost_regression" in alert_types


def test_performance_profiler_no_cost_tracking():
    """Test profiler with cost tracking disabled."""
    profiler = PerformanceProfiler(enable_cost_profiling=False)
    
    record = MonitorRecord(
        case_index=0,
        role="baseline",
        duration_ms=100.0,
        success=True,
        result={"cost_usd": 0.001},
    )
    profiler.record(record)
    
    result = profiler.finalize()
    
    assert "cost" not in result
    assert "tokens" not in result


def test_performance_profiler_no_distribution():
    """Test profiler with distribution disabled."""
    profiler = PerformanceProfiler(enable_distribution=False)
    
    record = MonitorRecord(
        case_index=0,
        role="baseline",
        duration_ms=100.0,
        success=True,
        result={},
    )
    profiler.record(record)
    
    result = profiler.finalize()
    
    assert "distribution" not in result

