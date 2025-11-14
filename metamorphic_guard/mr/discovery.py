"""
Heuristic metamorphic relation discovery helpers.
"""

from __future__ import annotations

from collections import Counter
from typing import Dict, List

from ..specs import Spec

KEYWORD_CATEGORY_MAP = {
    "monotonic": "monotonicity",
    "order": "stability",
    "robust": "robustness",
    "noise": "robustness",
    "idempotent": "idempotence",
    "deduplicate": "idempotence",
    "fair": "fairness",
    "parity": "fairness",
    "jitter": "robustness",
    "scale": "monotonicity",
    "rank": "stability",
}


def discover_relations(spec: Spec) -> List[Dict[str, str]]:
    """
    Suggest metamorphic relations based on property descriptions.

    This is a heuristic helper intended to jump-start MR design. It looks
    for keywords in property descriptions and emits canned suggestions.
    """
    suggestions: List[Dict[str, str]] = []
    seen_categories: set[str] = set()

    category_counts = infer_property_categories(spec)
    for prop in spec.properties:
        description = prop.description.lower()
        for keyword, category in KEYWORD_CATEGORY_MAP.items():
            if keyword in description and category not in seen_categories:
                seen_categories.add(category)
                suggestions.append(
                    {
                        "category": category,
                        "property": prop.description,
                        "suggestion": _suggestion_for(category),
                    }
                )

    if not suggestions:
        suggestions.append(
            {
                "category": "general",
                "property": "n/a",
                "suggestion": "Consider adding permutation, scaling, or noise injection relations to improve coverage.",
            }
        )

    return suggestions


def _suggestion_for(category: str) -> str:
    if category == "monotonicity":
        return "Duplicate inputs with scaled values to verify ranking monotonicity."
    if category == "stability":
        return "Shuffle equal-score items to confirm invariant results."
    if category == "robustness":
        return "Inject dominated or null inputs to assert robustness to noise."
    if category == "idempotence":
        return "Re-apply the same transformation and ensure outputs are unchanged."
    return "Compose existing relations to probe additional invariants."


def infer_property_categories(spec: Spec) -> Dict[str, int]:
    """Return keyword-inferred category counts for the given Spec."""
    counts: Counter[str] = Counter()
    for prop in spec.properties:
        description = prop.description.lower()
        matched = False
        for keyword, category in KEYWORD_CATEGORY_MAP.items():
            if keyword in description:
                counts[category] += 1
                matched = True
        if not matched:
            counts["general"] += 1
    return dict(counts)

