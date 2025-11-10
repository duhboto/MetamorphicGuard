"""
Test harness for running evaluations and computing bootstrap confidence intervals.
"""

from __future__ import annotations

import hashlib
import math
import random
import uuid
from statistics import NormalDist
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from .sandbox import run_in_sandbox
from .specs import Spec, get_task
from .util import (
    compute_spec_fingerprint,
    get_environment_fingerprint,
    collect_job_metadata,
    sha256_file,
    write_failed_artifacts,
)
from .dispatch import Dispatcher, ensure_dispatcher
from .monitoring import Monitor, MonitorContext
from .observability import add_log_context, increment_metric, log_event


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
    ci_method: str = "bootstrap",
    rr_ci_method: str = "log",
    executor: str | None = None,
    executor_config: Dict[str, Any] | None = None,
    dispatcher: Dispatcher | str | None = None,
    queue_config: Dict[str, Any] | None = None,
    monitors: Sequence[Monitor] | None = None,
    failed_artifact_limit: Optional[int] = None,
    failed_artifact_ttl_days: Optional[int] = None,
    policy_version: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run evaluation comparing baseline and candidate implementations.

    Returns comprehensive metrics including bootstrap confidence intervals.
    """
    spec = get_task(task_name)
    test_inputs = spec.gen_inputs(n, seed)

    worker_count = max(1, parallel or 1)
    dispatcher_obj = ensure_dispatcher(dispatcher, worker_count, queue_config)

    monitor_objs = list(monitors or [])
    if monitor_objs:
        context = MonitorContext(task=task_name, total_cases=n)
        for monitor in monitor_objs:
            monitor.start(context)

    run_id = f"eval-{uuid.uuid4().hex}"
    add_log_context(run_id=run_id)
    log_event(
        "run_eval_start",
        task=task_name,
        total_cases=n,
        dispatcher=getattr(dispatcher_obj, "kind", "local"),
        executor=executor,
    )

    def make_runner(file_path: str) -> Callable[[int, Tuple[Any, ...]], Dict[str, Any]]:
        def _run_case(index: int, call_args: Tuple[Any, ...]) -> Dict[str, Any]:
            return run_in_sandbox(
                file_path,
                "solve",
                call_args,
                timeout_s,
                mem_mb,
                executor=executor,
                executor_config=executor_config,
            )
        return _run_case

    baseline_results = dispatcher_obj.execute(
        test_inputs=test_inputs,
        run_case=make_runner(baseline_path),
        role="baseline",
        monitors=monitor_objs,
        call_spec=_build_call_spec(
            baseline_path,
            timeout_s=timeout_s,
            mem_mb=mem_mb,
            executor=executor,
            executor_config=executor_config,
        ),
    )
    candidate_results = dispatcher_obj.execute(
        test_inputs=test_inputs,
        run_case=make_runner(candidate_path),
        role="candidate",
        monitors=monitor_objs,
        call_spec=_build_call_spec(
            candidate_path,
            timeout_s=timeout_s,
            mem_mb=mem_mb,
            executor=executor,
            executor_config=executor_config,
        ),
    )

    baseline_metrics = _evaluate_results(
        baseline_results,
        spec,
        test_inputs,
        violation_cap,
        role="baseline",
        seed=seed,
        rerun=lambda call_args: run_in_sandbox(
            baseline_path,
            "solve",
            call_args,
            timeout_s,
            mem_mb,
            executor=executor,
            executor_config=executor_config,
        ),
    )
    candidate_metrics = _evaluate_results(
        candidate_results,
        spec,
        test_inputs,
        violation_cap,
        role="candidate",
        seed=seed,
        rerun=lambda call_args: run_in_sandbox(
            candidate_path,
            "solve",
            call_args,
            timeout_s,
            mem_mb,
            executor=executor,
            executor_config=executor_config,
        ),
    )

    delta_ci = _compute_delta_ci(
        baseline_metrics,
        candidate_metrics,
        alpha=alpha,
        seed=seed,
        samples=bootstrap_samples,
        method=ci_method,
    )

    baseline_hash = sha256_file(baseline_path)
    candidate_hash = sha256_file(candidate_path)
    spec_fingerprint = compute_spec_fingerprint(spec)
    rr_value, rr_ci = _compute_relative_risk(
        baseline_metrics,
        candidate_metrics,
        alpha=alpha,
        method=rr_ci_method,
    )

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
            "ci_method": ci_method,
            "rr_ci_method": rr_ci_method,
            "executor": executor,
            "executor_config": executor_config,
            "dispatcher": getattr(dispatcher_obj, "kind", "local"),
            "queue_config": queue_config,
        },
        "hashes": {
            "baseline": baseline_hash,
            "candidate": candidate_hash,
        },
        "spec_fingerprint": spec_fingerprint,
        "baseline": {
            "passes": baseline_metrics["passes"],
            "total": baseline_metrics["total"],
            "pass_rate": baseline_metrics["pass_rate"],
            "prop_violations": baseline_metrics["prop_violations"],
            "mr_violations": baseline_metrics["mr_violations"],
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
        "relative_risk": rr_value,
        "relative_risk_ci": rr_ci,
        "environment": get_environment_fingerprint(),
        "job_metadata": collect_job_metadata(),
    }
    result["job_metadata"]["run_id"] = run_id
    if policy_version is not None:
        result["config"]["policy_version"] = policy_version

    if monitor_objs:
        result["config"]["monitors"] = [monitor.identifier() for monitor in monitor_objs]
        result["monitors"] = {
            monitor.identifier(): monitor.finalize() for monitor in monitor_objs
        }

    log_event(
        "run_eval_complete",
        task=task_name,
        candidate_passes=result["candidate"]["passes"],
        candidate_total=result["candidate"]["total"],
        baseline_passes=result["baseline"]["passes"],
        baseline_total=result["baseline"]["total"],
        delta=result["delta_pass_rate"],
    )

    decision = result.get("decision") or {}
    if (
        not decision.get("adopt", True)
        or result["candidate"].get("prop_violations")
        or result["candidate"].get("mr_violations")
    ):
        write_failed_artifacts(
            result,
            limit=failed_artifact_limit,
            ttl_days=failed_artifact_ttl_days,
            run_id=run_id,
        )

    return result


def _evaluate_results(
    results: Sequence[Dict[str, Any]],
    spec: Spec,
    test_inputs: Sequence[Tuple[Any, ...]],
    violation_cap: int,
    *,
    role: str,
    seed: int,
    rerun: Callable[[Tuple[Any, ...]], Dict[str, Any]],
) -> Dict[str, Any]:
    """Evaluate results against properties and metamorphic relations."""
    passes = 0
    total = len(results)
    prop_violations: list[Dict[str, Any]] = []
    mr_violations: list[Dict[str, Any]] = []
    pass_indicators: list[int] = []
    rerun_cache: Dict[str, Dict[str, Any]] = {}

    for idx, (result, args) in enumerate(zip(results, test_inputs)):
        if not result["success"]:
            pass_indicators.append(0)
            increment_metric(role, "failure")
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
            increment_metric(role, "failure")
            continue

        mr_passed = True
        for relation_index, relation in enumerate(spec.relations):
            relation_rng = None
            if relation.accepts_rng:
                relation_rng = _relation_rng(seed, idx, relation_index, relation.name)
            try:
                if relation.accepts_rng:
                    transformed_args = relation.transform(*args, rng=relation_rng)
                else:
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

            cache_key = _relation_cache_key(relation_index, transformed_args)
            if cache_key in rerun_cache:
                relation_result = rerun_cache[cache_key]
            else:
                relation_result = rerun(transformed_args)
                rerun_cache[cache_key] = relation_result
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
            increment_metric(role, "success")
        else:
            pass_indicators.append(0)
            increment_metric(role, "failure")

    return {
        "passes": passes,
        "total": total,
        "pass_rate": passes / total if total else 0.0,
        "prop_violations": prop_violations,
        "mr_violations": mr_violations,
        "pass_indicators": pass_indicators,
    }


def _relation_rng(
    seed: int,
    case_index: int,
    relation_index: int,
    relation_name: str,
) -> random.Random:
    """
    Build a deterministic RNG for a relation invocation.

    The construction uses a stable hash so results are reproducible across Python
    invocations regardless of PYTHONHASHSEED.
    """
    payload = f"{seed}:{case_index}:{relation_index}:{relation_name}".encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    seed_int = int.from_bytes(digest[:8], "big")
    return random.Random(seed_int)


def _relation_cache_key(relation_index: int, args: Tuple[Any, ...]) -> str:
    """Build a stable cache key for relation reruns."""
    return f"{relation_index}:{repr(args)}"


def _build_call_spec(
    file_path: str,
    *,
    timeout_s: float,
    mem_mb: int,
    executor: str | None,
    executor_config: Dict[str, Any] | None,
) -> Dict[str, Any]:
    spec: Dict[str, Any] = {
        "file_path": file_path,
        "func_name": "solve",
        "timeout_s": timeout_s,
        "mem_mb": mem_mb,
    }
    if executor is not None:
        spec["executor"] = executor
    if executor_config is not None:
        spec["executor_config"] = executor_config
    return spec


def _compute_delta_ci(
    baseline_metrics: Dict[str, Any],
    candidate_metrics: Dict[str, Any],
    *,
    alpha: float,
    seed: int,
    samples: int,
    method: str,
) -> List[float]:
    """Compute the pass-rate delta confidence interval using the requested method."""
    method = method.lower()
    if method == "bootstrap":
        return _compute_bootstrap_ci(
            baseline_metrics["pass_indicators"],
            candidate_metrics["pass_indicators"],
            alpha=alpha,
            seed=seed,
            samples=samples,
        )
    if method in {"newcombe", "wilson"}:
        return _compute_newcombe_ci(
            baseline_metrics["passes"],
            baseline_metrics["total"],
            candidate_metrics["passes"],
            candidate_metrics["total"],
            alpha=alpha,
        )
    raise ValueError(f"Unsupported CI method: {method}")


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
    if n == 0 or len(candidate_indicators) != n:
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


def _compute_newcombe_ci(
    baseline_passes: int,
    baseline_total: int,
    candidate_passes: int,
    candidate_total: int,
    *,
    alpha: float,
) -> List[float]:
    """Compute the score CI for difference in proportions using Newcombe's method."""
    if baseline_total == 0 or candidate_total == 0:
        return [0.0, 0.0]

    lower_b, upper_b = _wilson_interval(baseline_passes, baseline_total, alpha)
    lower_c, upper_c = _wilson_interval(candidate_passes, candidate_total, alpha)

    delta_lower = lower_c - upper_b
    delta_upper = upper_c - lower_b
    return [float(delta_lower), float(delta_upper)]


def _wilson_interval(successes: int, total: int, alpha: float) -> Tuple[float, float]:
    if total == 0:
        return (0.0, 0.0)

    z = NormalDist().inv_cdf(1 - alpha / 2)
    phat = successes / total
    denom = 1 + (z ** 2) / total
    center = phat + (z ** 2) / (2 * total)
    margin = z * math.sqrt((phat * (1 - phat) + (z ** 2) / (4 * total)) / total)
    lower = (center - margin) / denom
    upper = (center + margin) / denom
    return (max(0.0, lower), min(1.0, upper))


def _compute_relative_risk(
    baseline_metrics: Dict[str, Any],
    candidate_metrics: Dict[str, Any],
    *,
    alpha: float,
    method: str,
) -> Tuple[float, List[float]]:
    """Compute relative risk (candidate/baseline pass rate) with confidence interval."""
    p_b = baseline_metrics.get("pass_rate")
    if p_b is None:
        total_b = baseline_metrics.get("total", 0)
        p_b = baseline_metrics.get("passes", 0) / total_b if total_b else 0.0

    p_c = candidate_metrics.get("pass_rate")
    if p_c is None:
        total_c = candidate_metrics.get("total", 0)
        p_c = candidate_metrics.get("passes", 0) / total_c if total_c else 0.0

    if p_b == 0:
        return float("inf"), [float("inf"), float("inf")]

    rr = p_c / p_b
    method = method.lower()
    if method != "log":
        raise ValueError(f"Unsupported relative risk CI method: {method}")

    # Katz log method
    total_b = max(1, baseline_metrics.get("total", 0))
    total_c = max(1, candidate_metrics.get("total", 0))
    successes_b = max(1, baseline_metrics.get("passes", 0))
    successes_c = max(1, candidate_metrics.get("passes", 0))
    failures_b = max(1, total_b - successes_b)
    failures_c = max(1, total_c - successes_c)

    ln_rr = math.log(rr) if rr > 0 else float("-inf")
    se = math.sqrt((1 / successes_c) - (1 / total_c) +
                   (1 / successes_b) - (1 / total_b))
    z = NormalDist().inv_cdf(1 - alpha / 2)
    lower = math.exp(ln_rr - z * se)
    upper = math.exp(ln_rr + z * se)
    return rr, [float(lower), float(upper)]


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
