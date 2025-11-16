"""
Simulation-oriented tests for statistical routines.
"""

from __future__ import annotations

import os
import random

import pytest

from metamorphic_guard.harness.statistics import compute_delta_ci, estimate_power
from metamorphic_guard.sequential_testing import (
    SequentialTestConfig,
    apply_sequential_correction,
)


def _build_metrics(indicators):
    total = len(indicators)
    passes = sum(indicators)
    return {
        "pass_indicators": indicators,
        "pass_rate": passes / total if total else 0.0,
        "passes": passes,
        "total": total,
        "cluster_labels": None,
    }


def _simulate_binomial(rng: random.Random, n: int, p: float):
    return [1 if rng.random() < p else 0 for _ in range(n)]


def test_bootstrap_ci_empirical_coverage():
    """
    Empirical coverage for the bootstrap CI should fall near the nominal rate.
    """

    seed = int(os.environ.get("MG_CI_RUNS", "120"))
    rng = random.Random(1337)
    runs = max(30, seed)
    n = 80
    p_baseline = 0.78
    p_candidate = 0.83
    true_delta = p_candidate - p_baseline

    coverage_hits = 0
    for _ in range(runs):
        baseline = _simulate_binomial(rng, n, p_baseline)
        candidate = _simulate_binomial(rng, n, p_candidate)
        baseline_metrics = _build_metrics(baseline)
        candidate_metrics = _build_metrics(candidate)
        ci = compute_delta_ci(
            baseline_metrics,
            candidate_metrics,
            alpha=0.05,
            seed=rng.randrange(1_000_000),
            samples=250,
            method="bootstrap",
        )
        if ci[0] <= true_delta <= ci[1]:
            coverage_hits += 1

    coverage = coverage_hits / runs
    tolerance = float(os.environ.get("MG_CI_TOLERANCE", "0.12"))
    assert (1 - tolerance) <= coverage <= 1.0, coverage
    min_threshold = os.environ.get("MG_CI_MIN_COVERAGE")
    if min_threshold is not None:
        threshold = float(min_threshold)
        assert coverage >= threshold, f"coverage {coverage:.3f} < threshold {threshold:.3f}"


def test_sequential_correction_expands_interval():
    baseline = [1] * 70 + [0] * 30
    candidate = [1] * 76 + [0] * 24
    baseline_metrics = _build_metrics(baseline)
    candidate_metrics = _build_metrics(candidate)

    original_ci = compute_delta_ci(
        baseline_metrics,
        candidate_metrics,
        alpha=0.05,
        seed=0,
        samples=0,
        method="newcombe",
    )

    config = SequentialTestConfig(
        method="pocock",
        alpha=0.05,
        max_looks=3,
        look_number=2,
    )

    def _recompute(new_alpha: float):
        return compute_delta_ci(
            baseline_metrics,
            candidate_metrics,
            alpha=new_alpha,
            seed=0,
            samples=0,
            method="newcombe",
        )

    adjusted_ci, effective_alpha = apply_sequential_correction(
        original_ci,
        config,
        recompute_ci=_recompute,
    )

    assert effective_alpha == pytest.approx(0.05 / 3, rel=1e-3)
    assert adjusted_ci[0] <= original_ci[0]
    assert adjusted_ci[1] >= original_ci[1]


def test_power_estimate_monotonic_with_threshold():
    p_baseline = 0.75
    p_candidate = 0.82
    sample_size = 200

    power_lo, n_lo = estimate_power(
        p_baseline,
        p_candidate,
        sample_size,
        alpha_value=0.05,
        delta_value=0.01,
        power_target=0.8,
    )
    power_hi, n_hi = estimate_power(
        p_baseline,
        p_candidate,
        sample_size,
        alpha_value=0.05,
        delta_value=0.05,
        power_target=0.8,
    )

    assert 0.0 <= power_lo <= 1.0
    assert 0.0 <= power_hi <= 1.0
    assert power_lo > power_hi  # Harder thresholds reduce observed power.
    assert n_hi is None or n_lo is None or n_lo >= n_hi

