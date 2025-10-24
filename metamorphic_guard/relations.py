"""
Metamorphic relations for input transformations.
"""

import random
from typing import List, Tuple


def permute_input(L: List[int], k: int) -> Tuple[List[int], int]:
    """
    Permute the input list while keeping k the same.
    The output should be equivalent (same multiset of results).
    """
    L_permuted = L.copy()
    random.shuffle(L_permuted)
    return L_permuted, k


def add_noise_below_min(L: List[int], k: int) -> Tuple[List[int], int]:
    """
    Add small negative values below the minimum of L.
    The output should be equivalent (same results).
    """
    if not L:
        return L, k
    
    min_val = min(L)
    noise = [min_val - 1 - i for i in range(5)]  # Add 5 values below min
    L_with_noise = L + noise
    return L_with_noise, k
