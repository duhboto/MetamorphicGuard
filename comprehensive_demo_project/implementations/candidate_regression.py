"""
Regression candidate - intentionally buggy implementation.

This should be rejected by Metamorphic Guard due to:
- Fairness violations (discriminates by demographic)
- Incorrect length handling
- Potential duplicate IDs
"""


def solve(user_prefs, catalog, num_recommendations):
    """
    Buggy implementation with fairness issues.
    
    BUGS:
    1. Discriminates against group_B (lower scores)
    2. May return more items than requested
    3. Doesn't check for duplicates
    """
    if not catalog or num_recommendations <= 0:
        return []
    
    preferences = user_prefs.get("preferences", {})
    demographic = user_prefs.get("demographic", "group_A")
    
    # BUG: Discriminate against group_B
    demographic_penalty = 0.5 if demographic == "group_B" else 1.0
    
    # Score each product
    scored_products = []
    for product in catalog:
        category = product["category"]
        pref_score = preferences.get(category, 0.0)
        
        # Apply unfair penalty
        score = pref_score * product["rating"] * demographic_penalty
        scored_products.append((score, product["product_id"]))
    
    # Sort by score
    scored_products.sort(reverse=True, key=lambda x: x[0])
    
    # BUG: Return k+1 items instead of k
    top_k = scored_products[:num_recommendations + 1]
    
    # BUG: No duplicate checking
    return [pid for _, pid in top_k]






