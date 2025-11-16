"""
Harness module for running evaluations and computing statistical analysis.

This module has been refactored from a monolithic harness.py into smaller,
focused modules for better maintainability.
"""

from .statistics import (
    compute_delta_ci,
    compute_paired_stats,
    estimate_power,
    compute_bootstrap_ci,
    compute_relative_risk,
)
from .execution import (
    ExecutionPlan,
    build_call_spec,
    execute_implementations,
    prepare_execution_plan,
    relation_cache_key,
    relation_rng,
)
from .reporting import (
    aggregate_metric_values,
    bootstrap_metric_delta,
    collect_metrics,
    compose_llm_metrics,
    evaluate_results,
    evaluate_roles,
    get_or_compute_metric_value,
    safe_extract_metric,
    should_sample_metric,
    summarize_llm_results,
    summarize_relations,
)
from .trust import compute_trust_scores

# Backward compatibility aliases for private functions (used by tests)
_compute_delta_ci = compute_delta_ci
_estimate_power = estimate_power
_collect_metrics = collect_metrics
_compute_bootstrap_ci = compute_bootstrap_ci
_compute_relative_risk = compute_relative_risk
_compose_llm_metrics = compose_llm_metrics
_evaluate_results = evaluate_results
_summarize_llm_results = summarize_llm_results

# Import run_eval from evaluation module
from .evaluation import run_eval

__all__ = [
    # Statistics
    "compute_delta_ci",
    "compute_paired_stats",
    "estimate_power",
    # Execution
    "ExecutionPlan",
    "build_call_spec",
    "execute_implementations",
    "prepare_execution_plan",
    "relation_cache_key",
    "relation_rng",
    # Reporting
    "evaluate_roles",
    "aggregate_metric_values",
    "bootstrap_metric_delta",
    "collect_metrics",
    "compose_llm_metrics",
    "evaluate_results",
    "get_or_compute_metric_value",
    "safe_extract_metric",
    "should_sample_metric",
    "summarize_llm_results",
    "summarize_relations",
    # Trust
    "compute_trust_scores",
    # Main entry point (from evaluation module)
    "run_eval",
    # Backward compatibility aliases for private functions (used by tests)
    "_compute_delta_ci",
    "_estimate_power",
    "_collect_metrics",
    "_compute_bootstrap_ci",
    "_compute_relative_risk",
    "_compose_llm_metrics",
    "_evaluate_results",
    "_summarize_llm_results",
]

