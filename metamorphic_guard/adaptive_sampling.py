"""
Adaptive sampling algorithms for smart test case selection.

This module implements intelligent sampling strategies that focus on high-signal
test cases to maximize information gain per execution.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .types import JSONDict


@dataclass
class SamplingStrategy:
    """Configuration for adaptive sampling strategy."""
    
    enabled: bool = True
    method: str = "uncertainty"  # "uncertainty", "diversity", "violation_focused"
    initial_sample_size: int = 50
    batch_size: int = 25
    uncertainty_threshold: float = 0.3
    diversity_weight: float = 0.5
    violation_weight: float = 0.3


@dataclass
class TestCaseScore:
    """Score for a test case indicating its information value."""
    
    index: int
    score: float
    reasons: List[str]


def compute_uncertainty_score(
    baseline_result: Optional[JSONDict],
    candidate_result: Optional[JSONDict],
) -> float:
    """
    Compute uncertainty score for a test case.
    
    Higher scores indicate more uncertainty about the outcome.
    
    Args:
        baseline_result: Baseline execution result (if available)
        candidate_result: Candidate execution result (if available)
    
    Returns:
        Uncertainty score between 0 and 1
    """
    if baseline_result is None and candidate_result is None:
        # No information yet - maximum uncertainty
        return 1.0
    
    if baseline_result is None or candidate_result is None:
        # Partial information - high uncertainty
        return 0.8
    
    # Check if results differ
    baseline_passed = baseline_result.get("passed", False)
    candidate_passed = candidate_result.get("passed", False)
    
    if baseline_passed == candidate_passed:
        # Results agree - lower uncertainty
        return 0.2
    else:
        # Results disagree - high uncertainty (potential violation)
        return 0.9


def compute_diversity_score(
    test_input: Tuple[object, ...],
    executed_inputs: Sequence[Tuple[object, ...]],
    cluster_key: Optional[Callable[[Tuple[object, ...]], object]] = None,
) -> float:
    """
    Compute diversity score for a test case.
    
    Higher scores indicate the input is more different from already executed cases.
    
    Args:
        test_input: Test case input
        executed_inputs: Already executed inputs
        cluster_key: Optional function to cluster inputs
    
    Returns:
        Diversity score between 0 and 1
    """
    if not executed_inputs:
        return 1.0
    
    if cluster_key is not None:
        # Use clustering for diversity
        test_cluster = cluster_key(test_input)
        executed_clusters = {cluster_key(inp) for inp in executed_inputs}
        
        if test_cluster not in executed_clusters:
            return 1.0
        else:
            # Same cluster - lower diversity
            return 0.3
    
    # Simple distance-based diversity
    # For numeric inputs, compute average distance
    if isinstance(test_input[0], (int, float)):
        distances = []
        for executed in executed_inputs:
            if isinstance(executed[0], (int, float)):
                dist = abs(test_input[0] - executed[0])
                distances.append(dist)
        
        if distances:
            avg_distance = sum(distances) / len(distances)
            # Normalize (assuming inputs in reasonable range)
            normalized = min(1.0, avg_distance / 100.0)
            return normalized
    
    # For other types, use simple uniqueness
    if test_input not in executed_inputs:
        return 1.0
    else:
        return 0.1


def compute_violation_focused_score(
    test_input: Tuple[object, ...],
    violation_history: Dict[Tuple[object, ...], int],
    similar_inputs: Optional[Callable[[Tuple[object, ...]], List[Tuple[object, ...]]]] = None,
) -> float:
    """
    Compute violation-focused score for a test case.
    
    Higher scores for inputs similar to previously violated cases.
    
    Args:
        test_input: Test case input
        violation_history: History of violations by input
        similar_inputs: Optional function to find similar inputs
    
    Returns:
        Violation-focused score between 0 and 1
    """
    if not violation_history:
        return 0.0
    
    # Direct match
    if test_input in violation_history:
        return 1.0
    
    # Similar inputs
    if similar_inputs is not None:
        similar = similar_inputs(test_input)
        for sim_input in similar:
            if sim_input in violation_history:
                return 0.7
    
    # Check for similar patterns (simple heuristic)
    # For numeric inputs, check nearby values
    if isinstance(test_input[0], (int, float)):
        for viol_input, count in violation_history.items():
            if isinstance(viol_input[0], (int, float)):
                distance = abs(test_input[0] - viol_input[0])
                if distance < 10:  # Within 10 units
                    return 0.5
    
    return 0.0


def score_test_cases(
    test_inputs: Sequence[Tuple[object, ...]],
    baseline_results: Sequence[Optional[JSONDict]],
    candidate_results: Sequence[Optional[JSONDict]],
    strategy: SamplingStrategy,
    violation_history: Optional[Dict[Tuple[object, ...], int]] = None,
    cluster_key: Optional[Callable[[Tuple[object, ...]], object]] = None,
) -> List[TestCaseScore]:
    """
    Score all test cases based on the sampling strategy.
    
    Args:
        test_inputs: All test case inputs
        baseline_results: Baseline execution results (may be partial)
        candidate_results: Candidate execution results (may be partial)
        strategy: Sampling strategy configuration
        violation_history: History of violations by input
        cluster_key: Optional function to cluster inputs
    
    Returns:
        List of scored test cases, sorted by score (highest first)
    """
    if violation_history is None:
        violation_history = {}
    
    executed_inputs = [
        inp for i, inp in enumerate(test_inputs)
        if baseline_results[i] is not None or candidate_results[i] is not None
    ]
    
    scores = []
    for i, test_input in enumerate(test_inputs):
        # Skip already executed
        if baseline_results[i] is not None and candidate_results[i] is not None:
            continue
        
        score = 0.0
        reasons = []
        
        if strategy.method == "uncertainty":
            uncertainty = compute_uncertainty_score(
                baseline_results[i] if i < len(baseline_results) else None,
                candidate_results[i] if i < len(candidate_results) else None,
            )
            score = uncertainty
            reasons.append(f"uncertainty={uncertainty:.2f}")
        
        elif strategy.method == "diversity":
            diversity = compute_diversity_score(test_input, executed_inputs, cluster_key)
            score = diversity
            reasons.append(f"diversity={diversity:.2f}")
        
        elif strategy.method == "violation_focused":
            violation_score = compute_violation_focused_score(
                test_input, violation_history
            )
            score = violation_score
            reasons.append(f"violation_focused={violation_score:.2f}")
        
        elif strategy.method == "hybrid":
            # Combine multiple strategies
            uncertainty = compute_uncertainty_score(
                baseline_results[i] if i < len(baseline_results) else None,
                candidate_results[i] if i < len(candidate_results) else None,
            )
            diversity = compute_diversity_score(test_input, executed_inputs, cluster_key)
            violation_score = compute_violation_focused_score(
                test_input, violation_history
            )
            
            score = (
                uncertainty * (1.0 - strategy.diversity_weight - strategy.violation_weight) +
                diversity * strategy.diversity_weight +
                violation_score * strategy.violation_weight
            )
            reasons.append(f"uncertainty={uncertainty:.2f}")
            reasons.append(f"diversity={diversity:.2f}")
            reasons.append(f"violation_focused={violation_score:.2f}")
        
        scores.append(TestCaseScore(index=i, score=score, reasons=reasons))
    
    # Sort by score (highest first)
    scores.sort(key=lambda x: x.score, reverse=True)
    return scores


def select_next_batch(
    test_inputs: Sequence[Tuple[object, ...]],
    baseline_results: Sequence[Optional[JSONDict]],
    candidate_results: Sequence[Optional[JSONDict]],
    strategy: SamplingStrategy,
    violation_history: Optional[Dict[Tuple[object, ...], int]] = None,
    cluster_key: Optional[Callable[[Tuple[object, ...]], object]] = None,
    rng: Optional[random.Random] = None,
) -> List[int]:
    """
    Select the next batch of test cases to execute using adaptive sampling.
    
    Args:
        test_inputs: All test case inputs
        baseline_results: Baseline execution results (may be partial)
        candidate_results: Candidate execution results (may be partial)
        strategy: Sampling strategy configuration
        violation_history: History of violations by input
        cluster_key: Optional function to cluster inputs
        rng: Random number generator for tie-breaking
    
    Returns:
        List of indices for test cases to execute next
    """
    if rng is None:
        rng = random.Random()
    
    # Score all test cases
    scored = score_test_cases(
        test_inputs,
        baseline_results,
        candidate_results,
        strategy,
        violation_history,
        cluster_key,
    )
    
    # Select top-scoring cases
    batch_size = min(strategy.batch_size, len(scored))
    selected = [case.index for case in scored[:batch_size]]
    
    # Add some randomness for exploration
    if len(scored) > batch_size:
        # Select a few random cases from the rest
        remaining = [case.index for case in scored[batch_size:]]
        if remaining:
            num_random = min(2, len(remaining))
            random_selected = rng.sample(remaining, num_random)
            selected.extend(random_selected)
    
    return selected

