"""Tests for plugin contract and discovery."""

from __future__ import annotations

from pathlib import Path

import pytest

from metamorphic_guard.harness import run_eval
from metamorphic_guard.plugins import monitor_plugins


def test_monitor_plugin_discovery() -> None:
    """Test that test monitor plugin is discoverable via entry points."""
    plugins = monitor_plugins()
    
    # Should find the test monitor
    assert "test_monitor" in plugins, "Test monitor should be discoverable"
    
    plugin_def = plugins["test_monitor"]
    assert plugin_def.name == "test_monitor"
    assert plugin_def.group == "metamorphic_guard.monitors"
    
    # Verify factory works
    monitor_instance = plugin_def.factory(config=None)
    assert monitor_instance is not None
    assert hasattr(monitor_instance, "record")
    assert hasattr(monitor_instance, "finalize")


def test_monitor_plugin_integration(tmp_path: Path) -> None:
    """Test that test monitor plugin works in actual evaluation."""
    baseline_path = Path("examples/top_k_baseline.py")
    candidate_path = Path("examples/top_k_improved.py")
    
    if not baseline_path.exists() or not candidate_path.exists():
        pytest.skip("Example files not found")
    
    # Resolve monitors first
    from metamorphic_guard.monitoring import resolve_monitors
    monitors = resolve_monitors(["test_monitor"], sandbox_plugins=False)
    
    # Run evaluation with test monitor
    result = run_eval(
        task_name="top_k",
        baseline_path=str(baseline_path),
        candidate_path=str(candidate_path),
        n=20,
        seed=42,
        monitors=monitors,
    )
    
    # Verify monitor was executed
    monitors = result.get("monitors", {})
    # Monitor key is the class name, not the entry point name
    assert "TestMonitor" in monitors, f"Test monitor should appear in results. Found: {list(monitors.keys())}"
    
    monitor_data = monitors["TestMonitor"]
    assert monitor_data["type"] == "test_monitor"
    
    # Verify summary contains expected data
    summary = monitor_data.get("summary", {})
    assert "baseline" in summary
    assert "candidate" in summary
    
    baseline_summary = summary["baseline"]
    candidate_summary = summary["candidate"]
    
    assert baseline_summary["total"] == 20, "Should have 20 baseline cases"
    assert candidate_summary["total"] == 20, "Should have 20 candidate cases"
    
    # Verify successes are tracked
    assert "successes" in baseline_summary
    assert "successes" in candidate_summary

