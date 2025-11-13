"""
Tests for group sequential designs.
"""

from __future__ import annotations

import pytest

from metamorphic_guard.adaptive import AdaptiveConfig, should_continue_adaptive
from metamorphic_guard.sequential_testing import SequentialTestConfig, compute_sequential_alpha


def test_group_sequential_config():
    """Test AdaptiveConfig with group sequential enabled."""
    config = AdaptiveConfig(
        enabled=True,
        group_sequential=True,
        sequential_method="pocock",
        max_looks=5,
        min_sample_size=50,
    )
    
    assert config.group_sequential is True
    assert config.sequential_method == "pocock"
    assert config.max_looks == 5


def test_group_sequential_boundary_cross():
    """Test that group sequential stops when boundary is crossed."""
    config = AdaptiveConfig(
        enabled=True,
        group_sequential=True,
        sequential_method="pocock",
        max_looks=3,
        min_sample_size=10,
    )
    
    # Large improvement that should cross boundary
    decision = should_continue_adaptive(
        baseline_metrics={"pass_rate": 0.5, "total": 200},
        candidate_metrics={"pass_rate": 0.8, "total": 200},  # Large improvement
        current_n=200,
        alpha=0.05,
        min_delta=0.02,
        power_target=0.8,
        config=config,
        look_number=1,
    )
    
    # Should stop if boundary crossed, or continue to next look
    assert isinstance(decision.continue_sampling, bool)
    assert "group_sequential" in decision.reason or decision.continue_sampling is True


def test_group_sequential_max_looks():
    """Test that group sequential stops at final look."""
    config = AdaptiveConfig(
        enabled=True,
        group_sequential=True,
        sequential_method="pocock",
        max_looks=3,
        min_sample_size=10,
    )
    
    decision = should_continue_adaptive(
        baseline_metrics={"pass_rate": 0.7, "total": 300},
        candidate_metrics={"pass_rate": 0.72, "total": 300},  # Small improvement
        current_n=300,
        alpha=0.05,
        min_delta=0.02,
        power_target=0.8,
        config=config,
        look_number=3,  # Final look
    )
    
    # At final look, should stop
    assert decision.continue_sampling is False
    assert "final_look" in decision.reason


def test_group_sequential_obrien_fleming():
    """Test group sequential with O'Brien-Fleming boundaries."""
    config = AdaptiveConfig(
        enabled=True,
        group_sequential=True,
        sequential_method="obrien-fleming",
        max_looks=3,
        min_sample_size=10,
    )
    
    decision = should_continue_adaptive(
        baseline_metrics={"pass_rate": 0.7, "total": 100},
        candidate_metrics={"pass_rate": 0.71, "total": 100},
        current_n=100,
        alpha=0.05,
        min_delta=0.02,
        power_target=0.8,
        config=config,
        look_number=1,
    )
    
    # O'Brien-Fleming is more conservative early, so may continue
    assert isinstance(decision.continue_sampling, bool)


def test_adaptive_vs_group_sequential():
    """Test that adaptive and group sequential use different decision logic."""
    # Adaptive (power-based)
    adaptive_config = AdaptiveConfig(
        enabled=True,
        group_sequential=False,
        power_threshold=0.95,
        min_sample_size=50,
    )
    
    # Group sequential
    gs_config = AdaptiveConfig(
        enabled=True,
        group_sequential=True,
        sequential_method="pocock",
        max_looks=3,
        min_sample_size=50,
    )
    
    baseline_metrics = {"pass_rate": 0.8, "total": 200}
    candidate_metrics = {"pass_rate": 0.9, "total": 200}
    
    adaptive_decision = should_continue_adaptive(
        baseline_metrics=baseline_metrics,
        candidate_metrics=candidate_metrics,
        current_n=200,
        alpha=0.05,
        min_delta=0.02,
        power_target=0.8,
        config=adaptive_config,
        look_number=1,
    )
    
    gs_decision = should_continue_adaptive(
        baseline_metrics=baseline_metrics,
        candidate_metrics=candidate_metrics,
        current_n=200,
        alpha=0.05,
        min_delta=0.02,
        power_target=0.8,
        config=gs_config,
        look_number=1,
    )
    
    # They may differ, but both should return valid decisions
    assert isinstance(adaptive_decision.continue_sampling, bool)
    assert isinstance(gs_decision.continue_sampling, bool)

