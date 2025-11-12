"""
Tests for harness evaluation and bootstrap CI calculation.
"""

from pathlib import Path

import pytest

from metamorphic_guard.harness import (
    _compute_bootstrap_ci,
    _compute_delta_ci,
    _compute_relative_risk,
    _evaluate_results,
    run_eval,
)
from metamorphic_guard.specs import MetamorphicRelation, Property, Spec
from metamorphic_guard.stability import multiset_equal


def test_bootstrap_ci_calculation():
    """Test bootstrap confidence interval calculation."""
    # Test case where candidate is clearly better
    baseline_indicators = [1, 0, 1, 0, 1] * 20  # 60% pass rate
    candidate_indicators = [1, 1, 1, 0, 1] * 20  # 80% pass rate
    
    ci = _compute_bootstrap_ci(
        baseline_indicators,
        candidate_indicators,
        alpha=0.05,
        seed=123,
        samples=500,
    )
    
    assert len(ci) == 2
    assert ci[0] < ci[1]  # Lower bound < upper bound
    assert ci[0] > 0  # Should show improvement


def test_bootstrap_ci_no_improvement():
    """Test bootstrap CI when there's no improvement."""
    indicators = [1, 0, 1, 0, 1] * 20  # Same for both
    
    ci = _compute_bootstrap_ci(indicators, indicators, alpha=0.05, seed=321, samples=500)
    
    assert len(ci) == 2
    # CI should contain 0 (no improvement)
    assert ci[0] <= 0 <= ci[1]


def test_bootstrap_cluster_ci():
    """Cluster-aware bootstrap should handle grouped observations."""
    baseline = [1, 1, 0, 0] * 10
    candidate = [1, 1, 1, 0] * 10
    clusters = [0, 0, 1, 1] * 10

    ci = _compute_bootstrap_ci(
        baseline,
        candidate,
        alpha=0.1,
        seed=42,
        samples=200,
        clusters=clusters,
    )

    assert len(ci) == 2
    assert ci[0] <= ci[1]


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
    
    metrics = _evaluate_results(
        results,
        spec,
        test_inputs,
        violation_cap=10,
        role="candidate",
        seed=123,
        rerun=lambda args: {"success": True, "result": None},
    )
    
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
    
    metrics = _evaluate_results(
        results,
        spec,
        test_inputs,
        violation_cap=10,
        role="candidate",
        seed=123,
        rerun=lambda args: {"success": False, "error": "Timeout"},
    )
    
    assert metrics["passes"] == 0
    assert metrics["total"] == 1
    assert metrics["pass_rate"] == 0.0


def test_evaluate_results_cluster_labels():
    """Cluster labels should follow spec.cluster_key."""
    spec = Spec(
        gen_inputs=lambda n, seed: [(0, 1), (1, 1), (2, 1)],
        properties=[
            Property(
                check=lambda out, x, y: out == x + y,
                description="Sum property"
            )
        ],
        relations=[],
        equivalence=multiset_equal,
        cluster_key=lambda args: args[0] % 2,
    )

    results = [
        {"success": True, "result": 1},
        {"success": True, "result": 2},
        {"success": True, "result": 3},
    ]

    metrics = _evaluate_results(
        results,
        spec,
        spec.gen_inputs(3, 0),
        violation_cap=5,
        role="baseline",
        seed=0,
        rerun=lambda args: {"success": True, "result": None},
    )

    assert metrics["cluster_labels"] == [0, 1, 0]


def test_metamorphic_relation_violations_detected():
    """Ensure metamorphic relations are re-run and violations recorded."""
    inputs = [([3, 1, 2], 2)]

    spec = Spec(
        gen_inputs=lambda n, seed: inputs,
        properties=[
            Property(
                check=lambda out, L, k: True,
                description="Always passes",
            )
        ],
        relations=[
            MetamorphicRelation(
                name="permute",
                transform=lambda L, k: (list(reversed(L)), k),
            )
        ],
        equivalence=lambda a, b: a == b,
    )

    run_results = [{"success": True, "result": [3, 2]}]

    def rerun(_args):
        return {"success": True, "result": [1, 2]}  # Different order to trigger failure

    metrics = _evaluate_results(
        run_results,
        spec,
        inputs,
        violation_cap=5,
        role="candidate",
        seed=321,
        rerun=rerun,
    )

    assert metrics["passes"] == 0
    assert metrics["pass_indicators"] == [0]
    assert metrics["mr_violations"], "Expected metamorphic relation violation to be recorded"


def test_relation_rng_injection():
    """Metamorphic relations flagged as seeded receive deterministic RNGs."""
    calls: list[float] = []

    def transform(value: int, *, rng):
        calls.append(rng.random())
        return (value,)

    inputs = [(1,), (2,)]
    spec = Spec(
        gen_inputs=lambda n, seed: inputs,
        properties=[
            Property(
                check=lambda out, original: True,
                description="Always passes",
            )
        ],
        relations=[
            MetamorphicRelation(
                name="rng_relation",
                transform=transform,
                expect="equal",
                accepts_rng=True,
            )
        ],
        equivalence=lambda a, b: a == b,
    )

    results = [{"success": True, "result": (1,)}, {"success": True, "result": (2,)}]

    _evaluate_results(
        results,
        spec,
        inputs,
        violation_cap=5,
        role="candidate",
        seed=123,
        rerun=lambda args: {"success": True, "result": args},
    )
    first_calls = list(calls)

    calls.clear()
    _evaluate_results(
        results,
        spec,
        inputs,
        violation_cap=5,
        role="candidate",
        seed=123,
        rerun=lambda args: {"success": True, "result": args},
    )

    assert calls == first_calls


def test_relation_rerun_cache():
    """Identical transformed inputs should reuse sandbox results."""
    call_counter = {"count": 0}

    def transform(value: int):
        return (value,)

    def rerun(args):
        call_counter["count"] += 1
        return {"success": True, "result": args}

    inputs = [(1,), (1,)]
    spec = Spec(
        gen_inputs=lambda n, seed: inputs,
        properties=[
            Property(
                check=lambda out, original: True,
                description="Always passes",
            )
        ],
        relations=[
            MetamorphicRelation(
                name="identity",
                transform=transform,
            )
        ],
        equivalence=lambda a, b: a == b,
    )

    results = [{"success": True, "result": (1,)}, {"success": True, "result": (1,)}]

    _evaluate_results(
        results,
        spec,
        inputs,
        violation_cap=5,
        role="candidate",
        seed=0,
        rerun=rerun,
    )

    assert call_counter["count"] == 1


def test_run_eval_applies_relation_correction_holm():
    repo_root = Path(__file__).resolve().parents[1]
    baseline = repo_root / "examples" / "top_k_baseline.py"
    candidate = repo_root / "examples" / "top_k_improved.py"

    result = run_eval(
        task_name="top_k",
        baseline_path=str(baseline),
        candidate_path=str(candidate),
        n=12,
        seed=7,
        bootstrap_samples=200,
        relation_correction="holm",
    )

    coverage = result.get("relation_coverage")
    assert coverage is not None
    correction = coverage.get("correction")
    assert correction is not None
    assert correction["method"] == "holm-bonferroni"
    assert correction["alpha"] == pytest.approx(0.05)

    for relation in coverage["relations"]:
        assert "p_value" in relation
        assert "adjusted_p_value" in relation
        assert "significant" in relation
def test_newcombe_ci_difference():
    baseline_metrics = {
        "passes": 60,
        "total": 100,
        "pass_indicators": [1] * 60 + [0] * 40,
    }
    candidate_metrics = {
        "passes": 90,
        "total": 100,
        "pass_indicators": [1] * 90 + [0] * 10,
    }

    ci = _compute_delta_ci(
        baseline_metrics,
        candidate_metrics,
        alpha=0.05,
        seed=123,
        samples=500,
        method="newcombe",
    )

    assert ci[0] < ci[1]
    assert ci[0] > 0

    rr, rr_ci = _compute_relative_risk(
        baseline_metrics,
        candidate_metrics,
        alpha=0.05,
        method="log",
    )

    assert rr > 1
    assert rr_ci[0] < rr_ci[1]
