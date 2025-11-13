"""
Multiple comparisons correction for Metamorphic Guard.

When evaluating multiple metamorphic relations or monitors, we need to control
the familywise error rate (FWER) or false discovery rate (FDR) to avoid inflated
false-positive rates.

Methods:
- Holm: Step-down procedure controlling FWER (conservative)
- Hochberg: Step-down procedure controlling FWER (more powerful than Holm)
- Benjamini-Hochberg: Step-up procedure controlling FDR (less conservative)
- Custom: User-provided correction function

Built-in methods can be extended with custom correction functions.
"""

from __future__ import annotations

from typing import Callable, List, Tuple
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


def hochberg_correction(
    p_values: List[float],
    alpha: float = 0.05,
) -> List[Tuple[int, float, bool]]:
    """
    Apply Hochberg step-down procedure for multiple comparisons.
    
    Controls familywise error rate (FWER) using a step-down procedure.
    More powerful than Holm but still controls FWER.
    
    Unlike Holm which rejects H[i] if p[i] <= alpha/(n-i+1),
    Hochberg uses a step-down approach that rejects all H[i] with p <= alpha/(n-k+1)
    where k is the largest index such that p[k] <= alpha/(n-k+1).
    
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
    
    # Find largest k such that p[k] <= alpha/(n-k+1)
    significant_count = 0
    for k in range(n, 0, -1):
        idx, p_val = indexed[k - 1]
        adjusted_alpha = alpha / (n - k + 1)
        if p_val <= adjusted_alpha:
            significant_count = k
            break
    
    results: List[Tuple[int, float, bool]] = []
    for k, (idx, p_val) in enumerate(indexed, start=1):
        # Adjusted p-value: min(1, p * (n - k + 1))
        adjusted_p = min(1.0, p_val * (n - k + 1))
        # Reject all hypotheses with index <= significant_count
        is_significant = k <= significant_count
        
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


# Registry for custom correction methods
_custom_corrections: dict[str, Callable[[List[float], float], List[Tuple[int, float, bool]]]] = {}


def register_correction_method(
    name: str,
    correction_fn: Callable[[List[float], float], List[Tuple[int, float, bool]]],
) -> None:
    """
    Register a custom correction method.
    
    Args:
        name: Name of the correction method (must be unique)
        correction_fn: Function that takes (p_values, alpha) and returns
            List of (index, adjusted_p_value, is_significant) tuples
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Correction method name must be a non-empty string")
    if not callable(correction_fn):
        raise ValueError("Correction function must be callable")
    
    _custom_corrections[name.lower()] = correction_fn


def get_registered_methods() -> List[str]:
    """Get list of all registered correction methods (built-in + custom)."""
    built_in = ["holm", "hochberg", "benjamini-hochberg", "bh", "fdr"]
    custom = list(_custom_corrections.keys())
    return sorted(set(built_in + custom))


def apply_multiple_comparisons_correction(
    p_values: List[float],
    method: str | Callable[[List[float], float], List[Tuple[int, float, bool]]] = "holm",
    alpha: float = 0.05,
) -> List[Tuple[int, float, bool]]:
    """
    Apply multiple comparisons correction.
    
    Args:
        p_values: List of p-values
        method: Correction method - either a string ("holm", "hochberg", "benjamini-hochberg"/"bh"/"fdr")
                or a custom function that takes (p_values, alpha) and returns
                List of (index, adjusted_p_value, is_significant) tuples
        alpha: Significance level
        
    Returns:
        List of (index, adjusted_p_value, is_significant) tuples
    """
    # If method is a callable, use it directly
    if callable(method):
        try:
            return method(p_values, alpha)
        except Exception as e:
            raise ValueError(f"Custom correction function failed: {e}") from e
    
    # Otherwise, treat as string method name
    method_str = str(method).lower()
    
    if method_str == "holm":
        return holm_correction(p_values, alpha)
    elif method_str == "hochberg":
        return hochberg_correction(p_values, alpha)
    elif method_str in ("benjamini-hochberg", "bh", "fdr"):
        return benjamini_hochberg_correction(p_values, alpha)
    elif method_str in _custom_corrections:
        return _custom_corrections[method_str](p_values, alpha)
    else:
        available = get_registered_methods()
        raise ValueError(
            f"Unknown correction method: {method}. "
            f"Use one of: {', '.join(available)} or provide a custom function"
        )

