"""
Benchmark regression suites for validating statistics engine.

These suites produce known lifts (positive/negative) to ensure the statistics
engine correctly computes confidence intervals and makes adoption decisions.
"""

import tempfile
from pathlib import Path

import pytest

from metamorphic_guard.harness import run_eval


@pytest.fixture
def benchmark_dir(tmp_path):
    """Create temporary directory for benchmark files."""
    return tmp_path


def create_benchmark_impls(baseline_pass_rate: float, candidate_pass_rate: float, tmp_dir: Path):
    """Create baseline and candidate implementations with specified pass rates."""
    baseline = tmp_dir / "baseline.py"
    candidate = tmp_dir / "candidate.py"
    
    # Create implementations that fail MR checks deterministically
    # Use sum of list elements modulo 100 to determine failure
    baseline_fail_threshold = int(100 * (1 - baseline_pass_rate))
    candidate_fail_threshold = int(100 * (1 - candidate_pass_rate))
    
    baseline.write_text(f"""
def solve(L, k):
    if not L or k <= 0:
        return []
    # Fail MR check for cases where sum(L) % 100 < threshold
    # This creates deterministic failures based on input
    case_key = (sum(L) if L else 0) % 100
    if case_key < {baseline_fail_threshold}:
        # Return ascending instead of descending to fail MR
        return sorted(L)[:min(k, len(L))]
    return sorted(L, reverse=True)[:min(k, len(L))]
""", encoding="utf-8")
    
    candidate.write_text(f"""
def solve(L, k):
    if not L or k <= 0:
        return []
    # Fail MR check for cases where sum(L) % 100 < threshold
    case_key = (sum(L) if L else 0) % 100
    if case_key < {candidate_fail_threshold}:
        # Return ascending instead of descending to fail MR
        return sorted(L)[:min(k, len(L))]
    return sorted(L, reverse=True)[:min(k, len(L))]
""", encoding="utf-8")
    
    return baseline, candidate


def test_benchmark_positive_lift(benchmark_dir):
    """Test that positive lift is correctly detected and adopted."""
    baseline, candidate = create_benchmark_impls(0.70, 0.85, benchmark_dir)
    
    result = run_eval(
        task_name="top_k",
        baseline_path=str(baseline),
        candidate_path=str(candidate),
        n=200,  # Increase n for more stable results
        seed=42,
        improve_delta=0.05,  # Expect ~0.15 improvement
        min_pass_rate=0.70,  # Lower threshold since we're testing MR failures
        ci_method="newcombe",
    )
    
    # Should detect improvement (delta > 0)
    assert result["delta_pass_rate"] > 0.05  # At least 5% improvement
    # Decision may vary based on CI, but should generally adopt with large improvement
    delta_ci = result.get("delta_ci", [0, 0])
    if delta_ci[0] >= 0.05:
        assert result["decision"]["adopt"] is True


def test_benchmark_negative_lift(benchmark_dir):
    """Test that negative lift is correctly detected and rejected."""
    baseline, candidate = create_benchmark_impls(0.85, 0.70, benchmark_dir)
    
    result = run_eval(
        task_name="top_k",
        baseline_path=str(baseline),
        candidate_path=str(candidate),
        n=200,  # Increase n for more stable results
        seed=42,
        improve_delta=0.02,
        min_pass_rate=0.70,  # Lower threshold
        ci_method="newcombe",
    )
    
    # Should detect regression (delta < 0)
    assert result["delta_pass_rate"] < -0.05  # At least 5% regression
    assert result["decision"]["adopt"] is False
    # Should reject due to low pass rate, negative delta, or violations
    reason = result["decision"]["reason"].lower()
    assert any(keyword in reason for keyword in ["low", "insufficient", "violation", "regression"])


def test_benchmark_no_change(benchmark_dir):
    """Test that equivalent implementations produce delta near zero."""
    baseline, candidate = create_benchmark_impls(0.80, 0.80, benchmark_dir)
    
    result = run_eval(
        task_name="top_k",
        baseline_path=str(baseline),
        candidate_path=str(candidate),
        n=100,
        seed=42,
        improve_delta=0.02,
        min_pass_rate=0.75,
        ci_method="newcombe",
    )
    
    # Delta should be near zero
    assert abs(result["delta_pass_rate"]) < 0.05
    # CI should contain zero
    delta_ci = result.get("delta_ci", [0, 0])
    assert delta_ci[0] <= 0 <= delta_ci[1]


def test_benchmark_small_positive_lift(benchmark_dir):
    """Test that small positive lift below threshold is correctly handled."""
    baseline, candidate = create_benchmark_impls(0.80, 0.82, benchmark_dir)
    
    result = run_eval(
        task_name="top_k",
        baseline_path=str(baseline),
        candidate_path=str(candidate),
        n=300,  # Increase n for more stable results
        seed=42,
        improve_delta=0.05,  # Require 5% improvement
        min_pass_rate=0.70,
        ci_method="newcombe",
    )
    
    # Small improvement (~2%) should be rejected if threshold is 5%
    delta_ci = result.get("delta_ci", [0, 0])
    if delta_ci[0] < 0.05:
        assert result["decision"]["adopt"] is False
        reason = result["decision"]["reason"].lower()
        assert any(keyword in reason for keyword in ["insufficient", "violation", "low"])


def test_benchmark_bootstrap_consistency(benchmark_dir):
    """Test that bootstrap CI produces consistent results."""
    baseline, candidate = create_benchmark_impls(0.75, 0.85, benchmark_dir)
    
    results = []
    for seed in range(42, 47):  # 5 different seeds
        result = run_eval(
            task_name="top_k",
            baseline_path=str(baseline),
            candidate_path=str(candidate),
            n=200,  # Increase n for stability
            seed=seed,
            improve_delta=0.02,
            min_pass_rate=0.70,
            ci_method="bootstrap",
            bootstrap_samples=500,
        )
        results.append(result)
    
    # Most runs should adopt (positive lift)
    adopt_count = sum(1 for r in results if r["decision"]["adopt"])
    assert adopt_count >= 3  # At least 3/5 should adopt (allowing for variance)
    
    # Delta pass rates should be positive and similar across seeds
    deltas = [r["delta_pass_rate"] for r in results]
    delta_mean = sum(deltas) / len(deltas)
    assert delta_mean > 0.05  # Should be positive


def test_benchmark_cluster_bootstrap(benchmark_dir):
    """Test cluster bootstrap with known cluster structure."""
    baseline, candidate = create_benchmark_impls(0.75, 0.85, benchmark_dir)
    
    result = run_eval(
        task_name="top_k",
        baseline_path=str(baseline),
        candidate_path=str(candidate),
        n=200,  # Increase n for stability
        seed=42,
        improve_delta=0.02,
        min_pass_rate=0.70,
        ci_method="bootstrap-cluster",
        bootstrap_samples=500,
    )
    
    # Should detect positive lift with cluster bootstrap
    assert result["delta_pass_rate"] > 0.05
    # Decision depends on CI, but with large improvement should generally adopt
    delta_ci = result.get("delta_ci", [0, 0])
    if delta_ci[0] >= 0.02:
        assert result["decision"]["adopt"] is True

