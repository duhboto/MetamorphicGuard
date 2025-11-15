"""
Budget-aware execution to maximize information per dollar.

This module implements strategies to optimize test case selection and execution
order based on cost estimates and budget constraints.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .cost_estimation import estimate_case_cost
from .types import JSONDict


@dataclass
class BudgetConfig:
    """Configuration for budget-aware execution."""
    
    enabled: bool = True
    total_budget: float = 100.0  # Total budget in USD
    spent: float = 0.0  # Amount spent so far
    cost_per_case_estimate: Optional[float] = None
    prioritize_cheap: bool = True  # Prioritize cheaper cases first
    information_per_dollar_threshold: float = 0.1  # Minimum info per dollar


@dataclass
class CaseCostEstimate:
    """Cost estimate for a test case."""
    
    index: int
    estimated_cost: float
    information_value: float
    efficiency_ratio: float  # information_value / estimated_cost


def estimate_case_costs(
    test_inputs: Sequence[Tuple[object, ...]],
    executor_name: Optional[str] = None,
    executor_config: Optional[JSONDict] = None,
    cost_per_case: Optional[float] = None,
) -> List[float]:
    """
    Estimate costs for all test cases.
    
    Args:
        test_inputs: Test case inputs
        executor_name: Executor name (for LLM cost estimation)
        executor_config: Executor configuration
        cost_per_case: Fixed cost per case (if known)
    
    Returns:
        List of cost estimates for each test case
    """
    if cost_per_case is not None:
        return [cost_per_case] * len(test_inputs)
    
    costs = []
    for test_input in test_inputs:
        try:
            # Try to estimate cost for this specific case
            # For LLM executors, this might vary by input
            if executor_name in ("openai", "anthropic", "vllm"):
                # Rough estimate based on input size
                # In practice, this would use actual token estimation
                estimated = estimate_case_cost(
                    executor_name=executor_name or "openai",
                    executor_config=executor_config or {},
                    system_prompt="",  # Would need actual prompt
                    user_prompt=str(test_input),  # Simplified
                    max_tokens=512,
                )
                costs.append(estimated.get("estimated_cost_usd", 0.001))
            else:
                # Non-LLM executors have negligible cost
                costs.append(0.0)
        except Exception:
            # Fallback to default
            costs.append(0.001)
    
    return costs


def compute_information_value(
    test_input: Tuple[object, ...],
    baseline_result: Optional[JSONDict],
    candidate_result: Optional[JSONDict],
    violation_history: Optional[Dict[Tuple[object, ...], int]] = None,
) -> float:
    """
    Compute information value of a test case.
    
    Higher values indicate more useful information.
    
    Args:
        test_input: Test case input
        baseline_result: Baseline result (if available)
        candidate_result: Candidate result (if available)
        violation_history: History of violations
    
    Returns:
        Information value between 0 and 1
    """
    # If not executed, high value (no information yet)
    if baseline_result is None and candidate_result is None:
        return 1.0
    
    # If partially executed, medium-high value
    if baseline_result is None or candidate_result is None:
        return 0.7
    
    # If results differ, high value (potential violation)
    baseline_passed = baseline_result.get("passed", False)
    candidate_passed = candidate_result.get("passed", False)
    
    if baseline_passed != candidate_passed:
        return 0.9
    
    # If similar to violation history, higher value
    if violation_history and test_input in violation_history:
        return 0.8
    
    # Otherwise, lower value (already have information)
    return 0.2


def prioritize_by_efficiency(
    test_inputs: Sequence[Tuple[object, ...]],
    baseline_results: Sequence[Optional[JSONDict]],
    candidate_results: Sequence[Optional[JSONDict]],
    costs: Sequence[float],
    violation_history: Optional[Dict[Tuple[object, ...], int]] = None,
) -> List[int]:
    """
    Prioritize test cases by information-per-dollar efficiency.
    
    Args:
        test_inputs: All test case inputs
        baseline_results: Baseline results (may be partial)
        candidate_results: Candidate results (may be partial)
        costs: Cost estimates for each case
        violation_history: History of violations
    
    Returns:
        List of indices sorted by efficiency (highest first)
    """
    efficiencies = []
    
    for i, test_input in enumerate(test_inputs):
        # Skip already fully executed
        if (i < len(baseline_results) and baseline_results[i] is not None and
            i < len(candidate_results) and candidate_results[i] is not None):
            continue
        
        cost = costs[i] if i < len(costs) else 0.001
        info_value = compute_information_value(
            test_input,
            baseline_results[i] if i < len(baseline_results) else None,
            candidate_results[i] if i < len(candidate_results) else None,
            violation_history,
        )
        
        # Efficiency = information value / cost
        # Add small epsilon to avoid division by zero
        efficiency = info_value / (cost + 0.0001)
        
        efficiencies.append((i, efficiency))
    
    # Sort by efficiency (highest first)
    efficiencies.sort(key=lambda x: x[1], reverse=True)
    return [idx for idx, _ in efficiencies]


def select_within_budget(
    test_inputs: Sequence[Tuple[object, ...]],
    baseline_results: Sequence[Optional[JSONDict]],
    candidate_results: Sequence[Optional[JSONDict]],
    costs: Sequence[float],
    budget_config: BudgetConfig,
    violation_history: Optional[Dict[Tuple[object, ...], int]] = None,
) -> List[int]:
    """
    Select test cases to execute within budget constraints.
    
    Args:
        test_inputs: All test case inputs
        baseline_results: Baseline results (may be partial)
        candidate_results: Candidate results (may be partial)
        costs: Cost estimates for each case
        budget_config: Budget configuration
        violation_history: History of violations
    
    Returns:
        List of indices to execute
    """
    if not budget_config.enabled:
        # Return all unexecuted cases
        return [
            i for i in range(len(test_inputs))
            if (i >= len(baseline_results) or baseline_results[i] is None or
                i >= len(candidate_results) or candidate_results[i] is None)
        ]
    
    # Prioritize by efficiency
    prioritized = prioritize_by_efficiency(
        test_inputs, baseline_results, candidate_results, costs, violation_history
    )
    
    # Select cases within remaining budget
    remaining_budget = budget_config.total_budget - budget_config.spent
    selected = []
    total_cost = 0.0
    
    for idx in prioritized:
        cost = costs[idx] if idx < len(costs) else 0.001
        
        if total_cost + cost <= remaining_budget:
            selected.append(idx)
            total_cost += cost
        else:
            # Can't afford this case
            break
    
    return selected


def update_budget_tracking(
    budget_config: BudgetConfig,
    executed_indices: List[int],
    costs: Sequence[float],
    actual_costs: Optional[Dict[int, float]] = None,
) -> BudgetConfig:
    """
    Update budget tracking after execution.
    
    Args:
        budget_config: Current budget configuration
        executed_indices: Indices of executed cases
        costs: Estimated costs
        actual_costs: Actual costs (if available, overrides estimates)
    
    Returns:
        Updated budget configuration
    """
    total_spent = 0.0
    
    for idx in executed_indices:
        if actual_costs and idx in actual_costs:
            total_spent += actual_costs[idx]
        elif idx < len(costs):
            total_spent += costs[idx]
        else:
            total_spent += 0.001  # Default estimate
    
    return BudgetConfig(
        enabled=budget_config.enabled,
        total_budget=budget_config.total_budget,
        spent=budget_config.spent + total_spent,
        cost_per_case_estimate=budget_config.cost_per_case_estimate,
        prioritize_cheap=budget_config.prioritize_cheap,
        information_per_dollar_threshold=budget_config.information_per_dollar_threshold,
    )

