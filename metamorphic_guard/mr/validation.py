"""
Static validation helpers for metamorphic relations.
"""

from __future__ import annotations

import inspect
from typing import List

from ..specs import MetamorphicRelation, Spec


def lint_relation(relation: MetamorphicRelation) -> List[str]:
    """Lint a single metamorphic relation definition."""
    warnings: List[str] = []
    if not relation.name:
        warnings.append("Relation is missing a name.")
    if not callable(relation.transform):
        warnings.append(f"{relation.name}: transform is not callable.")
        return warnings

    signature = inspect.signature(relation.transform)
    params = list(signature.parameters.values())
    if not params:
        warnings.append(f"{relation.name}: transform must accept at least one argument.")
    if relation.accepts_rng and "rng" not in signature.parameters:
        warnings.append(f"{relation.name}: accepts_rng=True but 'rng' parameter not found.")

    return warnings


def validate_relations(spec: Spec) -> List[str]:
    """Validate all relations defined in a spec."""
    issues: List[str] = []
    if not spec.relations:
        issues.append("Spec defines no metamorphic relations.")
        return issues

    for relation in spec.relations:
        issues.extend(lint_relation(relation))
        if relation.expect not in ("equal", "approx"):
            issues.append(f"{relation.name}: unsupported expect='{relation.expect}'.")
        if not relation.description:
            issues.append(f"{relation.name}: add a description for better docs.")

    return issues

