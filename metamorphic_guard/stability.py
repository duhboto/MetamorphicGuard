"""
Stability and equivalence utilities for metamorphic testing.
"""

from collections import Counter
from typing import List, Any


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
