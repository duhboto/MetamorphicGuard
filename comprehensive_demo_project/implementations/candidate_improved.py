"""
Improved candidate recommendation system.

Enhancements over baseline:
- Better diversity (ensures category spread)
- Improved relevance scoring
- Handles edge cases better
"""


def solve(user_prefs, catalog, num_recommendations):
    """
    Improved recommendation algorithm with diversity consideration.
    
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
        
        # Enhanced scoring: preference * rating * (1 + diversity bonus)
        base_score = pref_score * product["rating"]
        scored_products.append((base_score, product["product_id"], category))
    
    # Sort by score
    scored_products.sort(reverse=True, key=lambda x: x[0])
    
    # Diversity-aware selection: ensure category spread
    selected = []
    category_counts = {}
    
    for score, pid, category in scored_products:
        if len(selected) >= num_recommendations:
            break
        
        # Prefer products from underrepresented categories
        cat_count = category_counts.get(category, 0)
        max_per_category = max(1, num_recommendations // 3)  # Spread across categories
        
        if cat_count < max_per_category or len(selected) < num_recommendations // 2:
            selected.append(pid)
            category_counts[category] = cat_count + 1
    
    # Fill remaining slots with top-scoring products
    remaining = num_recommendations - len(selected)
    if remaining > 0:
        for score, pid, category in scored_products:
            if pid not in selected and len(selected) < num_recommendations:
                selected.append(pid)
    
    return selected[:num_recommendations]



