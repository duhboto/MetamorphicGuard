"""Tests for confidence interval helpers."""

from __future__ import annotations

from metamorphic_guard.harness.statistics import compute_delta_ci


def _build_metrics(indicators, cluster=False):
    total = len(indicators)
    passes = sum(indicators)
    metrics = {
        "pass_indicators": indicators,
        "pass_rate": passes / total if total else 0.0,
        "passes": passes,
        "total": total,
    }
    if cluster:
        metrics["cluster_labels"] = [i // 5 for i in range(total)]
    else:
        metrics["cluster_labels"] = None
    return metrics


def test_bootstrap_bca_interval_contains_delta():
    baseline = [1] * 80 + [0] * 20
    candidate = [1] * 88 + [0] * 12
    baseline_metrics = _build_metrics(baseline)
    candidate_metrics = _build_metrics(candidate)

    ci = compute_delta_ci(
        baseline_metrics,
        candidate_metrics,
        alpha=0.05,
        seed=123,
        samples=2000,
        method="bootstrap_bca",
    )

    delta = candidate_metrics["pass_rate"] - baseline_metrics["pass_rate"]
    assert ci[0] <= delta <= ci[1]
    assert ci[0] < ci[1]


def test_bootstrap_cluster_bca_interval_contains_delta():
    baseline = [1] * 60 + [0] * 40
    candidate = [1] * 70 + [0] * 30
    baseline_metrics = _build_metrics(baseline, cluster=True)
    candidate_metrics = _build_metrics(candidate, cluster=True)

    ci = compute_delta_ci(
        baseline_metrics,
        candidate_metrics,
        alpha=0.05,
        seed=321,
        samples=2000,
        method="bootstrap_cluster_bca",
    )

    delta = candidate_metrics["pass_rate"] - baseline_metrics["pass_rate"]
    assert ci[0] <= delta <= ci[1]
    assert ci[0] < ci[1]
