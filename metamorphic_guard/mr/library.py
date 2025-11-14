"""
Built-in metamorphic relation library.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..relations import add_noise_below_min, duplicate_top_k, permute_input, drop_low_confidence, scale_scores
from ..specs import MetamorphicRelation


_LIBRARY: List[Dict[str, Any]] = [
    {
        "name": "permute_input",
        "category": "stability",
        "description": "Shuffling ranked inputs should not change the top-k contents.",
        "risk": 0.7,
        "effort": "low",
        "relation": MetamorphicRelation(
            name="permute_input",
            transform=permute_input,
            description="Randomly permute list-like inputs; outputs should remain equivalent.",
            category="stability",
            accepts_rng=True,
        ),
    },
    {
        "name": "add_noise_below_min",
        "category": "robustness",
        "description": "Adding dominated elements below the minimum score should not affect ranking.",
        "risk": 0.8,
        "effort": "low",
        "relation": MetamorphicRelation(
            name="add_noise_below_min",
            transform=add_noise_below_min,
            description="Inject dominated noise to verify ranking robustness.",
            category="robustness",
        ),
    },
    {
        "name": "scale_scores",
        "category": "monotonicity",
        "description": "Scaling every score equally should preserve ordering decisions.",
        "risk": 0.6,
        "effort": "low",
        "relation": MetamorphicRelation(
            name="scale_scores",
            transform=scale_scores,
            description="Multiply scores by a constant factor to confirm monotonic ordering.",
            category="monotonicity",
        ),
    },
    {
        "name": "drop_low_confidence",
        "category": "robustness",
        "description": "Removing the bottom quartile should not change top-k beyond tolerance.",
        "risk": 0.5,
        "effort": "medium",
        "relation": MetamorphicRelation(
            name="drop_low_confidence",
            transform=drop_low_confidence,
            description="Trim the lowest scores to ensure resilience to low-signal candidates.",
            category="robustness",
        ),
    },
    {
        "name": "duplicate_top_k",
        "category": "idempotence",
        "description": "Re-submitting the same top queries should act idempotently.",
        "risk": 0.4,
        "effort": "low",
        "relation": MetamorphicRelation(
            name="duplicate_top_k",
            transform=duplicate_top_k,
            description="Duplicate the top-k set to ensure downstream deduplication logic.",
            category="idempotence",
        ),
    },
]


def load_library() -> List[MetamorphicRelation]:
    """Return instantiated metamorphic relations from the built-in library."""
    return [entry["relation"] for entry in _LIBRARY]


def library_metadata() -> List[Dict[str, str]]:
    """Return metadata describing the MR library."""
    return [
        {
            "name": entry["name"],
            "category": entry["category"],
            "description": entry["description"],
            "risk": entry.get("risk", 0.5),
            "effort": entry.get("effort", "medium"),
        }
        for entry in _LIBRARY
    ]

