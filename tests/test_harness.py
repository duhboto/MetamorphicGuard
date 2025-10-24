"""
Tests for harness evaluation and bootstrap CI calculation.
"""

import pytest
import numpy as np
from metamorphic_guard.harness import _compute_bootstrap_ci, _evaluate_results
from metamorphic_guard.specs import Spec, Property, MetamorphicRelation
from metamorphic_guard.stability import multiset_equal


def test_bootstrap_ci_calculation():
    """Test bootstrap confidence interval calculation."""
    # Test case where candidate is clearly better
    baseline_indicators = [1, 0, 1, 0, 1] * 20  # 60% pass rate
    candidate_indicators = [1, 1, 1, 0, 1] * 20  # 80% pass rate
    
    ci = _compute_bootstrap_ci(baseline_indicators, candidate_indicators, alpha=0.05)
    
    assert len(ci) == 2
    assert ci[0] < ci[1]  # Lower bound < upper bound
    assert ci[0] > 0  # Should show improvement


def test_bootstrap_ci_no_improvement():
    """Test bootstrap CI when there's no improvement."""
    indicators = [1, 0, 1, 0, 1] * 20  # Same for both
    
    ci = _compute_bootstrap_ci(indicators, indicators, alpha=0.05)
    
    assert len(ci) == 2
    # CI should contain 0 (no improvement)
    assert ci[0] <= 0 <= ci[1]


def test_evaluate_results():
    """Test result evaluation against properties."""
    # Create a simple spec
    spec = Spec(
        gen_inputs=lambda n, seed: [(1, 2), (3, 4)],
        properties=[
            Property(
                check=lambda out, x, y: out == x + y,
                description="Sum property"
            )
        ],
        relations=[],
        equivalence=multiset_equal
    )
    
    # Mock results
    results = [
        {"success": True, "result": 3},  # 1 + 2 = 3 ✓
        {"success": True, "result": 8}   # 3 + 4 = 7, but result is 8 ✗
    ]
    test_inputs = [(1, 2), (3, 4)]
    
    metrics = _evaluate_results(results, spec, test_inputs, violation_cap=10)
    
    assert metrics["passes"] == 1
    assert metrics["total"] == 2
    assert metrics["pass_rate"] == 0.5
    assert len(metrics["prop_violations"]) == 1
    assert metrics["prop_violations"][0]["test_case"] == 1


def test_evaluate_results_failure_handling():
    """Test evaluation handles execution failures."""
    spec = Spec(
        gen_inputs=lambda n, seed: [(1, 2)],
        properties=[
            Property(
                check=lambda out, x, y: out == x + y,
                description="Sum property"
            )
        ],
        relations=[],
        equivalence=multiset_equal
    )
    
    # Mock results with failures
    results = [
        {"success": False, "result": None, "error": "Timeout"}
    ]
    test_inputs = [(1, 2)]
    
    metrics = _evaluate_results(results, spec, test_inputs, violation_cap=10)
    
    assert metrics["passes"] == 0
    assert metrics["total"] == 1
    assert metrics["pass_rate"] == 0.0
