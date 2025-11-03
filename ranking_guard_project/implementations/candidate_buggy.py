"""
Buggy candidate that introduces a regression: it drops duplicate scores.

This violates the multiset equality requirement enforced by Metamorphic Guard.
"""

from __future__ import annotations

from typing import List


def solve(scores: List[int], k: int) -> List[int]:
    """Return the k highest *unique* scores (BUG: drops duplicates)."""
    if not scores or k <= 0:
        return []

    # Deduplicate values before sorting – an illegal change for our contract.
    unique_scores = sorted(set(scores), reverse=True)
    return unique_scores[: min(k, len(unique_scores))]
