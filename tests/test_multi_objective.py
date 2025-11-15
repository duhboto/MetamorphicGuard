"""
Tests for multi-objective analysis and Pareto frontier computation.
"""

from __future__ import annotations

import pytest

from metamorphic_guard.multi_objective import (
    CandidateMetrics,
    MultiObjectiveConfig,
    Objective,
    ParetoPoint,
    analyze_trade_offs,
    compute_pareto_frontier,
    compute_weighted_sum_score,
    is_dominated,
    multi_criteria_gate,
    recommend_candidate,
)


def test_is_dominated():
    """Test dominance checking between two points."""
    minimize = {"cost": True, "accuracy": False}
    
    # Point 1 dominates point 2 (lower cost, higher accuracy)
    point1 = {"cost": 10.0, "accuracy": 0.9}
    point2 = {"cost": 20.0, "accuracy": 0.8}
    
    assert is_dominated(point2, point1, minimize) is True
    assert is_dominated(point1, point2, minimize) is False
    
    # Neither dominates (trade-off)
    point3 = {"cost": 10.0, "accuracy": 0.8}
    point4 = {"cost": 20.0, "accuracy": 0.9}
    
    assert is_dominated(point3, point4, minimize) is False
    assert is_dominated(point4, point3, minimize) is False


def test_compute_pareto_frontier():
    """Test Pareto frontier computation."""
    candidates = [
        CandidateMetrics(
            candidate_id="c1",
            objectives={
                "cost": Objective(name="cost", value=10.0),
                "accuracy": Objective(name="accuracy", value=0.9),
            },
        ),
        CandidateMetrics(
            candidate_id="c2",
            objectives={
                "cost": Objective(name="cost", value=20.0),
                "accuracy": Objective(name="accuracy", value=0.8),
            },
        ),
        CandidateMetrics(
            candidate_id="c3",
            objectives={
                "cost": Objective(name="cost", value=15.0),
                "accuracy": Objective(name="accuracy", value=0.95),
            },
        ),
    ]
    
    objectives = ["cost", "accuracy"]
    minimize = {"cost": True, "accuracy": False}
    
    frontier = compute_pareto_frontier(candidates, objectives, minimize)
    
    # c1 and c3 should be Pareto-optimal (c2 is dominated by c1, so not in frontier)
    optimal_ids = [p.candidate_id for p in frontier if not p.dominated]
    assert len(optimal_ids) == 2
    assert "c1" in optimal_ids
    assert "c3" in optimal_ids
    # c2 should not be in frontier (dominated by c1)
    assert "c2" not in optimal_ids


def test_compute_weighted_sum_score():
    """Test weighted sum score computation."""
    candidate = CandidateMetrics(
        candidate_id="c1",
        objectives={
            "cost": Objective(name="cost", value=10.0),
            "accuracy": Objective(name="accuracy", value=0.9),
        },
    )
    
    objectives = ["cost", "accuracy"]
    weights = {"cost": 0.3, "accuracy": 0.7}
    minimize = {"cost": True, "accuracy": False}
    
    score = compute_weighted_sum_score(candidate, objectives, weights, minimize)
    
    assert isinstance(score, float)
    # Score can be positive or negative depending on normalization
    assert not (score != score)  # Check it's not NaN


def test_analyze_trade_offs():
    """Test trade-off analysis."""
    candidates = [
        CandidateMetrics(
            candidate_id="c1",
            objectives={
                "cost": Objective(name="cost", value=10.0),
                "accuracy": Objective(name="accuracy", value=0.9),
            },
        ),
        CandidateMetrics(
            candidate_id="c2",
            objectives={
                "cost": Objective(name="cost", value=20.0),
                "accuracy": Objective(name="accuracy", value=0.8),
            },
        ),
    ]
    
    config = MultiObjectiveConfig(
        objectives=["cost", "accuracy"],
        minimize={"cost": True, "accuracy": False},
        weights={"cost": 0.5, "accuracy": 0.5},
        use_pareto=True,
        use_weighted_sum=True,
    )
    
    analysis = analyze_trade_offs(candidates, config)
    
    assert "pareto_frontier" in analysis
    assert "pareto_optimal" in analysis
    assert "weighted_scores" in analysis
    assert "trade_off_matrix" in analysis
    # c2 is dominated by c1 (lower cost AND higher accuracy), so only c1 is in frontier
    assert len(analysis["pareto_frontier"]) == 1
    assert analysis["pareto_frontier"][0]["candidate_id"] == "c1"
    assert "c1" in analysis["weighted_scores"]
    assert "c2" in analysis["weighted_scores"]


def test_multi_criteria_gate():
    """Test multi-criteria gating decision."""
    candidate = CandidateMetrics(
        candidate_id="c1",
        objectives={
            "cost": Objective(name="cost", value=10.0),
            "accuracy": Objective(name="accuracy", value=0.9),
        },
    )
    
    config = MultiObjectiveConfig(
        objectives=["cost", "accuracy"],
        minimize={"cost": True, "accuracy": False},
        thresholds={"cost": 15.0, "accuracy": 0.8},
    )
    
    adopt, reason, details = multi_criteria_gate(candidate, config)
    
    assert isinstance(adopt, bool)
    assert isinstance(reason, str)
    assert isinstance(details, dict)
    # Should adopt since cost < 15 and accuracy > 0.8
    assert adopt is True


def test_multi_criteria_gate_fails_threshold():
    """Test multi-criteria gate when thresholds are not met."""
    candidate = CandidateMetrics(
        candidate_id="c1",
        objectives={
            "cost": Objective(name="cost", value=20.0),
            "accuracy": Objective(name="accuracy", value=0.7),
        },
    )
    
    config = MultiObjectiveConfig(
        objectives=["cost", "accuracy"],
        minimize={"cost": True, "accuracy": False},
        thresholds={"cost": 15.0, "accuracy": 0.8},
    )
    
    adopt, reason, details = multi_criteria_gate(candidate, config)
    
    # Should not adopt since cost > 15 or accuracy < 0.8
    assert adopt is False
    assert "threshold" in reason.lower() or "cost" in reason.lower() or "accuracy" in reason.lower()


def test_recommend_candidate():
    """Test candidate recommendation."""
    candidates = [
        CandidateMetrics(
            candidate_id="c1",
            objectives={
                "cost": Objective(name="cost", value=10.0),
                "accuracy": Objective(name="accuracy", value=0.9),
            },
        ),
        CandidateMetrics(
            candidate_id="c2",
            objectives={
                "cost": Objective(name="cost", value=20.0),
                "accuracy": Objective(name="accuracy", value=0.8),
            },
        ),
    ]
    
    config = MultiObjectiveConfig(
        objectives=["cost", "accuracy"],
        minimize={"cost": True, "accuracy": False},
        weights={"cost": 0.5, "accuracy": 0.5},
        thresholds={"cost": 25.0, "accuracy": 0.7},
        use_weighted_sum=True,
    )
    
    recommended = recommend_candidate(candidates, config)
    
    assert recommended is not None
    assert recommended in ["c1", "c2"]
    # c1 should be recommended (lower cost, higher accuracy)
    assert recommended == "c1"


def test_recommend_candidate_no_valid():
    """Test recommendation when no candidate meets thresholds."""
    candidates = [
        CandidateMetrics(
            candidate_id="c1",
            objectives={
                "cost": Objective(name="cost", value=30.0),
                "accuracy": Objective(name="accuracy", value=0.6),
            },
        ),
    ]
    
    config = MultiObjectiveConfig(
        objectives=["cost", "accuracy"],
        minimize={"cost": True, "accuracy": False},
        thresholds={"cost": 15.0, "accuracy": 0.8},
    )
    
    recommended = recommend_candidate(candidates, config)
    
    assert recommended is None


def test_pareto_frontier_ranking():
    """Test that Pareto frontier correctly ranks points."""
    candidates = [
        CandidateMetrics(
            candidate_id="c1",
            objectives={
                "cost": Objective(name="cost", value=10.0),
                "accuracy": Objective(name="accuracy", value=0.9),
            },
        ),
        CandidateMetrics(
            candidate_id="c2",
            objectives={
                "cost": Objective(name="cost", value=20.0),
                "accuracy": Objective(name="accuracy", value=0.8),
            },
        ),
        CandidateMetrics(
            candidate_id="c3",
            objectives={
                "cost": Objective(name="cost", value=15.0),
                "accuracy": Objective(name="accuracy", value=0.85),
            },
        ),
    ]
    
    objectives = ["cost", "accuracy"]
    minimize = {"cost": True, "accuracy": False}
    
    frontier = compute_pareto_frontier(candidates, objectives, minimize)
    
    # Check that ranks are assigned
    ranks = [p.rank for p in frontier]
    assert all(isinstance(r, int) for r in ranks)
    # First front should have rank 0
    assert 0 in ranks


def test_weighted_sum_with_preferences():
    """Test weighted sum with user preferences."""
    candidates = [
        CandidateMetrics(
            candidate_id="c1",
            objectives={
                "cost": Objective(name="cost", value=10.0),
                "accuracy": Objective(name="accuracy", value=0.9),
            },
        ),
        CandidateMetrics(
            candidate_id="c2",
            objectives={
                "cost": Objective(name="cost", value=20.0),
                "accuracy": Objective(name="accuracy", value=0.95),
            },
        ),
    ]
    
    config = MultiObjectiveConfig(
        objectives=["cost", "accuracy"],
        minimize={"cost": True, "accuracy": False},
        weights={"cost": 0.5, "accuracy": 0.5},
        use_weighted_sum=True,
    )
    
    # Prefer accuracy over cost
    preferences = {"cost": 0.2, "accuracy": 0.8}
    
    recommended = recommend_candidate(candidates, config, preferences=preferences)
    
    assert recommended is not None
    # c1 has higher accuracy (0.9 vs 0.8) and lower cost, so it should be preferred
    assert recommended == "c1"


def test_trade_off_matrix():
    """Test trade-off matrix computation."""
    candidates = [
        CandidateMetrics(
            candidate_id="c1",
            objectives={
                "cost": Objective(name="cost", value=10.0),
                "accuracy": Objective(name="accuracy", value=0.9),
            },
        ),
        CandidateMetrics(
            candidate_id="c2",
            objectives={
                "cost": Objective(name="cost", value=20.0),
                "accuracy": Objective(name="accuracy", value=0.8),
            },
        ),
    ]
    
    config = MultiObjectiveConfig(
        objectives=["cost", "accuracy"],
        minimize={"cost": True, "accuracy": False},
    )
    
    analysis = analyze_trade_offs(candidates, config)
    
    assert "trade_off_matrix" in analysis
    matrix = analysis["trade_off_matrix"]
    assert "c1" in matrix
    assert "c2" in matrix["c1"]
    # Should show relative differences
    assert "cost" in matrix["c1"]["c2"]
    assert "accuracy" in matrix["c1"]["c2"]

