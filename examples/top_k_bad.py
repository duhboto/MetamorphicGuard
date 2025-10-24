"""
Buggy implementation of top_k problem with several issues.
This should be rejected by the metamorphic guard.
"""

def solve(L, k):
    """
    Buggy implementation with several issues:
    1. Returns ascending order instead of descending
    2. Off-by-one error in some cases
    3. Doesn't handle empty lists properly
    """
    if not L:
        return []
    
    if k <= 0:
        return []
    
    # Bug 1: Sort in ascending order instead of descending
    sorted_L = sorted(L)
    
    # Bug 2: Off-by-one error - take k+1 elements instead of k
    result = sorted_L[-(k+1):] if k+1 <= len(sorted_L) else sorted_L
    
    # Bug 3: Reverse the result to make it look like descending order
    # but this doesn't give us the largest elements
    return result[::-1]
