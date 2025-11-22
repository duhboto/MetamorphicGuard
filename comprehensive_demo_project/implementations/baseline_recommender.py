"""
Baseline recommendation system implementation.

Simple collaborative filtering approach:
- Scores products based on user preferences
- Returns top-k products by score
- No fairness considerations
"""


def solve(user_prefs, catalog, num_recommendations):
    """
    Baseline recommendation algorithm.
    
    Args:
        user_prefs: Dict with 'preferences' (category -> score) and 'demographic'
        catalog: List of product dicts with 'product_id', 'category', 'price', 'rating'
        num_recommendations: Number of products to recommend
    
    Returns:
        List of product IDs (strings) in descending order of score
    """
    if not catalog or num_recommendations <= 0:
        return []
    
    preferences = user_prefs.get("preferences", {})
    
    # Score each product
    scored_products = []
    for product in catalog:
        category = product["category"]
        pref_score = preferences.get(category, 0.0)
        
        # Simple scoring: preference * rating
        score = pref_score * product["rating"]
        scored_products.append((score, product["product_id"]))
    
    # Sort by score (descending) and take top-k
    scored_products.sort(reverse=True, key=lambda x: x[0])
    top_k = scored_products[:num_recommendations]
    
    return [pid for _, pid in top_k]






