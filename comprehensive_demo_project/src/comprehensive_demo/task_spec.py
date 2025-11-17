"""
Task specification for recommendation system evaluation.

This demonstrates:
- Property testing (hard and soft properties)
- Metamorphic relations (permutation, monotonicity, fairness)
- Metrics extraction
- Cluster keys for correlated test cases
"""

import random
from typing import Any, Dict, List, Tuple

from metamorphic_guard import Property, MetamorphicRelation, Spec, Metric


def gen_recommendation_inputs(n: int, seed: int) -> List[Tuple[Dict[str, Any], List[Dict[str, Any]], int]]:
    """
    Generate test cases for recommendation system.
    
    Returns:
        List of (user_prefs, product_catalog, num_recommendations) tuples
    """
    random.seed(seed)
    cases = []
    
    for i in range(n):
        # Create user preferences
        user_prefs = {
            "user_id": f"user_{i % 100}",  # Reuse users for clustering
            "preferences": {
                "category_A": random.uniform(0.0, 1.0),
                "category_B": random.uniform(0.0, 1.0),
                "category_C": random.uniform(0.0, 1.0),
            },
            "demographic": "group_A" if i % 2 == 0 else "group_B",  # For fairness testing
        }
        
        # Create product catalog
        catalog_size = random.randint(50, 200)
        catalog = [
            {
                "product_id": f"prod_{j}",
                "category": random.choice(["category_A", "category_B", "category_C"]),
                "price": random.uniform(10.0, 1000.0),
                "rating": random.uniform(3.0, 5.0),
            }
            for j in range(catalog_size)
        ]
        
        num_recs = random.randint(5, 20)
        cases.append((user_prefs, catalog, num_recs))
    
    return cases


def cluster_key(args: Tuple[Dict, List, int]) -> str:
    """Cluster key for grouping related test cases."""
    user_prefs, _, _ = args
    return user_prefs["user_id"]


# Hard properties (must always pass)
def prop_is_list(output: List[str], args: Tuple) -> bool:
    """Output must be a list."""
    return isinstance(output, list)


def prop_valid_ids(output: List[str], args: Tuple) -> bool:
    """All product IDs must exist in catalog."""
    _, catalog, _ = args
    catalog_ids = {p["product_id"] for p in catalog}
    return all(pid in catalog_ids for pid in output)


def prop_no_duplicates(output: List[str], args: Tuple) -> bool:
    """No duplicate product IDs."""
    return len(output) == len(set(output))


def prop_correct_length(output: List[str], args: Tuple) -> bool:
    """Output length matches requested count."""
    _, _, num_recs = args
    return len(output) <= num_recs


# Soft properties (tolerance allowed)
def prop_diversity(output: List[str], args: Tuple) -> float:
    """Diversity score: higher is better."""
    _, catalog, _ = args
    if not output:
        return 0.0
    
    # Count unique categories
    product_map = {p["product_id"]: p for p in catalog}
    categories = [product_map[pid]["category"] for pid in output if pid in product_map]
    unique_cats = len(set(categories))
    total_cats = len(set(p["category"] for p in catalog))
    
    return unique_cats / max(total_cats, 1)


def prop_relevance(output: List[str], args: Tuple) -> float:
    """Relevance score based on user preferences."""
    user_prefs, catalog, _ = args
    if not output:
        return 0.0
    
    product_map = {p["product_id"]: p for p in catalog}
    preferences = user_prefs["preferences"]
    
    total_score = 0.0
    for pid in output:
        if pid in product_map:
            category = product_map[pid]["category"]
            pref_score = preferences.get(category, 0.0)
            total_score += pref_score
    
    return total_score / len(output) if output else 0.0


# Metamorphic Relations
def mr_permute_input(args: Tuple) -> Tuple:
    """Permutation: shuffling user preferences should produce same results."""
    import random
    user_prefs, catalog, num_recs = args
    
    # Shuffle preference values (but keep keys)
    shuffled_prefs = dict(user_prefs)
    pref_values = list(shuffled_prefs["preferences"].values())
    random.shuffle(pref_values)
    shuffled_prefs["preferences"] = {
        k: v for k, v in zip(shuffled_prefs["preferences"].keys(), pref_values)
    }
    
    return (shuffled_prefs, catalog, num_recs)


def mr_scale_preferences(args: Tuple) -> Tuple:
    """Monotonicity: scaling preferences by positive constant should preserve order."""
    import random
    user_prefs, catalog, num_recs = args
    
    scaled_prefs = dict(user_prefs)
    scale_factor = random.uniform(0.5, 2.0)
    scaled_prefs["preferences"] = {
        k: v * scale_factor for k, v in user_prefs["preferences"].items()
    }
    
    return (scaled_prefs, catalog, num_recs)


def mr_add_noise_products(args: Tuple) -> Tuple:
    """Adding low-relevance products shouldn't affect top recommendations."""
    import random
    user_prefs, catalog, num_recs = args
    
    # Add products with low preference scores
    noise_products = [
        {
            "product_id": f"noise_{i}",
            "category": "category_D",  # Category not in preferences
            "price": random.uniform(10.0, 100.0),
            "rating": random.uniform(1.0, 2.0),
        }
        for i in range(10)
    ]
    
    extended_catalog = catalog + noise_products
    return (user_prefs, extended_catalog, num_recs)


def mr_swap_demographic(args: Tuple) -> Tuple:
    """Fairness: swapping demographic should not drastically change results."""
    user_prefs, catalog, num_recs = args
    
    swapped_prefs = dict(user_prefs)
    swapped_prefs["demographic"] = "group_B" if user_prefs["demographic"] == "group_A" else "group_A"
    
    return (swapped_prefs, catalog, num_recs)


def equivalence(a: List[str], b: List[str]) -> bool:
    """Equivalence: same set of product IDs (order may differ)."""
    return set(a) == set(b)


def create_recommendation_task() -> Spec:
    """Create the recommendation system task specification."""
    return Spec(
        name="recommendation",
        gen_inputs=gen_recommendation_inputs,
        properties=[
            Property(
                check=prop_is_list,
                description="Output is a list",
                mode="hard",
            ),
            Property(
                check=prop_valid_ids,
                description="All product IDs are valid",
                mode="hard",
            ),
            Property(
                check=prop_no_duplicates,
                description="No duplicate product IDs",
                mode="hard",
            ),
            Property(
                check=prop_correct_length,
                description="Output length matches requested count",
                mode="hard",
            ),
            Property(
                check=lambda out, args: prop_diversity(out, args) > 0.5,
                description="Diversity score > 0.5",
                mode="soft",
            ),
            Property(
                check=lambda out, args: prop_relevance(out, args) > 0.7,
                description="Relevance score > 0.7",
                mode="soft",
            ),
        ],
        relations=[
            MetamorphicRelation(
                name="permute_input",
                transform=mr_permute_input,
                expect="equal",
                description="Shuffling preferences produces same results",
            ),
            MetamorphicRelation(
                name="scale_preferences",
                transform=mr_scale_preferences,
                expect="equal",
                description="Scaling preferences preserves order",
            ),
            MetamorphicRelation(
                name="add_noise_products",
                transform=mr_add_noise_products,
                expect="equal",
                description="Adding low-relevance products doesn't affect top results",
            ),
            MetamorphicRelation(
                name="swap_demographic",
                transform=mr_swap_demographic,
                expect="similar",  # Allow some variation for fairness
                description="Demographic swap produces similar results",
            ),
        ],
        equivalence=equivalence,
        cluster_key=cluster_key,
        metrics=[
            Metric(
                name="diversity_score",
                extract=lambda out, args: prop_diversity(out, args),
                kind="mean",
            ),
            Metric(
                name="relevance_score",
                extract=lambda out, args: prop_relevance(out, args),
                kind="mean",
            ),
            Metric(
                name="response_time_ms",
                extract=lambda out, args: 50.0,  # Placeholder - actual implementations should measure
                kind="mean",
                higher_is_better=False,
            ),
        ],
    )

