"""
Multiple comparisons correction for Metamorphic Guard.

When evaluating multiple metamorphic relations or monitors, we need to control
the familywise error rate (FWER) or false discovery rate (FDR) to avoid inflated
false-positive rates.

Methods:
- Holm: Step-down procedure controlling FWER (conservative)
- Benjamini-Hochberg: Step-up procedure controlling FDR (less conservative)
"""

from __future__ import annotations

from typing import List, Tuple
import math


def holm_correction(
    p_values: List[float],
    alpha: float = 0.05,
) -> List[Tuple[int, float, bool]]:
    """
    Apply Holm-Bonferroni correction for multiple comparisons.
    
    Controls familywise error rate (FWER) using a step-down procedure.
    
    Args:
        p_values: List of p-values (one per MR/monitor)
        alpha: Significance level (default: 0.05)
        
    Returns:
        List of (index, adjusted_p_value, is_significant) tuples, sorted by p-value
    """
    n = len(p_values)
    if n == 0:
        return []
    
    # Pair p-values with their indices
    indexed = [(i, p) for i, p in enumerate(p_values)]
    # Sort by p-value (ascending)
    indexed.sort(key=lambda x: x[1])
    
    results: List[Tuple[int, float, bool]] = []
    for k, (idx, p_val) in enumerate(indexed, start=1):
        # Adjusted alpha: alpha / (n - k + 1)
        adjusted_alpha = alpha / (n - k + 1)
        adjusted_p = min(1.0, p_val * (n - k + 1))
        is_significant = p_val <= adjusted_alpha
        
        results.append((idx, adjusted_p, is_significant))
    
    return results


def benjamini_hochberg_correction(
    p_values: List[float],
    alpha: float = 0.05,
) -> List[Tuple[int, float, bool]]:
    """
    Apply Benjamini-Hochberg correction for multiple comparisons.
    
    Controls false discovery rate (FDR) using a step-up procedure.
    Less conservative than Holm, appropriate when some false positives are acceptable.
    
    Args:
        p_values: List of p-values (one per MR/monitor)
        alpha: Significance level (default: 0.05)
        
    Returns:
        List of (index, adjusted_p_value, is_significant) tuples, sorted by p-value
    """
    n = len(p_values)
    if n == 0:
        return []
    
    # Pair p-values with their indices
    indexed = [(i, p) for i, p in enumerate(p_values)]
    # Sort by p-value (ascending)
    indexed.sort(key=lambda x: x[1])
    
    # Find largest k such that p[k] <= (k * alpha) / n
    significant_count = 0
    for k in range(n, 0, -1):
        idx, p_val = indexed[k - 1]
        if p_val <= (k * alpha) / n:
            significant_count = k
            break
    
    results: List[Tuple[int, float, bool]] = []
    for k, (idx, p_val) in enumerate(indexed, start=1):
        # Adjusted p-value: min(1, p * n / k)
        adjusted_p = min(1.0, p_val * n / k)
        is_significant = k <= significant_count
        
        results.append((idx, adjusted_p, is_significant))
    
    return results


def apply_multiple_comparisons_correction(
    p_values: List[float],
    method: str = "holm",
    alpha: float = 0.05,
) -> List[Tuple[int, float, bool]]:
    """
    Apply multiple comparisons correction.
    
    Args:
        p_values: List of p-values
        method: Correction method ("holm" or "benjamini-hochberg"/"bh")
        alpha: Significance level
        
    Returns:
        List of (index, adjusted_p_value, is_significant) tuples
    """
    method = method.lower()
    if method == "holm":
        return holm_correction(p_values, alpha)
    elif method in ("benjamini-hochberg", "bh", "fdr"):
        return benjamini_hochberg_correction(p_values, alpha)
    else:
        raise ValueError(f"Unknown correction method: {method}. Use 'holm' or 'benjamini-hochberg'")

