"""
Stability and equivalence utilities for metamorphic testing.
"""

from collections import Counter
from typing import List, Any, Dict


def multiset_equal(list_a: List[Any], list_b: List[Any]) -> bool:
    """Check if two lists contain the same elements with same multiplicities (order doesn't matter)."""
    return Counter(list_a) == Counter(list_b)


def float_list_close(a: List[float], b: List[float], rtol: float = 1e-5, atol: float = 1e-8) -> bool:
    """Check if two lists of floats are close within tolerance."""
    if len(a) != len(b):
        return False
    
    for x, y in zip(a, b):
        if abs(x - y) > atol + rtol * abs(y):
            return False
    
    return True

def detect_flakiness(
    results: List[Dict[str, Any]],
    key_selector: str = "result",
    tolerance: float = 0.0
) -> Dict[str, Any]:
    """
    Analyze a list of results from identical inputs to detect non-determinism.
    
    Args:
        results: List of result dictionaries from multiple runs of same input
        key_selector: Key in result dict to compare (default: "result")
        tolerance: Tolerance for float comparison (if applicable)
        
    Returns:
        Dict containing:
            - is_flaky: bool
            - distinct_values: list of unique values seen
            - distribution: counts of each value
    """
    if not results:
        return {"is_flaky": False, "distinct_values": [], "distribution": {}}
        
    values = []
    for r in results:
        val = r.get(key_selector)
        # Handle nested dicts or lists by converting to string for simple comparison
        # For rigorous comparison, we might need deep diff
        values.append(val)
        
    # Basic equality check
    first = values[0]
    is_flaky = False
    
    # If values are floats, use tolerance
    if isinstance(first, (int, float)) and tolerance > 0:
        for v in values[1:]:
            if not isinstance(v, (int, float)) or abs(v - first) > tolerance:
                is_flaky = True
                break
    else:
        # Strict equality for other types
        # Convert to string/hashable for distribution counting
        # Use string representation for complex objects to catch diffs
        if any(v != first for v in values[1:]):
            is_flaky = True
            
    # Compute distribution
    try:
        # Try to make values hashable
        hashable_values = []
        for v in values:
            if isinstance(v, (dict, list)):
                hashable_values.append(str(v))
            else:
                hashable_values.append(v)
        dist = dict(Counter(hashable_values))
    except TypeError:
        # Fallback if something is not hashable even after str() - unlikely but possible
        dist = {"error": "Could not compute distribution"}
        
    return {
        "is_flaky": is_flaky,
        "distinct_values": list(dist.keys()),
        "distribution": dist
    }
