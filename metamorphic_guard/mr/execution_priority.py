"""
Execution priority system for metamorphic relations.

This module prioritizes MRs based on their expected value and execution order
to maximize information gain early in the evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from ..specs import MetamorphicRelation, Spec


@dataclass
class MRPriority:
    """Priority information for a metamorphic relation."""
    
    relation: MetamorphicRelation
    priority_score: float
    execution_order: int
    reasons: List[str]


@dataclass
class MRPriorityConfig:
    """Configuration for MR prioritization."""
    
    enabled: bool = True
    method: str = "coverage"  # "coverage", "violation_likelihood", "cost_benefit"
    category_weights: Optional[Dict[str, float]] = None
    cost_aware: bool = False
    violation_history: Optional[Dict[str, int]] = None


# Default category weights (higher = more important)
DEFAULT_CATEGORY_WEIGHTS = {
    "robustness": 1.0,
    "stability": 0.9,
    "monotonicity": 0.8,
    "fairness": 0.85,
    "invariance": 0.75,
    "idempotence": 0.6,
    "general": 0.4,
}


def compute_coverage_priority(
    relation: MetamorphicRelation,
    spec: Spec,
    category_weights: Dict[str, float],
) -> float:
    """
    Compute priority based on category coverage.
    
    Relations in underrepresented categories get higher priority.
    
    Args:
        relation: Metamorphic relation
        spec: Task specification
        category_weights: Weights for each category
    
    Returns:
        Priority score (higher = more important)
    """
    category = relation.category or "general"
    weight = category_weights.get(category, 0.5)
    
    # Count relations in same category
    same_category_count = sum(
        1 for r in spec.relations
        if (r.category or "general") == category
    )
    
    # Lower count = higher priority (more unique)
    uniqueness_bonus = 1.0 / max(1, same_category_count)
    
    return weight * (1.0 + uniqueness_bonus)


def compute_violation_likelihood_priority(
    relation: MetamorphicRelation,
    violation_history: Dict[str, int],
) -> float:
    """
    Compute priority based on historical violation likelihood.
    
    Relations that have violated more often get higher priority.
    
    Args:
        relation: Metamorphic relation
        violation_history: History of violations by relation name
    
    Returns:
        Priority score (higher = more important)
    """
    relation_name = relation.name
    violation_count = violation_history.get(relation_name, 0)
    
    # Normalize violation count (assume max 100 violations)
    normalized = min(1.0, violation_count / 100.0)
    
    return 0.5 + normalized * 0.5  # Range: 0.5 to 1.0


def compute_cost_benefit_priority(
    relation: MetamorphicRelation,
    estimated_cost: Optional[float] = None,
    expected_value: float = 1.0,
) -> float:
    """
    Compute priority based on cost-benefit ratio.
    
    Relations with better value-to-cost ratio get higher priority.
    
    Args:
        relation: Metamorphic relation
        estimated_cost: Estimated execution cost (if available)
        expected_value: Expected information value
    
    Returns:
        Priority score (higher = more important)
    """
    if estimated_cost is None or estimated_cost == 0:
        return expected_value
    
    # Cost-benefit ratio: value / cost
    ratio = expected_value / estimated_cost
    
    # Normalize (assume reasonable range)
    normalized = min(1.0, ratio / 10.0)
    
    return normalized


def prioritize_relations(
    spec: Spec,
    config: MRPriorityConfig,
    violation_history: Optional[Dict[str, int]] = None,
) -> List[MRPriority]:
    """
    Prioritize metamorphic relations for execution.
    
    Args:
        spec: Task specification
        config: Prioritization configuration
        violation_history: History of violations by relation name
    
    Returns:
        List of prioritized relations, sorted by priority (highest first)
    """
    if not config.enabled:
        # Return in original order
        return [
            MRPriority(
                relation=r,
                priority_score=1.0,
                execution_order=i,
                reasons=["original_order"],
            )
            for i, r in enumerate(spec.relations)
        ]
    
    if violation_history is None:
        violation_history = config.violation_history or {}
    
    category_weights = config.category_weights or DEFAULT_CATEGORY_WEIGHTS
    
    priorities = []
    for i, relation in enumerate(spec.relations):
        score = 0.0
        reasons = []
        
        if config.method == "coverage":
            coverage_score = compute_coverage_priority(
                relation, spec, category_weights
            )
            score = coverage_score
            reasons.append(f"coverage={coverage_score:.2f}")
        
        elif config.method == "violation_likelihood":
            violation_score = compute_violation_likelihood_priority(
                relation, violation_history
            )
            score = violation_score
            reasons.append(f"violation_likelihood={violation_score:.2f}")
        
        elif config.method == "cost_benefit":
            cost_score = compute_cost_benefit_priority(relation)
            score = cost_score
            reasons.append(f"cost_benefit={cost_score:.2f}")
        
        elif config.method == "hybrid":
            # Combine multiple methods
            coverage_score = compute_coverage_priority(
                relation, spec, category_weights
            )
            violation_score = compute_violation_likelihood_priority(
                relation, violation_history
            )
            
            # Weighted combination
            score = coverage_score * 0.6 + violation_score * 0.4
            reasons.append(f"coverage={coverage_score:.2f}")
            reasons.append(f"violation={violation_score:.2f}")
        
        priorities.append(
            MRPriority(
                relation=relation,
                priority_score=score,
                execution_order=i,
                reasons=reasons,
            )
        )
    
    # Sort by priority score (highest first)
    priorities.sort(key=lambda p: p.priority_score, reverse=True)
    
    # Update execution order
    for i, priority in enumerate(priorities):
        priority.execution_order = i
    
    return priorities


def get_execution_order(
    spec: Spec,
    config: MRPriorityConfig,
    violation_history: Optional[Dict[str, int]] = None,
) -> List[MetamorphicRelation]:
    """
    Get metamorphic relations in execution priority order.
    
    Args:
        spec: Task specification
        config: Prioritization configuration
        violation_history: History of violations by relation name
    
    Returns:
        List of relations in priority order
    """
    priorities = prioritize_relations(spec, config, violation_history)
    return [p.relation for p in priorities]

