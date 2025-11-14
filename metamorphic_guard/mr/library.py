"""
Built-in metamorphic relation library.
"""

from __future__ import annotations

from typing import Dict, List

from ..relations import add_noise_below_min, permute_input
from ..specs import MetamorphicRelation


_LIBRARY: List[Dict[str, MetamorphicRelation | str]] = [
    {
        "name": "permute_input",
        "category": "stability",
        "description": "Shuffling ranked inputs should not change the top-k contents.",
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
        "relation": MetamorphicRelation(
            name="add_noise_below_min",
            transform=add_noise_below_min,
            description="Inject dominated noise to verify ranking robustness.",
            category="robustness",
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
        }
        for entry in _LIBRARY
    ]

