"""
Early stopping logic for adaptive testing.

This module implements statistical early stopping criteria to stop evaluation
when the decision is statistically clear, saving computation time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from .harness.statistics import PassRateMetrics
from .types import JSONDict


@dataclass
class EarlyStoppingConfig:
    """Configuration for early stopping."""
    
    enabled: bool = True
    method: str = "confidence"  # "confidence", "futility", "efficacy"
    confidence_threshold: float = 0.95
    futility_threshold: float = 0.01  # Stop if probability of success < 1%
    efficacy_threshold: float = 0.99  # Stop if probability of success > 99%
    min_samples: int = 50  # Minimum samples before considering stopping


@dataclass
class EarlyStoppingDecision:
    """Decision from early stopping analysis."""
    
    should_stop: bool
    reason: str
    confidence: float
    current_delta: float
    delta_ci: Tuple[float, float]


def check_confidence_stopping(
    baseline_metrics: PassRateMetrics,
    candidate_metrics: PassRateMetrics,
    delta_ci: Tuple[float, float],
    min_delta: float,
    config: EarlyStoppingConfig,
) -> EarlyStoppingDecision:
    """
    Check if we can stop early based on confidence interval.
    
    Stop if:
    - Lower CI bound > min_delta (clear improvement)
    - Upper CI bound < min_delta (clear rejection)
    
    Args:
        baseline_metrics: Baseline pass rate metrics
        candidate_metrics: Candidate pass rate metrics
        delta_ci: Confidence interval for delta
        min_delta: Minimum required improvement
        config: Early stopping configuration
    
    Returns:
        Early stopping decision
    """
    if baseline_metrics["total"] < config.min_samples:
        return EarlyStoppingDecision(
            should_stop=False,
            reason="insufficient_samples",
            confidence=0.0,
            current_delta=candidate_metrics["pass_rate"] - baseline_metrics["pass_rate"],
            delta_ci=delta_ci,
        )
    
    lower_bound, upper_bound = delta_ci
    current_delta = candidate_metrics["pass_rate"] - baseline_metrics["pass_rate"]
    
    # Check if CI is entirely above min_delta (clear improvement)
    if lower_bound > min_delta:
        # Compute confidence that delta > min_delta
        # Approximate: distance from min_delta to lower_bound
        confidence = min(1.0, (lower_bound - min_delta) / (upper_bound - lower_bound + 0.001))
        
        if confidence >= config.confidence_threshold:
            return EarlyStoppingDecision(
                should_stop=True,
                reason="clear_improvement",
                confidence=confidence,
                current_delta=current_delta,
                delta_ci=delta_ci,
            )
    
    # Check if CI is entirely below min_delta (clear rejection)
    if upper_bound < min_delta:
        confidence = min(1.0, (min_delta - upper_bound) / (upper_bound - lower_bound + 0.001))
        
        if confidence >= config.confidence_threshold:
            return EarlyStoppingDecision(
                should_stop=True,
                reason="clear_rejection",
                confidence=confidence,
                current_delta=current_delta,
                delta_ci=delta_ci,
            )
    
    return EarlyStoppingDecision(
        should_stop=False,
        reason="uncertain",
        confidence=0.0,
        current_delta=current_delta,
        delta_ci=delta_ci,
    )


def check_futility_stopping(
    baseline_metrics: PassRateMetrics,
    candidate_metrics: PassRateMetrics,
    delta_ci: Tuple[float, float],
    min_delta: float,
    config: EarlyStoppingConfig,
) -> EarlyStoppingDecision:
    """
    Check if we can stop early due to futility.
    
    Stop if probability of eventual success is very low.
    
    Args:
        baseline_metrics: Baseline pass rate metrics
        candidate_metrics: Candidate pass rate metrics
        delta_ci: Confidence interval for delta
        min_delta: Minimum required improvement
        config: Early stopping configuration
    
    Returns:
        Early stopping decision
    """
    if baseline_metrics["total"] < config.min_samples:
        return EarlyStoppingDecision(
            should_stop=False,
            reason="insufficient_samples",
            confidence=0.0,
            current_delta=candidate_metrics["pass_rate"] - baseline_metrics["pass_rate"],
            delta_ci=delta_ci,
        )
    
    upper_bound = delta_ci[1]
    current_delta = candidate_metrics["pass_rate"] - baseline_metrics["pass_rate"]
    
    # If upper bound is well below min_delta, success is unlikely
    if upper_bound < min_delta * 0.5:  # Upper bound is less than half of required
        # Estimate probability of success
        # Simple heuristic: distance from upper_bound to min_delta
        gap = min_delta - upper_bound
        probability_success = max(0.0, 1.0 - gap / min_delta)
        
        if probability_success < config.futility_threshold:
            return EarlyStoppingDecision(
                should_stop=True,
                reason="futility",
                confidence=1.0 - probability_success,
                current_delta=current_delta,
                delta_ci=delta_ci,
            )
    
    return EarlyStoppingDecision(
        should_stop=False,
        reason="not_futile",
        confidence=0.0,
        current_delta=current_delta,
        delta_ci=delta_ci,
    )


def check_efficacy_stopping(
    baseline_metrics: PassRateMetrics,
    candidate_metrics: PassRateMetrics,
    delta_ci: Tuple[float, float],
    min_delta: float,
    config: EarlyStoppingConfig,
) -> EarlyStoppingDecision:
    """
    Check if we can stop early due to clear efficacy.
    
    Stop if probability of success is very high.
    
    Args:
        baseline_metrics: Baseline pass rate metrics
        candidate_metrics: Candidate pass rate metrics
        delta_ci: Confidence interval for delta
        min_delta: Minimum required improvement
        config: Early stopping configuration
    
    Returns:
        Early stopping decision
    """
    if baseline_metrics["total"] < config.min_samples:
        return EarlyStoppingDecision(
            should_stop=False,
            reason="insufficient_samples",
            confidence=0.0,
            current_delta=candidate_metrics["pass_rate"] - baseline_metrics["pass_rate"],
            delta_ci=delta_ci,
        )
    
    lower_bound = delta_ci[0]
    current_delta = candidate_metrics["pass_rate"] - baseline_metrics["pass_rate"]
    
    # If lower bound is well above min_delta, success is very likely
    if lower_bound > min_delta * 1.5:  # Lower bound is 50% above required
        # Estimate probability of success
        # Simple heuristic: distance from lower_bound to min_delta
        margin = lower_bound - min_delta
        probability_success = min(1.0, 0.5 + margin / min_delta)
        
        if probability_success > config.efficacy_threshold:
            return EarlyStoppingDecision(
                should_stop=True,
                reason="clear_efficacy",
                confidence=probability_success,
                current_delta=current_delta,
                delta_ci=delta_ci,
            )
    
    return EarlyStoppingDecision(
        should_stop=False,
        reason="not_clear",
        confidence=0.0,
        current_delta=current_delta,
        delta_ci=delta_ci,
    )


def should_stop_early(
    baseline_metrics: PassRateMetrics,
    candidate_metrics: PassRateMetrics,
    delta_ci: Tuple[float, float],
    min_delta: float,
    config: EarlyStoppingConfig,
) -> EarlyStoppingDecision:
    """
    Determine if evaluation should stop early.
    
    Args:
        baseline_metrics: Baseline pass rate metrics
        candidate_metrics: Candidate pass rate metrics
        delta_ci: Confidence interval for delta
        min_delta: Minimum required improvement
        config: Early stopping configuration
    
    Returns:
        Early stopping decision
    """
    if not config.enabled:
        return EarlyStoppingDecision(
            should_stop=False,
            reason="disabled",
            confidence=0.0,
            current_delta=candidate_metrics["pass_rate"] - baseline_metrics["pass_rate"],
            delta_ci=delta_ci,
        )
    
    if config.method == "confidence":
        return check_confidence_stopping(
            baseline_metrics, candidate_metrics, delta_ci, min_delta, config
        )
    elif config.method == "futility":
        return check_futility_stopping(
            baseline_metrics, candidate_metrics, delta_ci, min_delta, config
        )
    elif config.method == "efficacy":
        return check_efficacy_stopping(
            baseline_metrics, candidate_metrics, delta_ci, min_delta, config
        )
    elif config.method == "combined":
        # Check all methods
        confidence_decision = check_confidence_stopping(
            baseline_metrics, candidate_metrics, delta_ci, min_delta, config
        )
        if confidence_decision.should_stop:
            return confidence_decision
        
        futility_decision = check_futility_stopping(
            baseline_metrics, candidate_metrics, delta_ci, min_delta, config
        )
        if futility_decision.should_stop:
            return futility_decision
        
        efficacy_decision = check_efficacy_stopping(
            baseline_metrics, candidate_metrics, delta_ci, min_delta, config
        )
        if efficacy_decision.should_stop:
            return efficacy_decision
        
        return EarlyStoppingDecision(
            should_stop=False,
            reason="no_stopping_criteria_met",
            confidence=0.0,
            current_delta=candidate_metrics["pass_rate"] - baseline_metrics["pass_rate"],
            delta_ci=delta_ci,
        )
    else:
        return EarlyStoppingDecision(
            should_stop=False,
            reason="unknown_method",
            confidence=0.0,
            current_delta=candidate_metrics["pass_rate"] - baseline_metrics["pass_rate"],
            delta_ci=delta_ci,
        )

