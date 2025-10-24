"""
Baseline implementation of top_k problem.
Returns the k largest elements from a list, sorted in descending order.
"""

def solve(L, k):
    """
    Find the k largest elements in list L.
    
    Args:
        L: List of integers
        k: Number of elements to return
        
    Returns:
        List of k largest elements, sorted in descending order
    """
    if not L or k <= 0:
        return []
    
    # Sort in descending order and take first k elements
    sorted_L = sorted(L, reverse=True)
    return sorted_L[:min(k, len(L))]
