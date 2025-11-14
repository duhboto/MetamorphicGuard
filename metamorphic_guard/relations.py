"""
Metamorphic relations for input transformations.
"""

import random
from random import Random
from typing import List, Optional, Tuple


def permute_input(L: List[int], k: int, *, rng: Optional[Random] = None) -> Tuple[List[int], int]:
    """
    Permute the input list while keeping k the same.
    The output should be equivalent (same multiset of results).
    """
    if len(L) <= 1:
        return L, k

    # Use the caller-provided RNG when available; fall back to a deterministic
    # derivation so legacy code remains reproducible.
    if rng is None:
        import hashlib

        seed_material = f"{tuple(L)}|{k}".encode("utf-8")
        digest = hashlib.sha256(seed_material).digest()
        seed = int.from_bytes(digest[:8], "big")
        rng = Random(seed)

    L_permuted = L.copy()
    rng.shuffle(L_permuted)
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
    adjusted_k = min(k, len(L))
    return L_with_noise, adjusted_k


def scale_scores(L: List[float], k: int, factor: float = 1.05) -> Tuple[List[float], int]:
    """
    Scale all scores by a fixed factor.

    Guards monotonicity—relative ordering should remain stable after scaling.
    """
    if not L:
        return L, k
    scaled = [value * factor for value in L]
    return scaled, k


def drop_low_confidence(L: List[float], k: int) -> Tuple[List[float], int]:
    """
    Drop the bottom quartile of scores to verify robustness to tail truncation.
    """
    if not L:
        return L, k
    cutoff = max(1, len(L) // 4)
    trimmed = L[cutoff:]
    adjusted_k = min(k, len(trimmed)) if trimmed else k
    return trimmed or L[:1], adjusted_k


def duplicate_top_k(L: List[int], k: int) -> Tuple[List[int], int]:
    """
    Duplicate the top-k section to ensure idempotence of repeated queries.
    """
    if not L:
        return L, k
    top_section = L[: max(1, k)]
    duplicated = top_section + L
    return duplicated, k
