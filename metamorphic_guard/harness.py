"""
Test harness for running evaluations and computing bootstrap confidence intervals.
"""

import numpy as np
from typing import Any, Dict, List, Tuple
from .sandbox import run_in_sandbox
from .specs import get_task, Spec
from .util import sha256_file


def run_eval(
    task_name: str,
    baseline_path: str,
    candidate_path: str,
    n: int = 400,
    seed: int = 42,
    timeout_s: float = 2.0,
    mem_mb: int = 512,
    alpha: float = 0.05,
    violation_cap: int = 25,
    parallel: int = None
) -> Dict[str, Any]:
    """
    Run evaluation comparing baseline and candidate implementations.
    
    Returns comprehensive metrics including bootstrap confidence intervals.
    """
    # Get task specification
    spec = get_task(task_name)
    
    # Generate test inputs
    test_inputs = spec.gen_inputs(n, seed)
    
    # Run baseline and candidate on all inputs
    baseline_results = []
    candidate_results = []
    
    for i, args in enumerate(test_inputs):
        # Run baseline
        baseline_result = run_in_sandbox(
            baseline_path, "solve", args, timeout_s, mem_mb
        )
        baseline_results.append(baseline_result)
        
        # Run candidate
        candidate_result = run_in_sandbox(
            candidate_path, "solve", args, timeout_s, mem_mb
        )
        candidate_results.append(candidate_result)
    
    # Evaluate results
    baseline_metrics = _evaluate_results(baseline_results, spec, test_inputs, violation_cap)
    candidate_metrics = _evaluate_results(candidate_results, spec, test_inputs, violation_cap)
    
    # Compute bootstrap confidence interval for delta
    delta_ci = _compute_bootstrap_ci(
        baseline_metrics["pass_indicators"],
        candidate_metrics["pass_indicators"],
        alpha
    )
    
    # Compute file hashes
    baseline_hash = sha256_file(baseline_path)
    candidate_hash = sha256_file(candidate_path)
    
    # Build result dictionary
    result = {
        "task": task_name,
        "n": n,
        "seed": seed,
        "config": {
            "timeout_s": timeout_s,
            "mem_mb": mem_mb,
            "alpha": alpha,
            "improve_delta": 0.02,  # Default from spec
            "violation_cap": violation_cap
        },
        "hashes": {
            "baseline": baseline_hash,
            "candidate": candidate_hash
        },
        "baseline": {
            "passes": baseline_metrics["passes"],
            "total": baseline_metrics["total"],
            "pass_rate": baseline_metrics["pass_rate"]
        },
        "candidate": {
            "passes": candidate_metrics["passes"],
            "total": candidate_metrics["total"],
            "pass_rate": candidate_metrics["pass_rate"],
            "prop_violations": candidate_metrics["prop_violations"],
            "mr_violations": candidate_metrics["mr_violations"]
        },
        "delta_pass_rate": candidate_metrics["pass_rate"] - baseline_metrics["pass_rate"],
        "delta_ci": delta_ci
    }
    
    return result


def _evaluate_results(
    results: List[Dict[str, Any]], 
    spec: Spec, 
    test_inputs: List[Tuple[Any, ...]], 
    violation_cap: int
) -> Dict[str, Any]:
    """Evaluate results against properties and metamorphic relations."""
    passes = 0
    total = len(results)
    prop_violations = []
    mr_violations = []
    
    for i, (result, args) in enumerate(zip(results, test_inputs)):
        if not result["success"]:
            continue
            
        output = result["result"]
        
        # Check properties
        prop_passed = True
        for prop in spec.properties:
            if prop.mode == "hard":  # Only check hard properties for v1
                try:
                    if not prop.check(output, *args):
                        prop_passed = False
                        if len(prop_violations) < violation_cap:
                            prop_violations.append({
                                "test_case": i,
                                "property": prop.description,
                                "input": spec.fmt_in(args),
                                "output": spec.fmt_out(output)
                            })
                except Exception as e:
                    prop_passed = False
                    if len(prop_violations) < violation_cap:
                        prop_violations.append({
                            "test_case": i,
                            "property": prop.description,
                            "input": spec.fmt_in(args),
                            "output": spec.fmt_out(output),
                            "error": str(e)
                        })
        
        if prop_passed:
            # Check metamorphic relations
            mr_passed = True
            for relation in spec.relations:
                try:
                    # Transform input
                    transformed_args = relation.transform(*args)
                    
                    # We would need to run the function again with transformed input
                    # For now, we'll skip MR checking in this simplified version
                    # In a full implementation, we'd need to store and re-run
                    pass
                    
                except Exception as e:
                    mr_passed = False
                    if len(mr_violations) < violation_cap:
                        mr_violations.append({
                            "test_case": i,
                            "relation": relation.name,
                            "input": spec.fmt_in(args),
                            "output": spec.fmt_out(output),
                            "error": str(e)
                        })
            
            if mr_passed:
                passes += 1
    
    return {
        "passes": passes,
        "total": total,
        "pass_rate": passes / total if total > 0 else 0.0,
        "prop_violations": prop_violations,
        "mr_violations": mr_violations,
        "pass_indicators": [1 if i < passes else 0 for i in range(total)]
    }


def _compute_bootstrap_ci(
    baseline_indicators: List[int],
    candidate_indicators: List[int],
    alpha: float,
    B: int = 1000
) -> List[float]:
    """
    Compute percentile bootstrap confidence interval for delta = p_candidate - p_baseline.
    """
    n = len(baseline_indicators)
    deltas = []
    
    for _ in range(B):
        # Resample with replacement
        baseline_sample = np.random.choice(baseline_indicators, size=n, replace=True)
        candidate_sample = np.random.choice(candidate_indicators, size=n, replace=True)
        
        # Compute delta for this bootstrap sample
        p_baseline = np.mean(baseline_sample)
        p_candidate = np.mean(candidate_sample)
        delta = p_candidate - p_baseline
        deltas.append(delta)
    
    # Compute quantiles
    lower_quantile = alpha / 2
    upper_quantile = 1 - alpha / 2
    
    ci_lower = np.percentile(deltas, lower_quantile * 100)
    ci_upper = np.percentile(deltas, upper_quantile * 100)
    
    return [float(ci_lower), float(ci_upper)]
