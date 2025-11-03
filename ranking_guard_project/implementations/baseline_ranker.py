"""
Baseline ranking algorithm currently serving production traffic.

It mirrors the simple reference implementation from our legacy service: we sort
the list in descending order and slice the top-k entries.
"""

from __future__ import annotations

from typing import Iterable, List


def solve(scores: List[int], k: int) -> List[int]:
    """Return the k highest scores in descending order."""
    if not scores or k <= 0:
        return []

    ordered = sorted(scores, reverse=True)
    return ordered[: min(k, len(ordered))]
