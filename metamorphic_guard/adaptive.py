"""
Adaptive testing support for Metamorphic Guard.

Implements adaptive sample size determination and early stopping based on
interim power analysis during evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .harness.statistics import estimate_power
from .power import calculate_sample_size


@dataclass
class AdaptiveConfig:
    """Configuration for adaptive testing."""
    enabled: bool = False
    min_sample_size: int = 50  # Minimum samples before first check
    check_interval: int = 50  # Check power every N samples
    power_threshold: float = 0.95  # Stop if power exceeds this
    max_sample_size: Optional[int] = None  # Maximum samples (None = no limit)
    early_stop_enabled: bool = True  # Allow early stopping


@dataclass
class AdaptiveDecision:
    """Decision from adaptive testing analysis."""
    continue_sampling: bool
    recommended_n: Optional[int]
    current_power: float
    reason: str


def should_continue_adaptive(
    baseline_metrics: Dict[str, Any],
    candidate_metrics: Dict[str, Any],
    current_n: int,
    *,
    alpha: float,
    min_delta: float,
    power_target: float,
    config: AdaptiveConfig,
) -> AdaptiveDecision:
    """
    Determine if sampling should continue based on interim results.
    
    Args:
        baseline_metrics: Interim baseline metrics (must have 'pass_rate' or 'passes'/'total')
        candidate_metrics: Interim candidate metrics (must have 'pass_rate' or 'passes'/'total')
        current_n: Current sample size
        alpha: Significance level
        min_delta: Minimum detectable effect
        power_target: Target power
        config: Adaptive testing configuration
        
    Returns:
        AdaptiveDecision with recommendation
    """
    if not config.enabled:
        return AdaptiveDecision(
            continue_sampling=True,
            recommended_n=None,
            current_power=0.0,
            reason="adaptive_testing_disabled",
        )
    
    # Check if we've reached minimum sample size
    if current_n < config.min_sample_size:
        return AdaptiveDecision(
            continue_sampling=True,
            recommended_n=None,
            current_power=0.0,
            reason=f"below_minimum_sample_size_{config.min_sample_size}",
        )
    
    # Check if we've exceeded maximum sample size
    if config.max_sample_size is not None and current_n >= config.max_sample_size:
        return AdaptiveDecision(
            continue_sampling=False,
            recommended_n=config.max_sample_size,
            current_power=0.0,
            reason=f"reached_maximum_sample_size_{config.max_sample_size}",
        )
    
    # Extract pass rates
    baseline_rate = baseline_metrics.get("pass_rate")
    if baseline_rate is None:
        baseline_passes = baseline_metrics.get("passes", 0)
        baseline_total = baseline_metrics.get("total", 0)
        baseline_rate = baseline_passes / baseline_total if baseline_total > 0 else 0.0
    
    candidate_rate = candidate_metrics.get("pass_rate")
    if candidate_rate is None:
        candidate_passes = candidate_metrics.get("passes", 0)
        candidate_total = candidate_metrics.get("total", 0)
        candidate_rate = candidate_passes / candidate_total if candidate_total > 0 else 0.0
    
    # Check if we have enough data for meaningful analysis
    if baseline_metrics.get("total", 0) < 10 or candidate_metrics.get("total", 0) < 10:
        return AdaptiveDecision(
            continue_sampling=True,
            recommended_n=None,
            current_power=0.0,
            reason="insufficient_data_for_analysis",
        )
    
    # Estimate current power
    current_power, recommended_n = estimate_power(
        p_baseline=baseline_rate,
        p_candidate=candidate_rate,
        sample_size=current_n,
        alpha_value=alpha,
        delta_value=min_delta,
        power_target=power_target,
    )
    
    # Decision logic
    if config.early_stop_enabled and current_power >= config.power_threshold:
        return AdaptiveDecision(
            continue_sampling=False,
            recommended_n=current_n,
            current_power=current_power,
            reason=f"sufficient_power_{current_power:.3f}",
        )
    
    # If recommended_n is available and higher than current, suggest increase
    if recommended_n is not None and recommended_n > current_n:
        # Cap at max_sample_size if set
        final_recommended = recommended_n
        if config.max_sample_size is not None:
            final_recommended = min(recommended_n, config.max_sample_size)
        
        return AdaptiveDecision(
            continue_sampling=True,
            recommended_n=final_recommended,
            current_power=current_power,
            reason=f"insufficient_power_{current_power:.3f}_recommend_{final_recommended}",
        )
    
    # Default: continue with current plan
    return AdaptiveDecision(
        continue_sampling=True,
        recommended_n=None,
        current_power=current_power,
        reason=f"continuing_power_{current_power:.3f}",
    )


def compute_interim_metrics(
    baseline_results: List[Dict[str, Any]],
    candidate_results: List[Dict[str, Any]],
    *,
    spec: Any,  # Spec type from specs module
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Compute interim metrics from partial results.
    
    Args:
        baseline_results: List of baseline results (may be partial)
        candidate_results: List of candidate results (may be partial)
        spec: Task specification
        
    Returns:
        Tuple of (baseline_metrics, candidate_metrics) dictionaries
    """
    # Count passes/failures
    baseline_passes = sum(1 for r in baseline_results if r.get("status") == "ok" and r.get("pass") is True)
    baseline_total = len(baseline_results)
    candidate_passes = sum(1 for r in candidate_results if r.get("status") == "ok" and r.get("pass") is True)
    candidate_total = len(candidate_results)
    
    baseline_rate = baseline_passes / baseline_total if baseline_total > 0 else 0.0
    candidate_rate = candidate_passes / candidate_total if candidate_total > 0 else 0.0
    
    # Compute pass indicators for statistical analysis
    baseline_indicators = [
        1 if (r.get("status") == "ok" and r.get("pass") is True) else 0
        for r in baseline_results
    ]
    candidate_indicators = [
        1 if (r.get("status") == "ok" and r.get("pass") is True) else 0
        for r in candidate_results
    ]
    
    return (
        {
            "passes": baseline_passes,
            "total": baseline_total,
            "pass_rate": baseline_rate,
            "pass_indicators": baseline_indicators,
        },
        {
            "passes": candidate_passes,
            "total": candidate_total,
            "pass_rate": candidate_rate,
            "pass_indicators": candidate_indicators,
        },
    )

