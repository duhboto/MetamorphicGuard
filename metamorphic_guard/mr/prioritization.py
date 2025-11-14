"""
Heuristics for prioritizing metamorphic relations by coverage and impact.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Tuple

from ..specs import Spec
from .discovery import infer_property_categories
from .library import library_metadata

CATEGORY_WEIGHTS: Dict[str, float] = {
    "robustness": 1.0,
    "stability": 0.9,
    "monotonicity": 0.8,
    "fairness": 0.85,
    "idempotence": 0.6,
    "general": 0.4,
}

EFFORT_WEIGHTS: Dict[str, float] = {"low": 0.2, "medium": 0.0, "high": -0.3}


def summarize_coverage(spec: Spec) -> Dict[str, Any]:
    """Summarize category coverage for the provided spec."""
    property_categories = infer_property_categories(spec)
    relation_categories: Counter[str] = Counter()
    for relation in spec.relations:
        category = relation.category or "unspecified"
        relation_categories[category] += 1

    categories = {}
    all_categories = set(property_categories) | set(relation_categories)
    for category in sorted(all_categories):
        prop_count = property_categories.get(category, 0)
        rel_count = relation_categories.get(category, 0)
        target = max(prop_count, 1)
        coverage_ratio = rel_count / target
        categories[category] = {
            "properties": prop_count,
            "relations": rel_count,
            "coverage_ratio": round(coverage_ratio, 2),
        }

    missing = [
        category
        for category, stats in categories.items()
        if stats["relations"] == 0 and category != "general"
    ]

    return {
        "properties": len(spec.properties),
        "relations": len(spec.relations),
        "density": round(len(spec.relations) / max(1, len(spec.properties)), 2),
        "categories": categories,
        "missing_categories": missing,
    }


def prioritize_relations(spec: Spec, *, max_items: int = 5) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Rank library relations by how much coverage/impact they would add to the spec.

    Returns (suggestions, coverage_summary).
    """

    coverage = summarize_coverage(spec)
    category_stats = coverage["categories"]
    missing = set(coverage["missing_categories"])

    scored: List[Dict[str, Any]] = []
    for entry in library_metadata():
        category = entry["category"]
        weight = CATEGORY_WEIGHTS.get(category, 0.5)
        coverage_ratio = category_stats.get(category, {}).get("coverage_ratio", 0.0)
        risk = float(entry.get("risk", 0.5))
        effort = entry.get("effort", "medium").lower()
        effort_weight = EFFORT_WEIGHTS.get(effort, 0.0)

        score = weight * (1.0 - coverage_ratio) + risk + effort_weight
        if category in missing:
            score += 0.5

        scored.append(
            {
                **entry,
                "score": round(score, 2),
                "coverage_ratio": coverage_ratio,
                "reason": _reason_for_entry(category, coverage_ratio, missing),
            }
        )

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:max_items], coverage


def _reason_for_entry(category: str, coverage_ratio: float, missing: set[str]) -> str:
    if category in missing:
        return f"No coverage for {category}; add at least one relation."
    if coverage_ratio < 0.5:
        return f"Coverage for {category} at {coverage_ratio:.2f}; add redundancy."
    return f"{category} already covered; use for diversity or regression guardrails."

