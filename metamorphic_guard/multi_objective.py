"""
Multi-objective optimization for Metamorphic Guard.

This module implements Pareto frontier analysis, multi-criteria gating,
and trade-off visualization for complex adoption decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .types import JSONDict


@dataclass
class Objective:
    """Definition of an optimization objective."""
    
    name: str
    value: float
    weight: float = 1.0
    minimize: bool = False  # True to minimize, False to maximize
    threshold: Optional[float] = None  # Optional threshold for gating


@dataclass
class CandidateMetrics:
    """Metrics for a candidate implementation."""
    
    candidate_id: str
    objectives: Dict[str, Objective]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParetoPoint:
    """A point on the Pareto frontier."""
    
    candidate_id: str
    objectives: Dict[str, float]
    dominated: bool = False
    rank: int = 0  # Non-dominated sorting rank


@dataclass
class MultiObjectiveConfig:
    """Configuration for multi-objective analysis."""
    
    objectives: List[str]  # Names of objectives to optimize
    weights: Optional[Dict[str, float]] = None
    minimize: Optional[Dict[str, bool]] = None
    thresholds: Optional[Dict[str, float]] = None
    use_pareto: bool = True  # Use Pareto frontier analysis
    use_weighted_sum: bool = False  # Use weighted sum as alternative


def is_dominated(
    point1: Dict[str, float],
    point2: Dict[str, float],
    minimize: Dict[str, bool],
) -> bool:
    """
    Check if point1 is dominated by point2.
    
    point1 is dominated if point2 is better in all objectives.
    
    Args:
        point1: First point's objective values
        point2: Second point's objective values
        minimize: Dict indicating which objectives to minimize
    
    Returns:
        True if point1 is dominated by point2
    """
    better_in_all = True
    better_in_some = False
    
    for obj_name, value1 in point1.items():
        value2 = point2.get(obj_name, value1)
        should_minimize = minimize.get(obj_name, False)
        
        if should_minimize:
            if value2 > value1:
                better_in_all = False
                break
            elif value2 < value1:
                better_in_some = True
        else:
            if value2 < value1:
                better_in_all = False
                break
            elif value2 > value1:
                better_in_some = True
    
    return better_in_all and better_in_some


def compute_pareto_frontier(
    candidates: List[CandidateMetrics],
    objectives: List[str],
    minimize: Dict[str, bool],
) -> List[ParetoPoint]:
    """
    Compute the Pareto frontier from candidate metrics.
    
    Args:
        candidates: List of candidate metrics
        objectives: Names of objectives to consider
        minimize: Dict indicating which objectives to minimize
    
    Returns:
        List of Pareto-optimal points
    """
    points: List[ParetoPoint] = []
    
    # Convert candidates to points
    for candidate in candidates:
        obj_values = {
            obj_name: candidate.objectives[obj_name].value
            for obj_name in objectives
            if obj_name in candidate.objectives
        }
        points.append(
            ParetoPoint(
                candidate_id=candidate.candidate_id,
                objectives=obj_values,
            )
        )
    
    # Mark dominated points
    for i, point1 in enumerate(points):
        for j, point2 in enumerate(points):
            if i != j:
                if is_dominated(point1.objectives, point2.objectives, minimize):
                    point1.dominated = True
                    break
    
    # Non-dominated sorting (NSGA-II style)
    fronts: List[List[ParetoPoint]] = []
    remaining = [p for p in points if not p.dominated]
    
    rank = 0
    while remaining:
        front: List[ParetoPoint] = []
        for point in remaining:
            is_dom = False
            for other in remaining:
                if point != other:
                    if is_dominated(point.objectives, other.objectives, minimize):
                        is_dom = True
                        break
            if not is_dom:
                front.append(point)
                point.rank = rank
        
        fronts.append(front)
        remaining = [p for p in remaining if p not in front]
        rank += 1
    
    # Flatten and return
    result: List[ParetoPoint] = []
    for front in fronts:
        result.extend(front)
    
    return result


def compute_weighted_sum_score(
    candidate: CandidateMetrics,
    objectives: List[str],
    weights: Dict[str, float],
    minimize: Dict[str, bool],
) -> float:
    """
    Compute weighted sum score for a candidate.
    
    Args:
        candidate: Candidate metrics
        objectives: Names of objectives
        weights: Weights for each objective
        minimize: Dict indicating which objectives to minimize
    
    Returns:
        Weighted sum score (higher is better)
    """
    score = 0.0
    
    for obj_name in objectives:
        if obj_name not in candidate.objectives:
            continue
        
        obj = candidate.objectives[obj_name]
        weight = weights.get(obj_name, 1.0)
        value = obj.value
        
        # Normalize: if minimizing, negate
        if minimize.get(obj_name, False):
            value = -value
        
        score += weight * value
    
    return score


def analyze_trade_offs(
    candidates: List[CandidateMetrics],
    config: MultiObjectiveConfig,
) -> Dict[str, Any]:
    """
    Analyze trade-offs between multiple objectives.
    
    Args:
        candidates: List of candidate metrics
        config: Multi-objective configuration
    
    Returns:
        Analysis results with Pareto frontier, trade-offs, and recommendations
    """
    minimize = config.minimize or {obj: False for obj in config.objectives}
    weights = config.weights or {obj: 1.0 for obj in config.objectives}
    
    # Compute Pareto frontier
    pareto_points = []
    if config.use_pareto:
        pareto_points = compute_pareto_frontier(
            candidates, config.objectives, minimize
        )
    
    # Compute weighted sum scores
    weighted_scores = {}
    if config.use_weighted_sum:
        for candidate in candidates:
            score = compute_weighted_sum_score(
                candidate, config.objectives, weights, minimize
            )
            weighted_scores[candidate.candidate_id] = score
    
    # Find best candidate by weighted sum
    best_weighted = None
    if weighted_scores:
        best_weighted = max(weighted_scores.items(), key=lambda x: x[1])[0]
    
    # Find Pareto-optimal candidates
    pareto_optimal = [
        p.candidate_id for p in pareto_points if not p.dominated
    ]
    
    # Compute trade-off matrix
    trade_off_matrix: Dict[str, Dict[str, float]] = {}
    for i, cand1 in enumerate(candidates):
        trade_off_matrix[cand1.candidate_id] = {}
        for cand2 in candidates:
            if cand1 != cand2:
                # Compute relative differences
                diffs = {}
                for obj_name in config.objectives:
                    if obj_name in cand1.objectives and obj_name in cand2.objectives:
                        val1 = cand1.objectives[obj_name].value
                        val2 = cand2.objectives[obj_name].value
                        if val1 != 0:
                            diff = (val2 - val1) / abs(val1)
                        else:
                            diff = val2
                        diffs[obj_name] = diff
                trade_off_matrix[cand1.candidate_id][cand2.candidate_id] = diffs
    
    return {
        "pareto_frontier": [
            {
                "candidate_id": p.candidate_id,
                "objectives": p.objectives,
                "rank": p.rank,
                "dominated": p.dominated,
            }
            for p in pareto_points
        ],
        "pareto_optimal": pareto_optimal,
        "weighted_scores": weighted_scores,
        "best_weighted": best_weighted,
        "trade_off_matrix": trade_off_matrix,
        "objectives": config.objectives,
        "weights": weights,
        "minimize": minimize,
    }


def multi_criteria_gate(
    candidate: CandidateMetrics,
    config: MultiObjectiveConfig,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Apply multi-criteria gating rules to a candidate.
    
    Args:
        candidate: Candidate metrics
        config: Multi-objective configuration
    
    Returns:
        Tuple of (adopt, reason, details)
    """
    thresholds = config.thresholds or {}
    details: Dict[str, Any] = {
        "passed_objectives": [],
        "failed_objectives": [],
    }
    
    # Check each objective threshold
    for obj_name in config.objectives:
        if obj_name not in candidate.objectives:
            continue
        
        obj = candidate.objectives[obj_name]
        threshold = thresholds.get(obj_name, obj.threshold)
        
        if threshold is None:
            # No threshold - always pass
            details["passed_objectives"].append(obj_name)
            continue
        
        # Check if objective meets threshold
        # Use config.minimize if available, otherwise use obj.minimize
        should_minimize = config.minimize.get(obj_name, obj.minimize) if config.minimize else obj.minimize
        if should_minimize:
            passes = obj.value <= threshold
        else:
            passes = obj.value >= threshold
        
        if passes:
            details["passed_objectives"].append(obj_name)
        else:
            details["failed_objectives"].append({
                "objective": obj_name,
                "value": obj.value,
                "threshold": threshold,
                "gap": threshold - obj.value if obj.minimize else obj.value - threshold,
            })
    
    # Decision: adopt if all objectives pass
    if not details["failed_objectives"]:
        return True, "all_objectives_met", details
    
    # Reject with reason
    failed_names = [f["objective"] for f in details["failed_objectives"]]
    reason = f"failed_objectives: {', '.join(failed_names)}"
    return False, reason, details


def recommend_candidate(
    candidates: List[CandidateMetrics],
    config: MultiObjectiveConfig,
    preferences: Optional[Dict[str, float]] = None,
) -> Optional[str]:
    """
    Recommend best candidate based on multi-objective analysis.
    
    Args:
        candidates: List of candidate metrics
        config: Multi-objective configuration
        preferences: Optional user preferences (overrides config weights)
    
    Returns:
        Recommended candidate ID, or None if no candidate meets thresholds
    """
    if not candidates:
        return None
    
    # Use preferences if provided
    weights = preferences or config.weights or {obj: 1.0 for obj in config.objectives}
    
    # Filter candidates that meet all thresholds
    valid_candidates = []
    for candidate in candidates:
        adopt, reason, _ = multi_criteria_gate(candidate, config)
        if adopt:
            valid_candidates.append(candidate)
    
    if not valid_candidates:
        return None
    
    # If using Pareto, prefer Pareto-optimal candidates
    if config.use_pareto:
        minimize = config.minimize or {obj: False for obj in config.objectives}
        pareto_points = compute_pareto_frontier(
            valid_candidates, config.objectives, minimize
        )
        pareto_optimal = [p for p in pareto_points if not p.dominated]
        
        if pareto_optimal:
            # Among Pareto-optimal, use weighted sum
            pareto_candidates = [
                c for c in valid_candidates
                if c.candidate_id in [p.candidate_id for p in pareto_optimal]
            ]
            if pareto_candidates:
                scores = {
                    c.candidate_id: compute_weighted_sum_score(
                        c, config.objectives, weights, minimize
                    )
                    for c in pareto_candidates
                }
                return max(scores.items(), key=lambda x: x[1])[0]
    
    # Otherwise, use weighted sum on all valid candidates
    minimize = config.minimize or {obj: False for obj in config.objectives}
    scores = {
        c.candidate_id: compute_weighted_sum_score(
            c, config.objectives, weights, minimize
        )
        for c in valid_candidates
    }
    
    return max(scores.items(), key=lambda x: x[1])[0]

