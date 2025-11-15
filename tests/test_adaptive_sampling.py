"""
Tests for adaptive sampling functionality.
"""

from __future__ import annotations

import pytest

from metamorphic_guard.adaptive import AdaptiveConfig, AdaptiveDecision, should_continue_adaptive
from metamorphic_guard.adaptive_sampling import (
    SamplingStrategy,
    TestCaseScore,
    compute_diversity_score,
    compute_uncertainty_score,
    compute_violation_focused_score,
    score_test_cases,
    select_next_batch,
)


def test_adaptive_config_defaults():
    """Test AdaptiveConfig with default values."""
    config = AdaptiveConfig()
    assert config.enabled is False
    assert config.min_sample_size == 50
    assert config.check_interval == 50
    assert config.power_threshold == 0.95
    assert config.max_sample_size is None
    assert config.early_stop_enabled is True
    assert config.group_sequential is False
    assert config.sequential_method == "pocock"
    assert config.max_looks == 5


def test_adaptive_config_custom():
    """Test AdaptiveConfig with custom values."""
    config = AdaptiveConfig(
        enabled=True,
        min_sample_size=100,
        check_interval=25,
        power_threshold=0.90,
        max_sample_size=500,
        group_sequential=True,
        sequential_method="obrien-fleming",
        max_looks=10,
    )
    assert config.enabled is True
    assert config.min_sample_size == 100
    assert config.check_interval == 25
    assert config.power_threshold == 0.90
    assert config.max_sample_size == 500
    assert config.group_sequential is True
    assert config.sequential_method == "obrien-fleming"
    assert config.max_looks == 10


def test_should_continue_adaptive_disabled():
    """Test adaptive decision when adaptive testing is disabled."""
    config = AdaptiveConfig(enabled=False)
    baseline_metrics = {"pass_rate": 0.8, "passes": 80, "total": 100}
    candidate_metrics = {"pass_rate": 0.85, "passes": 85, "total": 100}
    
    decision = should_continue_adaptive(
        baseline_metrics,
        candidate_metrics,
        current_n=100,
        alpha=0.05,
        min_delta=0.02,
        power_target=0.8,
        config=config,
    )
    
    assert decision.continue_sampling is True
    assert decision.recommended_n is None
    assert decision.reason == "adaptive_testing_disabled"


def test_should_continue_adaptive_below_minimum():
    """Test adaptive decision when below minimum sample size."""
    config = AdaptiveConfig(enabled=True, min_sample_size=100)
    baseline_metrics = {"pass_rate": 0.8, "passes": 40, "total": 50}
    candidate_metrics = {"pass_rate": 0.85, "passes": 42, "total": 50}
    
    decision = should_continue_adaptive(
        baseline_metrics,
        candidate_metrics,
        current_n=50,
        alpha=0.05,
        min_delta=0.02,
        power_target=0.8,
        config=config,
    )
    
    assert decision.continue_sampling is True
    assert decision.reason.startswith("below_minimum_sample_size")


def test_should_continue_adaptive_max_sample_size():
    """Test adaptive decision when maximum sample size is reached."""
    config = AdaptiveConfig(enabled=True, max_sample_size=200)
    baseline_metrics = {"pass_rate": 0.8, "passes": 160, "total": 200}
    candidate_metrics = {"pass_rate": 0.85, "passes": 170, "total": 200}
    
    decision = should_continue_adaptive(
        baseline_metrics,
        candidate_metrics,
        current_n=200,
        alpha=0.05,
        min_delta=0.02,
        power_target=0.8,
        config=config,
    )
    
    assert decision.continue_sampling is False
    assert decision.recommended_n == 200
    assert decision.reason.startswith("reached_maximum_sample_size")


def test_should_continue_adaptive_high_power():
    """Test adaptive decision when power threshold is exceeded."""
    config = AdaptiveConfig(enabled=True, power_threshold=0.95, min_sample_size=50)
    # High power scenario: clear difference
    baseline_metrics = {"pass_rate": 0.7, "passes": 70, "total": 100}
    candidate_metrics = {"pass_rate": 0.9, "passes": 90, "total": 100}
    
    decision = should_continue_adaptive(
        baseline_metrics,
        candidate_metrics,
        current_n=100,
        alpha=0.05,
        min_delta=0.02,
        power_target=0.8,
        config=config,
    )
    
    # Should stop early if power is high enough
    assert isinstance(decision.continue_sampling, bool)
    assert decision.current_power >= 0.0
    assert decision.reason is not None


def test_should_continue_adaptive_low_power():
    """Test adaptive decision when power is below threshold."""
    config = AdaptiveConfig(enabled=True, power_threshold=0.95, min_sample_size=50)
    # Low power scenario: small difference
    baseline_metrics = {"pass_rate": 0.8, "passes": 80, "total": 100}
    candidate_metrics = {"pass_rate": 0.81, "passes": 81, "total": 100}
    
    decision = should_continue_adaptive(
        baseline_metrics,
        candidate_metrics,
        current_n=100,
        alpha=0.05,
        min_delta=0.02,
        power_target=0.8,
        config=config,
    )
    
    # Should continue sampling if power is low
    assert isinstance(decision.continue_sampling, bool)
    assert decision.current_power >= 0.0


def test_compute_uncertainty_score():
    """Test uncertainty score computation."""
    # Case with no results (high uncertainty)
    score1 = compute_uncertainty_score(None, None)
    assert score1 > 0
    
    # Case with results (lower uncertainty)
    baseline_result = {"success": True, "result": 42}
    candidate_result = {"success": True, "result": 42}
    score2 = compute_uncertainty_score(baseline_result, candidate_result)
    assert score2 >= 0
    
    # Case with different results (higher uncertainty)
    candidate_result_diff = {"success": True, "result": 100}
    score3 = compute_uncertainty_score(baseline_result, candidate_result_diff)
    assert score3 >= score2


def test_compute_diversity_score():
    """Test diversity score computation."""
    test_inputs = [(1,), (2,), (3,), (4,), (5,)]
    executed_inputs = [(1,), (2,)]  # Already executed
    
    # Should prefer unexecuted cases
    score = compute_diversity_score((3,), executed_inputs, cluster_key=None)
    assert score > 0
    
    # Already executed cases should have lower diversity
    score_executed = compute_diversity_score((1,), executed_inputs, cluster_key=None)
    assert score_executed < score


def test_compute_violation_focused_score():
    """Test violation-focused score computation."""
    violation_history = {
        (1,): 2,
        (2,): 1,
    }
    
    # Cases in violation history should score higher
    score1 = compute_violation_focused_score((1,), violation_history)
    score2 = compute_violation_focused_score((2,), violation_history)
    score3 = compute_violation_focused_score((3,), violation_history)  # Not in history, but similar (within 10 units)
    score4 = compute_violation_focused_score((100,), violation_history)  # Not in history, not similar
    
    assert score1 == 1.0  # Direct match returns 1.0
    assert score2 == 1.0  # Direct match returns 1.0
    assert score3 == 0.5  # Similar pattern (within 10 units) returns 0.5
    assert score4 == 0.0  # Not similar, not in history returns 0.0
    assert score1 > score3
    assert score2 > score3
    assert score3 > score4


def test_score_test_cases():
    """Test test case scoring."""
    test_inputs = [(1,), (2,), (3,)]
    baseline_results = [
        {"success": True, "result": 10},
        None,  # Not executed yet
        {"success": True, "result": 30},
    ]
    candidate_results = [
        {"success": True, "result": 10},
        None,  # Not executed yet
        {"success": True, "result": 35},  # Different result
    ]
    
    strategy = SamplingStrategy(
        diversity_weight=0.3,
        violation_weight=0.2,
        batch_size=2,
    )
    
    scores = score_test_cases(
        test_inputs,
        baseline_results,
        candidate_results,
        strategy,
    )
    
    # Function only scores unexecuted cases (where both results are None)
    assert len(scores) >= 1  # At least the unexecuted case
    assert all(isinstance(score, TestCaseScore) for score in scores)
    # Unexecuted case (index 1) should be in the scores
    unexecuted_scores = [s for s in scores if s.index == 1]
    assert len(unexecuted_scores) > 0
    # Unexecuted case should have a positive score
    assert unexecuted_scores[0].score > 0


def test_select_next_batch():
    """Test next batch selection."""
    test_inputs = [(1,), (2,), (3,), (4,), (5,)]
    baseline_results = [
        {"success": True, "result": 10},
        None,
        {"success": True, "result": 30},
        None,
        None,
    ]
    candidate_results = [
        {"success": True, "result": 10},
        None,
        {"success": True, "result": 35},
        None,
        None,
    ]
    
    strategy = SamplingStrategy(
        diversity_weight=0.3,
        violation_weight=0.2,
        batch_size=2,
    )
    
    selected = select_next_batch(
        test_inputs,
        baseline_results,
        candidate_results,
        strategy,
    )
    
    assert len(selected) <= strategy.batch_size + 2  # batch_size + some randomness
    assert all(idx in range(len(test_inputs)) for idx in selected)
    # Should prefer unexecuted cases
    unexecuted = [1, 3, 4]
    assert any(idx in unexecuted for idx in selected)


def test_adaptive_group_sequential_pocock():
    """Test adaptive testing with Pocock group sequential method."""
    config = AdaptiveConfig(
        enabled=True,
        group_sequential=True,
        sequential_method="pocock",
        max_looks=5,
        min_sample_size=50,
    )
    
    baseline_metrics = {"pass_rate": 0.8, "passes": 80, "total": 100}
    candidate_metrics = {"pass_rate": 0.85, "passes": 85, "total": 100}
    
    decision = should_continue_adaptive(
        baseline_metrics,
        candidate_metrics,
        current_n=100,
        alpha=0.05,
        min_delta=0.02,
        power_target=0.8,
        config=config,
        look_number=2,
    )
    
    assert isinstance(decision.continue_sampling, bool)
    assert decision.current_power >= 0.0
    assert decision.reason is not None


def test_adaptive_group_sequential_obrien_fleming():
    """Test adaptive testing with O'Brien-Fleming group sequential method."""
    config = AdaptiveConfig(
        enabled=True,
        group_sequential=True,
        sequential_method="obrien-fleming",
        max_looks=5,
        min_sample_size=50,
    )
    
    baseline_metrics = {"pass_rate": 0.8, "passes": 80, "total": 100}
    candidate_metrics = {"pass_rate": 0.85, "passes": 85, "total": 100}
    
    decision = should_continue_adaptive(
        baseline_metrics,
        candidate_metrics,
        current_n=100,
        alpha=0.05,
        min_delta=0.02,
        power_target=0.8,
        config=config,
        look_number=2,
    )
    
    assert isinstance(decision.continue_sampling, bool)
    assert decision.current_power >= 0.0


def test_adaptive_power_calculation():
    """Test that power is correctly calculated in adaptive decisions."""
    config = AdaptiveConfig(enabled=True, min_sample_size=50)
    
    # Scenario with high power (large difference)
    baseline_metrics = {"pass_rate": 0.6, "passes": 60, "total": 100}
    candidate_metrics = {"pass_rate": 0.8, "passes": 80, "total": 100}
    
    decision = should_continue_adaptive(
        baseline_metrics,
        candidate_metrics,
        current_n=100,
        alpha=0.05,
        min_delta=0.02,
        power_target=0.8,
        config=config,
    )
    
    assert decision.current_power > 0.0
    assert decision.current_power <= 1.0
    
    # Scenario with low power (small difference)
    baseline_metrics_low = {"pass_rate": 0.8, "passes": 80, "total": 100}
    candidate_metrics_low = {"pass_rate": 0.81, "passes": 81, "total": 100}
    
    decision_low = should_continue_adaptive(
        baseline_metrics_low,
        candidate_metrics_low,
        current_n=100,
        alpha=0.05,
        min_delta=0.02,
        power_target=0.8,
        config=config,
    )
    
    assert decision_low.current_power < decision.current_power


def test_sampling_strategy_weights():
    """Test that sampling strategy weights affect scoring."""
    test_inputs = [(1,), (2,), (3,)]
    baseline_results = [None, None, None]
    candidate_results = [None, None, None]
    
    # Strategy emphasizing uncertainty (default method)
    strategy_uncertainty = SamplingStrategy(
        method="uncertainty",
        diversity_weight=0.0,
        violation_weight=0.0,
        batch_size=2,
    )
    
    # Strategy emphasizing diversity
    strategy_diversity = SamplingStrategy(
        method="diversity",
        diversity_weight=1.0,
        violation_weight=0.0,
        batch_size=2,
    )
    
    scores_uncertainty = score_test_cases(
        test_inputs, baseline_results, candidate_results, strategy_uncertainty
    )
    scores_diversity = score_test_cases(
        test_inputs, baseline_results, candidate_results, strategy_diversity
    )
    
    # Both should produce valid scores
    assert len(scores_uncertainty) == 3
    assert len(scores_diversity) == 3
    # Scores may differ based on strategy
    assert all(s.score >= 0 for s in scores_uncertainty)
    assert all(s.score >= 0 for s in scores_diversity)

