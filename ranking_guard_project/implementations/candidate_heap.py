"""
Candidate ranking algorithm using a heap for better scalability.

It should match the baseline semantics while improving throughput when k is
much smaller than the input size.
"""

from __future__ import annotations

import heapq
from typing import List


def solve(scores: List[int], k: int) -> List[int]:
    """Return the k highest scores in descending order using a heap."""
    if not scores or k <= 0:
        return []

    if k >= len(scores):
        return sorted(scores, reverse=True)

    top_k = heapq.nlargest(k, scores)
    return sorted(top_k, reverse=True)
