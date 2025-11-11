"""
Test harness for running evaluations and computing bootstrap confidence intervals.
"""

from __future__ import annotations

import hashlib
import json
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


def _serialize_for_report(value: Any) -> Any:
    """
    Convert an arbitrary object into a JSON-friendly structure.
    Non-serializable objects are represented via repr().
    """
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        if isinstance(value, dict):
            return {str(k): _serialize_for_report(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [_serialize_for_report(item) for item in value]
        return repr(value)
from .dispatch import Dispatcher, ensure_dispatcher
from .monitoring import Monitor, MonitorContext
from .observability import add_log_context, increment_metric, log_event
from .gate import decide_adopt


def _compute_trust_scores(
    results: Sequence[Dict[str, Any]],
    test_inputs: Sequence[Tuple[Any, ...]],
    spec: Spec,
) -> Optional[Dict[str, Any]]:
    """
    Compute trust scores for RAG evaluations if applicable.
    
    Args:
        results: Evaluation results
        test_inputs: Test input tuples
        spec: Task specification
        
    Returns:
        Trust scores dictionary or None if not applicable
    """
    try:
        from .rag_guards import assess
        
        # Check if this looks like a RAG evaluation
        # RAG evaluations typically have prompts and sources in inputs
        trust_scores_list = []
        
        for result, args in zip(results, test_inputs):
            if not result.get("success"):
                continue
                
            output = result.get("result", "")
            if not isinstance(output, str):
                continue
                
            # Try to extract question and sources from inputs
            # For LLM evaluations, args might be (prompt, system_prompt) or similar
            if len(args) >= 1:
                question = str(args[0]) if args[0] else ""
                sources = []
                
                # Try to find sources in remaining args or in the result metadata
                if len(args) > 1:
                    for arg in args[1:]:
                        if isinstance(arg, str) and len(arg) > 50:
                            sources.append(arg)
                        elif isinstance(arg, (list, tuple)):
                            sources.extend([str(s) for s in arg if isinstance(s, str)])
                
                # If we have question and output, compute trust score
                if question and output and sources:
                    try:
                        score, flags = assess(
                            question=question,
                            answer=output,
                            sources=sources,
                            checks=["citation", "faithfulness", "coverage", "answerability", "novelty"],
                        )
                        trust_scores_list.append({
                            "score": score.score,
                            "flags": flags.to_dict(),
                            "details": score.details,
                        })
                    except Exception:
                        # Skip if trust scoring fails
                        continue
        
        if trust_scores_list:
            # Aggregate trust scores
            avg_score = sum(t["score"] for t in trust_scores_list) / len(trust_scores_list)
            
            # Aggregate flags (all must be True for overall flag to be True)
            aggregated_flags = {
                "citation_correct": all(t["flags"].get("citation_correct", True) for t in trust_scores_list),
                "citation_complete": all(t["flags"].get("citation_complete", True) for t in trust_scores_list),
                "coverage_sufficient": all(t["flags"].get("coverage_sufficient", True) for t in trust_scores_list),
                "answerable": all(t["flags"].get("answerable", True) for t in trust_scores_list),
                "novel_content": any(t["flags"].get("novel_content", False) for t in trust_scores_list),
            }
            
            return {
                "score": avg_score,
                "flags": aggregated_flags,
                "count": len(trust_scores_list),
                "individual_scores": trust_scores_list[:10],  # Keep first 10 for details
            }
    except ImportError:
        # RAG guards not available
        pass
    
    return None


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
    explicit_inputs: Optional[List[Tuple[Any, ...]]] = None,
    min_pass_rate: float = 0.80,
    power_target: float = 0.8,
    policy_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run evaluation comparing baseline and candidate implementations.

    Returns comprehensive metrics including bootstrap confidence intervals.
    """
    spec = get_task(task_name)

    if explicit_inputs is not None:
        test_inputs = [tuple(case) for case in explicit_inputs]
        n = len(test_inputs)
    else:
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

    def _estimate_power(
        p_baseline: float,
        p_candidate: float,
        sample_size: int,
        alpha_value: float,
        delta_value: float,
        power_target: float,
    ) -> Tuple[float, Optional[int]]:
        if sample_size == 0:
            return 0.0, None
        effect = p_candidate - p_baseline
        pooled_var = p_baseline * (1 - p_baseline) + p_candidate * (1 - p_candidate)
        if pooled_var == 0:
            power_val = 1.0 if effect >= delta_value else 0.0
            return power_val, None
        se = math.sqrt(pooled_var / sample_size)
        if se == 0:
            power_val = 1.0 if effect >= delta_value else 0.0
            return power_val, None

        z_alpha = NormalDist().inv_cdf(1 - alpha_value)
        z_effect = (effect - delta_value) / se
        power_val = 1 - NormalDist().cdf(z_alpha - z_effect)
        power_val = max(0.0, min(1.0, power_val))

        recommended_n = None
        if delta_value > 0 and power_target > 0 and power_target < 1:
            p1 = p_baseline
            p2 = max(0.0, min(1.0, p_baseline + delta_value))
            var_target = p1 * (1 - p1) + p2 * (1 - p2)
            if delta_value > 0 and var_target > 0:
                z_beta = NormalDist().inv_cdf(power_target)
                recommended_n = math.ceil(((z_alpha + z_beta) ** 2 * var_target) / (delta_value ** 2))
        return power_val, recommended_n
    
    # Compute trust scores if applicable (for RAG evaluations)
    baseline_trust = _compute_trust_scores(baseline_results, test_inputs, spec)
    candidate_trust = _compute_trust_scores(candidate_results, test_inputs, spec)

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
            "min_pass_rate": min_pass_rate,
            "violation_cap": violation_cap,
            "parallel": worker_count,
            "bootstrap_samples": bootstrap_samples,
            "ci_method": ci_method,
            "rr_ci_method": rr_ci_method,
            "executor": executor,
            "executor_config": _serialize_for_report(executor_config),
            "dispatcher": getattr(dispatcher_obj, "kind", "local"),
            "queue_config": _serialize_for_report(queue_config),
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
    
    result["cases"] = [
        {
            "index": index,
            "input": _serialize_for_report(args),
            "formatted": spec.fmt_in(args),
        }
        for index, args in enumerate(test_inputs)
    ]

    try:
        result["decision"] = decide_adopt(result, improve_delta=improve_delta, min_pass_rate=min_pass_rate)
    except Exception as exc:
        result["decision"] = {
            "adopt": False,
            "reason": f"gate_error: {exc}",
        }

    power_estimate, recommended_n = _estimate_power(
        baseline_metrics["pass_rate"],
        candidate_metrics["pass_rate"],
        n,
        alpha,
        improve_delta,
        power_target,
    )
    result["statistics"] = {
        "power_estimate": power_estimate,
        "power_target": power_target,
        "recommended_n": recommended_n,
        "min_delta": improve_delta,
        "alpha": alpha,
    }

    relation_summary: List[Dict[str, Any]] = []
    category_totals: Dict[str, Dict[str, Any]] = {}

    def _pass_rate(total: int, failures: int) -> Optional[float]:
        if total <= 0:
            return None
        return (total - failures) / total

    baseline_relation_stats = baseline_metrics.get("relation_stats", {})
    candidate_relation_stats = candidate_metrics.get("relation_stats", {})

    for relation in spec.relations:
        name = relation.name
        baseline_entry = baseline_relation_stats.get(name, {})
        candidate_entry = candidate_relation_stats.get(name, {})

        category = (
            baseline_entry.get("category")
            or candidate_entry.get("category")
            or relation.category
            or "uncategorized"
        )
        description = relation.description or baseline_entry.get("description") or candidate_entry.get("description")

        base_total = baseline_entry.get("total", 0)
        base_fail = baseline_entry.get("failures", 0)
        cand_total = candidate_entry.get("total", 0)
        cand_fail = candidate_entry.get("failures", 0)

        relation_summary.append(
            {
                "name": name,
                "category": category,
                "description": description,
                "baseline": {
                    "total": base_total,
                    "failures": base_fail,
                    "pass_rate": _pass_rate(base_total, base_fail),
                },
                "candidate": {
                    "total": cand_total,
                    "failures": cand_fail,
                    "pass_rate": _pass_rate(cand_total, cand_fail),
                },
            }
        )

        cat_entry = category_totals.setdefault(
            category,
            {
                "relations": 0,
                "baseline_total": 0,
                "baseline_failures": 0,
                "candidate_total": 0,
                "candidate_failures": 0,
            },
        )
        cat_entry["relations"] += 1
        cat_entry["baseline_total"] += base_total
        cat_entry["baseline_failures"] += base_fail
        cat_entry["candidate_total"] += cand_total
        cat_entry["candidate_failures"] += cand_fail

    for cat_entry in category_totals.values():
        cat_entry["baseline_pass_rate"] = _pass_rate(cat_entry["baseline_total"], cat_entry["baseline_failures"])
        cat_entry["candidate_pass_rate"] = _pass_rate(cat_entry["candidate_total"], cat_entry["candidate_failures"])

    if relation_summary:
        result["relation_coverage"] = {
            "relations": relation_summary,
            "categories": category_totals,
        }
        result["statistics"]["relation_categories"] = category_totals

    if policy_config:
        result["policy"] = _serialize_for_report(policy_config)

    # Add version information
    try:
        from . import __version__
        result["job_metadata"]["metamorphic_guard_version"] = __version__
    except ImportError:
        pass
    
    if policy_version is not None:
        result["config"]["policy_version"] = policy_version

    if monitor_objs:
        result["config"]["monitors"] = [monitor.identifier() for monitor in monitor_objs]
        result["monitors"] = {
            monitor.identifier(): monitor.finalize() for monitor in monitor_objs
        }
    
    # Add trust scores if computed
    if baseline_trust or candidate_trust:
        result["trust_scores"] = {}
        if baseline_trust:
            result["trust_scores"]["baseline"] = baseline_trust
        if candidate_trust:
            result["trust_scores"]["candidate"] = candidate_trust

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
    relation_stats: Dict[str, Dict[str, Any]] = {}
    for relation in spec.relations:
        relation_stats[relation.name] = {
            "category": relation.category or "uncategorized",
            "description": relation.description,
            "total": 0,
            "failures": 0,
        }

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
            stats_entry = relation_stats.setdefault(
                relation.name,
                {
                    "category": relation.category or "uncategorized",
                    "description": relation.description,
                    "total": 0,
                    "failures": 0,
                },
            )
            stats_entry["total"] += 1
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
                stats_entry["failures"] += 1
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
                stats_entry["failures"] += 1
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
                stats_entry["failures"] += 1
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
        "relation_stats": relation_stats,
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
