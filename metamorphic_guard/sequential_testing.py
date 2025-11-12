"""
Sequential testing support for iterative PR workflows.

Implements alpha-spending and sequential probability ratio test (SPRT) methods
to control false-positive rates when gates are re-run multiple times within
a PR or across multiple PRs.

Alpha-spending methods:
- Pocock: Equal spending at each look
- O'Brien-Fleming: More conservative early, less conservative later
- Custom spending functions

SPRT: Sequential Probability Ratio Test for early stopping.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from statistics import NormalDist


@dataclass
class SequentialTestConfig:
    """Configuration for sequential testing."""
    method: str = "pocock"  # "pocock", "obrien-fleming", "sprt", "none"
    alpha: float = 0.05
    max_looks: int = 5  # Maximum number of looks/interim analyses
    look_number: int = 1  # Current look number (1-indexed)
    effect_size: Optional[float] = None  # For SPRT: expected effect size
    power: float = 0.8  # For SPRT: desired power


def pocock_bound(alpha: float, max_looks: int, look_number: int) -> float:
    """
    Compute Pocock boundary for sequential testing.
    
    Equal spending at each look. More conservative than fixed alpha.
    
    Args:
        alpha: Overall significance level
        max_looks: Maximum number of looks
        look_number: Current look number (1-indexed)
        
    Returns:
        Adjusted alpha for this look
    """
    if look_number > max_looks:
        raise ValueError(f"look_number ({look_number}) exceeds max_looks ({max_looks})")
    
    # Pocock: equal spending at each look
    # Approximate formula: alpha_k ≈ alpha / max_looks (conservative)
    # More accurate: solve iteratively, but this approximation is common
    if max_looks == 1:
        return alpha
    
    # Simple approximation (conservative)
    return alpha / max_looks


def obrien_fleming_bound(alpha: float, max_looks: int, look_number: int) -> float:
    """
    Compute O'Brien-Fleming boundary for sequential testing.
    
    More conservative early, less conservative later.
    
    Args:
        alpha: Overall significance level
        max_looks: Maximum number of looks
        look_number: Current look number (1-indexed)
        
    Returns:
        Adjusted alpha for this look
    """
    if look_number > max_looks:
        raise ValueError(f"look_number ({look_number}) exceeds max_looks ({max_looks})")
    
    if max_looks == 1:
        return alpha
    
    # O'Brien-Fleming: early looks are very conservative
    # Boundary scales as sqrt(max_looks / look_number)
    # For alpha spending, we use a conservative approximation
    z_alpha_overall = NormalDist().inv_cdf(1 - alpha / 2)
    z_boundary = z_alpha_overall * math.sqrt(max_looks / look_number)
    adjusted_alpha = 2 * (1 - NormalDist().cdf(z_boundary))
    
    return min(alpha, adjusted_alpha)


def compute_sequential_alpha(
    config: SequentialTestConfig,
    look_number: Optional[int] = None,
) -> float:
    """
    Compute adjusted alpha for sequential testing.
    
    Args:
        config: Sequential test configuration
        look_number: Override look number from config
        
    Returns:
        Adjusted alpha for this look
    """
    look = look_number if look_number is not None else config.look_number
    
    if config.method == "none" or config.max_looks == 1:
        return config.alpha
    
    if config.method == "pocock":
        return pocock_bound(config.alpha, config.max_looks, look)
    elif config.method == "obrien-fleming":
        return obrien_fleming_bound(config.alpha, config.max_looks, look)
    else:
        raise ValueError(f"Unknown sequential test method: {config.method}")


def sprt_boundary(
    alpha: float,
    beta: float,
    effect_size: float,
    baseline_rate: float,
    sample_size: int,
) -> Tuple[float, float]:
    """
    Compute SPRT (Sequential Probability Ratio Test) boundaries.
    
    Returns (lower_bound, upper_bound) for test statistic.
    If test statistic < lower_bound: accept null (no improvement)
    If test statistic > upper_bound: accept alternative (improvement)
    Otherwise: continue sampling
    
    Args:
        alpha: Type I error rate
        beta: Type II error rate (1 - power)
        effect_size: Expected improvement (delta)
        baseline_rate: Baseline pass rate
        sample_size: Current sample size
        
    Returns:
        (lower_bound, upper_bound) for test statistic
    """
    if effect_size <= 0:
        raise ValueError("effect_size must be positive")
    
    p0 = baseline_rate
    p1 = min(1.0, baseline_rate + effect_size)
    
    # Log-likelihood ratio boundaries
    log_A = math.log((1 - beta) / alpha)
    log_B = math.log(beta / (1 - alpha))
    
    # For binomial, approximate boundaries
    # More sophisticated implementation would track running sum
    # This is a simplified version
    
    # Approximate using normal approximation
    n = sample_size
    if n == 0:
        return (-float("inf"), float("inf"))
    
    # Variance under null and alternative
    var0 = p0 * (1 - p0) / n
    var1 = p1 * (1 - p1) / n
    
    # Simplified boundaries (would need full SPRT implementation for production)
    # This provides a framework
    z_alpha = NormalDist().inv_cdf(1 - alpha / 2)
    z_beta = NormalDist().inv_cdf(1 - beta)
    
    se = math.sqrt(var0)
    lower = p0 - z_alpha * se
    upper = p1 + z_beta * math.sqrt(var1)
    
    return (lower, upper)


def should_continue_sprt(
    observed_rate: float,
    baseline_rate: float,
    effect_size: float,
    alpha: float,
    beta: float,
    sample_size: int,
) -> Tuple[bool, str]:
    """
    Determine if SPRT should continue sampling.
    
    Args:
        observed_rate: Current observed pass rate
        baseline_rate: Baseline pass rate
        effect_size: Expected improvement
        alpha: Type I error rate
        beta: Type II error rate
        sample_size: Current sample size
        
    Returns:
        (should_continue, reason) tuple
    """
    lower, upper = sprt_boundary(alpha, beta, effect_size, baseline_rate, sample_size)
    
    if observed_rate < lower:
        return (False, "reject_null")  # No improvement
    elif observed_rate > upper:
        return (False, "accept_alternative")  # Improvement detected
    else:
        return (True, "continue")  # Need more data


def apply_sequential_correction(
    delta_ci: List[float],
    config: SequentialTestConfig,
    look_number: Optional[int] = None,
    *,
    recompute_ci: Optional[Callable[[float], List[float]]] = None,
) -> Tuple[List[float], float]:
    """
    Apply sequential testing correction to confidence interval.
    
    Args:
        delta_ci: Original confidence interval [lower, upper]
        config: Sequential test configuration
        look_number: Override look number
        
    Args:
        delta_ci: Original confidence interval [lower, upper]
        config: Sequential test configuration
        look_number: Override look number
        recompute_ci: Callable that recomputes the CI given an adjusted alpha

    Returns:
        (adjusted_ci, adjusted_alpha) tuple
    """
    if config.method == "none" or config.max_looks == 1:
        return (delta_ci, config.alpha)
    
    adjusted_alpha = compute_sequential_alpha(config, look_number)
    
    if recompute_ci is None:
        raise ValueError(
            "recompute_ci must be provided when sequential corrections are enabled."
        )

    adjusted_ci = recompute_ci(adjusted_alpha)
    if not isinstance(adjusted_ci, (list, tuple)) or len(adjusted_ci) != 2:
        raise ValueError("recompute_ci must return a 2-element sequence [lower, upper].")
    
    return (list(adjusted_ci), adjusted_alpha)

