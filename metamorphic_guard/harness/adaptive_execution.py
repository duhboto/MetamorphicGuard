"""
Adaptive execution wrapper for incremental evaluation with power-based stopping.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..adaptive import AdaptiveConfig, AdaptiveDecision, compute_interim_metrics, should_continue_adaptive
from .reporting import evaluate_roles
from ..observability import log_event
from ..specs import Spec
from .execution import ExecutionPlan, execute_implementations, prepare_execution_plan


def execute_adaptively(
    *,
    plan: ExecutionPlan,
    baseline_path: str,
    candidate_path: str,
    timeout_s: float,
    mem_mb: int,
    executor: Optional[str],
    executor_config: Dict[str, Any] | None,
    baseline_executor: Optional[str],
    baseline_executor_config: Dict[str, Any] | None,
    candidate_executor: Optional[str],
    candidate_executor_config: Dict[str, Any] | None,
    alpha: float,
    min_delta: float,
    power_target: float,
    adaptive_config: AdaptiveConfig,
    violation_cap: int,
    seed: int,
    shrink_violations: bool,
    spec: Spec,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    """
    Execute baseline and candidate with adaptive sample size determination.
    
    Args:
        plan: Initial execution plan
        baseline_path: Path to baseline implementation
        candidate_path: Path to candidate implementation
        timeout_s: Timeout per test case
        mem_mb: Memory limit per test case
        executor: Executor name
        executor_config: Executor configuration
        baseline_executor: Baseline-specific executor
        baseline_executor_config: Baseline executor config
        candidate_executor: Candidate-specific executor
        candidate_executor_config: Candidate executor config
        alpha: Significance level
        min_delta: Minimum detectable effect
        power_target: Target power
        adaptive_config: Adaptive testing configuration
        violation_cap: Maximum violations to record
        seed: Random seed
        shrink_violations: Whether to shrink violations
        spec: Task specification
        
    Returns:
        Tuple of (baseline_results, candidate_results, adaptive_metadata)
    """
    if not adaptive_config.enabled:
        # If adaptive testing is disabled, execute normally
        baseline_results, candidate_results = execute_implementations(
            plan,
            baseline_path=baseline_path,
            candidate_path=candidate_path,
            timeout_s=timeout_s,
            mem_mb=mem_mb,
            executor=executor,
            executor_config=executor_config,
            baseline_executor=baseline_executor,
            baseline_executor_config=baseline_executor_config,
            candidate_executor=candidate_executor,
            candidate_executor_config=candidate_executor_config,
        )
        return baseline_results, candidate_results, {"adaptive_testing": False}
    
    # Adaptive execution: execute in batches and check power
    test_inputs = plan.test_inputs
    baseline_results: List[Dict[str, Any]] = []
    candidate_results: List[Dict[str, Any]] = []
    adaptive_metadata: Dict[str, Any] = {
        "adaptive_testing": True,
        "decisions": [],
        "final_n": 0,
        "early_stop": False,
    }
    
    current_n = len(test_inputs)
    chunk_size = adaptive_config.check_interval
    next_check = adaptive_config.min_sample_size
    final_n = current_n  # May be adjusted
    
    # Execute in chunks, checking power after each
    processed = 0
    while processed < len(test_inputs):
        # Determine how many to execute in this chunk
        chunk_end = min(processed + chunk_size, len(test_inputs))
        chunk_inputs = test_inputs[processed:chunk_end]
        
        # Create a temporary plan for this chunk
        chunk_plan = ExecutionPlan(
            spec=plan.spec,
            test_inputs=chunk_inputs,
            dispatcher=plan.dispatcher,
            monitors=plan.monitors,
            worker_count=plan.worker_count,
            run_id=plan.run_id,
        )
        
        # Execute this chunk
        chunk_baseline, chunk_candidate = execute_implementations(
            chunk_plan,
            baseline_path=baseline_path,
            candidate_path=candidate_path,
            timeout_s=timeout_s,
            mem_mb=mem_mb,
            executor=executor,
            executor_config=executor_config,
            baseline_executor=baseline_executor,
            baseline_executor_config=baseline_executor_config,
            candidate_executor=candidate_executor,
            candidate_executor_config=candidate_executor_config,
        )
        
        baseline_results.extend(chunk_baseline)
        candidate_results.extend(chunk_candidate)
        processed = len(baseline_results)
        
        # Check if we should check power at this point
        if processed >= next_check:
            # Compute interim metrics
            interim_baseline, interim_candidate = compute_interim_metrics(
                baseline_results,
                candidate_results,
                spec=spec,
            )
            
            # Evaluate results to get proper metrics
            baseline_metrics, candidate_metrics = evaluate_roles(
                spec=spec,
                test_inputs=test_inputs[:processed],
                baseline_results=baseline_results,
                candidate_results=candidate_results,
                baseline_path=baseline_path,
                candidate_path=candidate_path,
                timeout_s=timeout_s,
                mem_mb=mem_mb,
                violation_cap=violation_cap,
                seed=seed,
                executor=executor,
                executor_config=executor_config,
                shrink_violations=shrink_violations,
            )
            
            # Check adaptive decision
            decision = should_continue_adaptive(
                baseline_metrics=baseline_metrics,
                candidate_metrics=candidate_metrics,
                current_n=processed,
                alpha=alpha,
                min_delta=min_delta,
                power_target=power_target,
                config=adaptive_config,
            )
            
            adaptive_metadata["decisions"].append({
                "n": processed,
                "power": decision.current_power,
                "recommended_n": decision.recommended_n,
                "reason": decision.reason,
            })
            
            log_event(
                "adaptive_check",
                n=processed,
                power=decision.current_power,
                recommended_n=decision.recommended_n,
                reason=decision.reason,
            )
            
            if not decision.continue_sampling:
                # Stop early
                adaptive_metadata["early_stop"] = True
                adaptive_metadata["final_n"] = processed
                final_n = processed
                break
            
            # Update next check point
            if decision.recommended_n is not None and decision.recommended_n > processed:
                # Increase sample size if recommended
                final_n = min(decision.recommended_n, adaptive_config.max_sample_size or len(test_inputs))
                # Generate additional test cases if needed
                if final_n > len(test_inputs):
                    additional_needed = final_n - len(test_inputs)
                    additional_inputs = spec.gen_inputs(additional_needed, seed + len(test_inputs))
                    test_inputs.extend(additional_inputs)
            
            next_check = processed + adaptive_config.check_interval
    
    adaptive_metadata["final_n"] = final_n
    return baseline_results, candidate_results, adaptive_metadata

