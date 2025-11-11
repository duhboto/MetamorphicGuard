"""
Power analysis and sample size calculation for Metamorphic Guard.

Provides functions to estimate statistical power and calculate required sample sizes
for detecting minimum detectable effects (MDE) in pass-rate comparisons.
"""

from __future__ import annotations

import math
from statistics import NormalDist
from typing import Tuple, Optional


def calculate_power(
    baseline_rate: float,
    candidate_rate: float,
    sample_size: int,
    alpha: float = 0.05,
    min_delta: float = 0.02,
) -> float:
    """
    Calculate statistical power for detecting a pass-rate improvement.
    
    Args:
        baseline_rate: Expected baseline pass rate (0-1)
        candidate_rate: Expected candidate pass rate (0-1)
        sample_size: Number of test cases
        alpha: Significance level (default: 0.05)
        min_delta: Minimum detectable effect (default: 0.02)
        
    Returns:
        Statistical power (0-1)
    """
    if sample_size == 0:
        return 0.0
    
    effect = candidate_rate - baseline_rate
    pooled_var = baseline_rate * (1 - baseline_rate) + candidate_rate * (1 - candidate_rate)
    
    if pooled_var == 0:
        return 1.0 if effect >= min_delta else 0.0
    
    se = math.sqrt(pooled_var / sample_size)
    if se == 0:
        return 1.0 if effect >= min_delta else 0.0
    
    z_alpha = NormalDist().inv_cdf(1 - alpha)
    z_effect = (effect - min_delta) / se
    power_val = 1 - NormalDist().cdf(z_alpha - z_effect)
    return max(0.0, min(1.0, power_val))


def calculate_sample_size(
    baseline_rate: float,
    min_delta: float,
    alpha: float = 0.05,
    power_target: float = 0.8,
) -> int:
    """
    Calculate required sample size to detect a minimum detectable effect.
    
    Args:
        baseline_rate: Expected baseline pass rate (0-1)
        min_delta: Minimum detectable effect (improvement threshold)
        alpha: Significance level (default: 0.05)
        power_target: Desired statistical power (default: 0.8)
        
    Returns:
        Required sample size (number of test cases)
    """
    if min_delta <= 0:
        raise ValueError("min_delta must be positive")
    if not (0 < power_target < 1):
        raise ValueError("power_target must be between 0 and 1")
    if not (0 < alpha < 1):
        raise ValueError("alpha must be between 0 and 1")
    if not (0 <= baseline_rate <= 1):
        raise ValueError("baseline_rate must be between 0 and 1")
    
    p1 = baseline_rate
    p2 = max(0.0, min(1.0, baseline_rate + min_delta))
    
    var_target = p1 * (1 - p1) + p2 * (1 - p2)
    if var_target == 0:
        # Edge case: both rates are 0 or 1
        return 1
    
    z_alpha = NormalDist().inv_cdf(1 - alpha)
    z_beta = NormalDist().inv_cdf(power_target)
    
    n = ((z_alpha + z_beta) ** 2 * var_target) / (min_delta ** 2)
    return math.ceil(n)


def estimate_mde(
    baseline_rate: float,
    sample_size: int,
    alpha: float = 0.05,
    power_target: float = 0.8,
) -> float:
    """
    Estimate minimum detectable effect (MDE) for given sample size.
    
    Args:
        baseline_rate: Expected baseline pass rate (0-1)
        sample_size: Number of test cases
        alpha: Significance level (default: 0.05)
        power_target: Desired statistical power (default: 0.8)
        
    Returns:
        Minimum detectable effect (pass-rate improvement)
    """
    if sample_size <= 0:
        raise ValueError("sample_size must be positive")
    if not (0 < power_target < 1):
        raise ValueError("power_target must be between 0 and 1")
    if not (0 < alpha < 1):
        raise ValueError("alpha must be between 0 and 1")
    if not (0 <= baseline_rate <= 1):
        raise ValueError("baseline_rate must be between 0 and 1")
    
    p1 = baseline_rate
    # For MDE estimation, assume p2 = p1 + delta (unknown)
    # We'll solve for delta iteratively or use approximation
    
    z_alpha = NormalDist().inv_cdf(1 - alpha)
    z_beta = NormalDist().inv_cdf(power_target)
    
    # Approximate: assume p2 ≈ p1 for variance calculation
    # This gives a conservative estimate
    var_approx = 2 * p1 * (1 - p1)
    
    if var_approx == 0:
        return 0.0
    
    mde = (z_alpha + z_beta) * math.sqrt(var_approx / sample_size)
    return max(0.0, min(1.0 - baseline_rate, mde))

