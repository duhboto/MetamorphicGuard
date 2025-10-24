"""
Test harness for running evaluations and computing bootstrap confidence intervals.
"""

import math
import random
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Iterable, List, Sequence, Tuple

from .sandbox import run_in_sandbox
from .specs import Spec, get_task
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
    parallel: int | None = None,
    improve_delta: float = 0.02,
    bootstrap_samples: int = 1000,
) -> Dict[str, Any]:
    """
    Run evaluation comparing baseline and candidate implementations.

    Returns comprehensive metrics including bootstrap confidence intervals.
    """
    spec = get_task(task_name)
    test_inputs = spec.gen_inputs(n, seed)

    worker_count = max(1, parallel or 1)
    baseline_results = _execute_suite(
        baseline_path,
        test_inputs,
        timeout_s=timeout_s,
        mem_mb=mem_mb,
        workers=worker_count,
    )
    candidate_results = _execute_suite(
        candidate_path,
        test_inputs,
        timeout_s=timeout_s,
        mem_mb=mem_mb,
        workers=worker_count,
    )

    baseline_metrics = _evaluate_results(
        baseline_results,
        spec,
        test_inputs,
        violation_cap,
        rerun=lambda call_args: run_in_sandbox(
            baseline_path,
            "solve",
            call_args,
            timeout_s,
            mem_mb,
        ),
    )
    candidate_metrics = _evaluate_results(
        candidate_results,
        spec,
        test_inputs,
        violation_cap,
        rerun=lambda call_args: run_in_sandbox(
            candidate_path,
            "solve",
            call_args,
            timeout_s,
            mem_mb,
        ),
    )

    delta_ci = _compute_bootstrap_ci(
        baseline_metrics["pass_indicators"],
        candidate_metrics["pass_indicators"],
        alpha=alpha,
        seed=seed,
        samples=bootstrap_samples,
    )

    baseline_hash = sha256_file(baseline_path)
    candidate_hash = sha256_file(candidate_path)

    result = {
        "task": task_name,
        "n": n,
        "seed": seed,
        "config": {
            "timeout_s": timeout_s,
            "mem_mb": mem_mb,
            "alpha": alpha,
            "improve_delta": improve_delta,
            "violation_cap": violation_cap,
            "parallel": worker_count,
            "bootstrap_samples": bootstrap_samples,
        },
        "hashes": {
            "baseline": baseline_hash,
            "candidate": candidate_hash,
        },
        "baseline": {
            "passes": baseline_metrics["passes"],
            "total": baseline_metrics["total"],
            "pass_rate": baseline_metrics["pass_rate"],
        },
        "candidate": {
            "passes": candidate_metrics["passes"],
            "total": candidate_metrics["total"],
            "pass_rate": candidate_metrics["pass_rate"],
            "prop_violations": candidate_metrics["prop_violations"],
            "mr_violations": candidate_metrics["mr_violations"],
        },
        "delta_pass_rate": candidate_metrics["pass_rate"] - baseline_metrics["pass_rate"],
        "delta_ci": delta_ci,
    }

    return result


def _execute_suite(
    file_path: str,
    test_inputs: Sequence[Tuple[Any, ...]],
    *,
    timeout_s: float,
    mem_mb: int,
    workers: int,
) -> List[Dict[str, Any]]:
    """Run the candidate/baseline across the generated inputs."""
    if workers <= 1:
        return [
            run_in_sandbox(file_path, "solve", args, timeout_s, mem_mb)
            for args in test_inputs
        ]

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                run_in_sandbox,
                file_path,
                "solve",
                args,
                timeout_s,
                mem_mb,
            )
            for args in test_inputs
        ]
    return [future.result() for future in futures]


def _evaluate_results(
    results: Sequence[Dict[str, Any]],
    spec: Spec,
    test_inputs: Sequence[Tuple[Any, ...]],
    violation_cap: int,
    rerun: Callable[[Tuple[Any, ...]], Dict[str, Any]],
) -> Dict[str, Any]:
    """Evaluate results against properties and metamorphic relations."""
    passes = 0
    total = len(results)
    prop_violations: list[Dict[str, Any]] = []
    mr_violations: list[Dict[str, Any]] = []
    pass_indicators: list[int] = []

    for idx, (result, args) in enumerate(zip(results, test_inputs)):
        if not result["success"]:
            pass_indicators.append(0)
            if len(prop_violations) < violation_cap:
                prop_violations.append(
                    {
                        "test_case": idx,
                        "property": "execution",
                        "input": spec.fmt_in(args),
                        "output": "",
                        "error": result.get("error") or "Execution failed",
                    }
                )
            continue

        output = result["result"]
        prop_passed = True
        for prop in spec.properties:
            if prop.mode != "hard":
                continue
            try:
                if not prop.check(output, *args):
                    prop_passed = False
                    if len(prop_violations) < violation_cap:
                        prop_violations.append(
                            {
                                "test_case": idx,
                                "property": prop.description,
                                "input": spec.fmt_in(args),
                                "output": spec.fmt_out(output),
                            }
                        )
            except Exception as exc:  # pragma: no cover - defensive logging
                prop_passed = False
                if len(prop_violations) < violation_cap:
                    prop_violations.append(
                        {
                            "test_case": idx,
                            "property": prop.description,
                            "input": spec.fmt_in(args),
                            "output": spec.fmt_out(output),
                            "error": str(exc),
                        }
                    )

        if not prop_passed:
            pass_indicators.append(0)
            continue

        mr_passed = True
        for relation in spec.relations:
            try:
                transformed_args = relation.transform(*args)
            except Exception as exc:
                mr_passed = False
                if len(mr_violations) < violation_cap:
                    mr_violations.append(
                        {
                            "test_case": idx,
                            "relation": relation.name,
                            "input": spec.fmt_in(args),
                            "output": spec.fmt_out(output),
                            "error": str(exc),
                        }
                    )
                break

            relation_result = rerun(transformed_args)
            if not relation_result["success"]:
                mr_passed = False
                if len(mr_violations) < violation_cap:
                    mr_violations.append(
                        {
                            "test_case": idx,
                            "relation": relation.name,
                            "input": spec.fmt_in(transformed_args),
                            "output": "",
                            "error": relation_result.get("error") or "Execution failed",
                        }
                    )
                break

            relation_output = relation_result["result"]
            if relation.expect == "equal":
                equivalent = spec.equivalence(output, relation_output)
            else:  # pragma: no cover - placeholder for future relation modes
                raise ValueError(f"Unsupported relation expectation: {relation.expect}")

            if not equivalent:
                mr_passed = False
                if len(mr_violations) < violation_cap:
                    mr_violations.append(
                        {
                            "test_case": idx,
                            "relation": relation.name,
                            "input": spec.fmt_in(args),
                            "output": spec.fmt_out(output),
                            "relation_output": spec.fmt_out(relation_output),
                        }
                    )
                break

        if mr_passed:
            passes += 1
            pass_indicators.append(1)
        else:
            pass_indicators.append(0)

    return {
        "passes": passes,
        "total": total,
        "pass_rate": passes / total if total else 0.0,
        "prop_violations": prop_violations,
        "mr_violations": mr_violations,
        "pass_indicators": pass_indicators,
    }


def _compute_bootstrap_ci(
    baseline_indicators: Sequence[int],
    candidate_indicators: Sequence[int],
    *,
    alpha: float,
    seed: int,
    samples: int,
) -> List[float]:
    """Compute a percentile bootstrap confidence interval for the pass-rate delta."""
    n = len(baseline_indicators)
    if n == 0:
        return [0.0, 0.0]

    rng = random.Random(seed)
    deltas: list[float] = []

    for _ in range(max(1, samples)):
        baseline_sample = [baseline_indicators[rng.randrange(n)] for _ in range(n)]
        candidate_sample = [candidate_indicators[rng.randrange(n)] for _ in range(n)]

        p_baseline = sum(baseline_sample) / n
        p_candidate = sum(candidate_sample) / n
        deltas.append(p_candidate - p_baseline)

    lower_quantile = alpha / 2
    upper_quantile = 1 - alpha / 2
    ci_lower = _percentile(deltas, lower_quantile)
    ci_upper = _percentile(deltas, upper_quantile)
    return [float(ci_lower), float(ci_upper)]


def _percentile(values: Sequence[float], q: float) -> float:
    """Compute the q-th percentile (0 <= q <= 1) using linear interpolation."""
    if not values:
        return 0.0
    if q <= 0:
        return float(min(values))
    if q >= 1:
        return float(max(values))

    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * q
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_vals[int(k)])
    d0 = sorted_vals[f] * (c - k)
    d1 = sorted_vals[c] * (k - f)
    return float(d0 + d1)
