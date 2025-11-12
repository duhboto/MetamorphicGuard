"""
Test harness for running evaluations and computing bootstrap confidence intervals.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import uuid
from collections import defaultdict
from statistics import NormalDist
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from .sandbox import run_in_sandbox
from .specs import Metric, Spec, get_task
from .util import (
    compute_spec_fingerprint,
    get_environment_fingerprint,
    collect_job_metadata,
    sha256_file,
    write_failed_artifacts,
)
try:
    from .shrink import shrink_input
except ImportError:
    # Shrinking not available
    shrink_input = None


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
from .multiple_comparisons import apply_multiple_comparisons_correction


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
    if delta_value > 0 and 0 < power_target < 1:
        p1 = p_baseline
        p2 = max(0.0, min(1.0, p_baseline + delta_value))
        var_target = p1 * (1 - p1) + p2 * (1 - p2)
        if var_target > 0:
            z_beta = NormalDist().inv_cdf(power_target)
            recommended_n = math.ceil(((z_alpha + z_beta) ** 2 * var_target) / (delta_value ** 2))

    return power_val, recommended_n


def _fingerprint_payload(payload: Any) -> str:
    normalized = _serialize_for_report(payload)
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass
class ExecutionPlan:
    spec: Spec
    test_inputs: List[Tuple[Any, ...]]
    dispatcher: Dispatcher
    monitors: List[Monitor]
    worker_count: int
    run_id: str

    @property
    def total_cases(self) -> int:
        return len(self.test_inputs)


def _prepare_execution_plan(
    *,
    task_name: str,
    spec: Spec,
    n: int,
    seed: int,
    parallel: Optional[int],
    dispatcher: Dispatcher | str | None,
    queue_config: Dict[str, Any] | None,
    monitors: Sequence[Monitor] | None,
    explicit_inputs: Optional[List[Tuple[Any, ...]]],
    executor: Optional[str],
) -> ExecutionPlan:
    if explicit_inputs is not None:
        test_inputs = [tuple(case) for case in explicit_inputs]
    else:
        test_inputs = spec.gen_inputs(n, seed)

    worker_count = max(1, parallel or 1)
    dispatcher_obj = ensure_dispatcher(dispatcher, worker_count, queue_config)

    monitor_objs = list(monitors or [])
    if monitor_objs:
        context = MonitorContext(task=task_name, total_cases=len(test_inputs))
        for monitor in monitor_objs:
            monitor.start(context)

    run_id = f"eval-{uuid.uuid4().hex}"
    add_log_context(run_id=run_id)
    log_event(
        "run_eval_start",
        task=task_name,
        total_cases=len(test_inputs),
        dispatcher=getattr(dispatcher_obj, "kind", "local"),
        executor=executor,
    )

    return ExecutionPlan(
        spec=spec,
        test_inputs=list(test_inputs),
        dispatcher=dispatcher_obj,
        monitors=monitor_objs,
        worker_count=worker_count,
        run_id=run_id,
    )


def _execute_implementations(
    plan: ExecutionPlan,
    *,
    baseline_path: str,
    candidate_path: str,
    timeout_s: float,
    mem_mb: int,
    executor: Optional[str],
    executor_config: Dict[str, Any] | None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
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

    dispatcher_obj = plan.dispatcher
    monitors = plan.monitors
    test_inputs = plan.test_inputs

    baseline_results = dispatcher_obj.execute(
        test_inputs=test_inputs,
        run_case=make_runner(baseline_path),
        role="baseline",
        monitors=monitors,
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
        monitors=monitors,
        call_spec=_build_call_spec(
            candidate_path,
            timeout_s=timeout_s,
            mem_mb=mem_mb,
            executor=executor,
            executor_config=executor_config,
        ),
    )
    return baseline_results, candidate_results


def _evaluate_roles(
    *,
    spec: Spec,
    test_inputs: Sequence[Tuple[Any, ...]],
    baseline_results: Sequence[Dict[str, Any]],
    candidate_results: Sequence[Dict[str, Any]],
    baseline_path: str,
    candidate_path: str,
    timeout_s: float,
    mem_mb: int,
    violation_cap: int,
    seed: int,
    executor: Optional[str],
    executor_config: Dict[str, Any] | None,
    shrink_violations: bool,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
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
        shrink_violations=shrink_violations,
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
        shrink_violations=shrink_violations,
    )
    return baseline_metrics, candidate_metrics


def _summarize_relations(
    spec: Spec,
    baseline_metrics: Dict[str, Any],
    candidate_metrics: Dict[str, Any],
    *,
    alpha: float,
    relation_correction: Optional[str],
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]], Optional[Dict[str, Any]]]:
    relation_summary: List[Dict[str, Any]] = []
    relation_p_values: List[float] = []
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
        description = (
            relation.description
            or baseline_entry.get("description")
            or candidate_entry.get("description")
        )

        base_total = baseline_entry.get("total", 0)
        base_fail = baseline_entry.get("failures", 0)
        cand_total = candidate_entry.get("total", 0)
        cand_fail = candidate_entry.get("failures", 0)

        base_passes = base_total - base_fail
        cand_passes = cand_total - cand_fail
        p_value = _two_proportion_p_value(
            base_passes,
            base_total,
            cand_passes,
            cand_total,
        )
        relation_p_values.append(p_value)

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
                "p_value": p_value,
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
        cat_entry["baseline_pass_rate"] = _pass_rate(
            cat_entry["baseline_total"], cat_entry["baseline_failures"]
        )
        cat_entry["candidate_pass_rate"] = _pass_rate(
            cat_entry["candidate_total"], cat_entry["candidate_failures"]
        )

    correction_metadata: Optional[Dict[str, Any]] = None
    if relation_summary and relation_correction and relation_p_values:
        correction_method = "holm" if relation_correction == "holm" else "fdr"
        corrected = apply_multiple_comparisons_correction(
            relation_p_values,
            method=correction_method,
            alpha=alpha,
        )
        for index, adjusted_p, significant in corrected:
            relation_summary[index]["adjusted_p_value"] = adjusted_p
            relation_summary[index]["significant"] = significant
        correction_metadata = {
            "method": "holm-bonferroni"
            if relation_correction == "holm"
            else "benjamini-hochberg",
            "alpha": alpha,
        }

    return relation_summary, category_totals, correction_metadata


def _safe_extract_metric(metric: Metric, result: Dict[str, Any], args: Tuple[Any, ...]) -> Optional[float]:
    if not result.get("success"):
        return None
    try:
        value = metric.extract(result.get("result"), args)
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _metric_memo_key(metric: Metric) -> Optional[str]:
    if getattr(metric, "memoize_key", None):
        return metric.memoize_key
    if getattr(metric, "memoize", False):
        return metric.name
    return None


def _get_or_compute_metric_value(
    metric: Metric,
    result: Dict[str, Any],
    args: Tuple[Any, ...],
    *,
    memo_key: Optional[str],
    cache: Dict[str, Dict[int, Optional[float]]],
    index: int,
) -> Optional[float]:
    if memo_key is None:
        return _safe_extract_metric(metric, result, args)
    bucket = cache.setdefault(memo_key, {})
    if index in bucket:
        return bucket[index]
    value = _safe_extract_metric(metric, result, args)
    bucket[index] = value
    return value


def _should_sample_metric(metric: Metric, index: int, global_seed: Optional[int]) -> bool:
    rate = getattr(metric, "sample_rate", 1.0)
    try:
        rate = float(rate)
    except Exception:
        rate = 1.0
    rate = max(0.0, min(1.0, rate))
    if rate <= 0.0:
        return False
    if rate >= 1.0:
        return True
    base_seed = metric.seed if metric.seed is not None else global_seed
    if base_seed is None:
        base_seed = 0
    random_seed = int(base_seed) + (index + 1) * 1013904223
    rng = random.Random(random_seed & 0xFFFFFFFF)
    return rng.random() < rate


def _aggregate_metric_values(
    values: Sequence[Optional[float]],
    *,
    kind: str,
    total_count: int,
) -> Dict[str, Any]:
    summary: Dict[str, Any] = {"count": 0, "missing": total_count}
    if total_count <= 0:
        return summary

    filtered = [float(v) for v in values if v is not None]
    summary["count"] = len(filtered)
    summary["missing"] = total_count - len(filtered)

    if not filtered:
        return summary

    summary["min"] = min(filtered)
    summary["max"] = max(filtered)

    if kind == "mean":
        mean = sum(filtered) / len(filtered)
        summary["mean"] = mean
        summary["value"] = mean
        if len(filtered) > 1:
            variance = sum((v - mean) ** 2 for v in filtered) / (len(filtered) - 1)
            summary["stddev"] = math.sqrt(variance)
    elif kind == "sum":
        total = sum(filtered)
        summary["sum"] = total
        summary["value"] = total
    else:
        raise ValueError(f"Unsupported metric kind: {kind}")

    return summary


def _bootstrap_metric_delta(
    deltas: Sequence[float],
    *,
    kind: str,
    samples: int,
    alpha: float,
    seed: Optional[int],
) -> Optional[Dict[str, Any]]:
    count = len(deltas)
    if count == 0 or samples <= 0:
        return None

    rng = random.Random(seed if seed is not None else 0)
    resampled_means: List[float] = []
    for _ in range(max(1, samples)):
        sample = [deltas[rng.randrange(count)] for _ in range(count)]
        resampled_means.append(sum(sample) / count)

    resampled_means.sort()
    lower_mean = _percentile(resampled_means, alpha / 2)
    upper_mean = _percentile(resampled_means, 1 - alpha / 2)

    observed_mean = sum(deltas) / count
    ci_payload: Dict[str, Any] = {
        "method": "bootstrap",
        "level": 1 - alpha,
        "mean": {
            "estimate": observed_mean,
            "lower": lower_mean,
            "upper": upper_mean,
        },
    }

    if kind == "sum":
        observed_sum = observed_mean * count
        lower_sum = lower_mean * count
        upper_sum = upper_mean * count
        ci_payload["sum"] = {
            "estimate": observed_sum,
            "lower": lower_sum,
            "upper": upper_sum,
        }

    return ci_payload


def _collect_metrics(
    metrics: Sequence[Metric],
    baseline_results: Sequence[Dict[str, Any]],
    candidate_results: Sequence[Dict[str, Any]],
    test_inputs: Sequence[Tuple[Any, ...]],
    *,
    seed: Optional[int],
) -> Dict[str, Any]:
    if not metrics:
        return {}

    metrics_payload: Dict[str, Any] = {}
    global_seed = seed
    shared_baseline_cache: Dict[str, Dict[int, Optional[float]]] = defaultdict(dict)
    shared_candidate_cache: Dict[str, Dict[int, Optional[float]]] = defaultdict(dict)

    for metric in metrics:
        baseline_values: List[Optional[float]] = []
        candidate_values: List[Optional[float]] = []
        memo_key = _metric_memo_key(metric)

        for index, (args, b_result, c_result) in enumerate(
            zip(test_inputs, baseline_results, candidate_results)
        ):
            include_case = _should_sample_metric(metric, index, global_seed)
            if not include_case:
                baseline_values.append(None)
                candidate_values.append(None)
                continue

            baseline_values.append(
                _get_or_compute_metric_value(
                    metric,
                    b_result,
                    args,
                    memo_key=memo_key,
                    cache=shared_baseline_cache,
                    index=index,
                )
            )
            candidate_values.append(
                _get_or_compute_metric_value(
                    metric,
                    c_result,
                    args,
                    memo_key=memo_key,
                    cache=shared_candidate_cache,
                    index=index,
                )
            )

        total_count = len(baseline_values)
        baseline_summary = _aggregate_metric_values(
            baseline_values,
            kind=metric.kind,
            total_count=total_count,
        )
        candidate_summary = _aggregate_metric_values(
            candidate_values,
            kind=metric.kind,
            total_count=len(candidate_values),
        )

        delta_payload: Dict[str, Any] = {}
        baseline_value = baseline_summary.get("value")
        candidate_value = candidate_summary.get("value")
        if baseline_value is not None and candidate_value is not None:
            delta_payload["difference"] = candidate_value - baseline_value
            if baseline_value != 0:
                delta_payload["ratio"] = candidate_value / baseline_value

        paired_deltas = [
            cand - base
            for base, cand in zip(baseline_values, candidate_values)
            if base is not None and cand is not None
        ]
        paired_count = len(paired_deltas)
        delta_payload["paired_count"] = paired_count
        if paired_deltas:
            paired_mean = sum(paired_deltas) / paired_count
            delta_payload["paired_mean"] = paired_mean

            if metric.ci_method and metric.ci_method.lower() == "bootstrap" and paired_count > 1:
                ci_result = _bootstrap_metric_delta(
                    paired_deltas,
                    kind=metric.kind,
                    samples=max(1, metric.bootstrap_samples),
                    alpha=metric.alpha,
                    seed=metric.seed,
                )
                if ci_result:
                    delta_payload["ci"] = ci_result

        metric_entry: Dict[str, Any] = {
            "kind": metric.kind,
            "higher_is_better": metric.higher_is_better,
            "baseline": baseline_summary,
            "candidate": candidate_summary,
        }
        if delta_payload:
            metric_entry["delta"] = delta_payload

        metrics_payload[metric.name] = metric_entry

    return metrics_payload


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
    shrink_violations: bool = False,
    sequential_method: str = "none",
    max_looks: int = 1,
    look_number: int = 1,
    relation_correction: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run evaluation comparing baseline and candidate implementations.

    Returns comprehensive metrics including bootstrap confidence intervals.
    """
    spec = get_task(task_name)

    plan = _prepare_execution_plan(
        task_name=task_name,
        spec=spec,
        n=n,
        seed=seed,
        parallel=parallel,
        dispatcher=dispatcher,
        queue_config=queue_config,
        monitors=monitors,
        explicit_inputs=explicit_inputs,
        executor=executor,
    )

    test_inputs = plan.test_inputs
    n = plan.total_cases
    worker_count = plan.worker_count
    dispatcher_obj = plan.dispatcher
    monitor_objs = plan.monitors
    run_id = plan.run_id

    baseline_results, candidate_results = _execute_implementations(
        plan,
        baseline_path=baseline_path,
        candidate_path=candidate_path,
        timeout_s=timeout_s,
        mem_mb=mem_mb,
        executor=executor,
        executor_config=executor_config,
    )
    baseline_runtime_meta = next(
        (
            _serialize_for_report(entry.get("sandbox_metadata"))
            for entry in baseline_results
            if entry.get("sandbox_metadata")
        ),
        None,
    )
    candidate_runtime_meta = next(
        (
            _serialize_for_report(entry.get("sandbox_metadata"))
            for entry in candidate_results
            if entry.get("sandbox_metadata")
        ),
        None,
    )

    baseline_metrics, candidate_metrics = _evaluate_roles(
        spec=spec,
        test_inputs=test_inputs,
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

    paired_stats = _compute_paired_stats(
        baseline_metrics.get("pass_indicators", []),
        candidate_metrics.get("pass_indicators", []),
    )

    baseline_call_spec = _serialize_for_report(
        _build_call_spec(
            baseline_path,
            timeout_s=timeout_s,
            mem_mb=mem_mb,
            executor=executor,
            executor_config=executor_config,
        )
    )
    candidate_call_spec = _serialize_for_report(
        _build_call_spec(
            candidate_path,
            timeout_s=timeout_s,
            mem_mb=mem_mb,
            executor=executor,
            executor_config=executor_config,
        )
    )

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

    def _recompute_delta_ci(new_alpha: float) -> List[float]:
        return _compute_delta_ci(
            baseline_metrics,
            candidate_metrics,
            alpha=new_alpha,
            seed=seed,
            samples=bootstrap_samples,
            method=ci_method,
        )

    # Apply sequential testing correction if enabled
    effective_alpha = alpha
    if sequential_method != "none" and max_looks > 1:
        from .sequential_testing import SequentialTestConfig, apply_sequential_correction
        
        seq_config = SequentialTestConfig(
            method=sequential_method,
            alpha=alpha,
            max_looks=max_looks,
            look_number=look_number,
        )
        delta_ci, effective_alpha = apply_sequential_correction(
            delta_ci,
            seq_config,
            recompute_ci=_recompute_delta_ci,
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
            "effective_alpha": effective_alpha,
            "sequential_method": sequential_method,
            "max_looks": max_looks,
            "look_number": look_number,
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
            "relation_correction": relation_correction,
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

    if policy_config:
        descriptor = policy_config.get("descriptor")
        if descriptor:
            result["config"]["policy_rule"] = _serialize_for_report(descriptor)
    
    baseline_clusters = baseline_metrics.get("cluster_labels") or []
    result["cases"] = []
    for index, args in enumerate(test_inputs):
        cluster_value = baseline_clusters[index] if index < len(baseline_clusters) else index
        result["cases"].append(
            {
                "index": index,
                "input": _serialize_for_report(args),
                "formatted": spec.fmt_in(args),
                "cluster": _serialize_for_report(cluster_value),
            }
        )

    try:
        policy_gate = None
        if policy_config:
            policy_gate = policy_config.get("policy")
        result["decision"] = decide_adopt(
            result,
            improve_delta=improve_delta,
            min_pass_rate=min_pass_rate,
            policy=policy_gate,
        )
    except Exception as exc:
        result["decision"] = {
            "adopt": False,
            "reason": f"gate_error: {exc}",
        }

    result["replay"] = {
        "seed": seed,
        "cases": len(test_inputs),
        "explicit_inputs": bool(explicit_inputs),
        "baseline_path": baseline_path,
        "candidate_path": candidate_path,
        "task": task_name,
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
    if paired_stats:
        result["statistics"]["paired"] = paired_stats

    relation_summary, category_totals, correction_metadata = _summarize_relations(
        spec,
        baseline_metrics,
        candidate_metrics,
        alpha=alpha,
        relation_correction=relation_correction,
    )

    if relation_summary:
        relation_coverage_payload: Dict[str, Any] = {
            "relations": relation_summary,
            "categories": category_totals,
        }
        if correction_metadata:
            relation_coverage_payload["correction"] = correction_metadata

        result["relation_coverage"] = relation_coverage_payload
        result["statistics"]["relation_categories"] = category_totals
        if correction_metadata:
            result["statistics"]["relation_correction"] = correction_metadata

    metrics_payload = _collect_metrics(
        spec.metrics,
        baseline_results,
        candidate_results,
        test_inputs,
        seed=seed,
    )
    if metrics_payload:
        result["metrics"] = metrics_payload

    if policy_config:
        result["policy"] = _serialize_for_report(policy_config)

    # Build provenance section
    provenance_data: Dict[str, Any] = {}
    
    # Library version
    try:
        from . import __version__
        provenance_data["library_version"] = __version__
    except ImportError:
        pass
    
    # Git and environment from job_metadata
    job_meta = result.get("job_metadata", {})
    if "git_commit" in job_meta:
        provenance_data["git_sha"] = job_meta["git_commit"]
    if "git_dirty" in job_meta:
        provenance_data["git_dirty"] = job_meta["git_dirty"]
    if "hostname" in job_meta:
        provenance_data["hostname"] = job_meta["hostname"]
    if "python_version" in job_meta:
        provenance_data["python_version"] = job_meta["python_version"]
    if "executable" in job_meta:
        provenance_data["executable"] = job_meta["executable"]
    
    # Platform and environment
    env_fp = result.get("environment", {})
    if "platform" in env_fp:
        provenance_data["platform"] = env_fp["platform"]
    if env_fp:
        provenance_data["environment"] = env_fp
    
    # MR IDs from spec
    mr_ids = [rel.name for rel in spec.relations]
    if mr_ids:
        provenance_data["mr_ids"] = mr_ids
    
    # Spec fingerprint
    if "spec_fingerprint" in result:
        provenance_data["spec_fingerprint"] = result["spec_fingerprint"]

    sandbox_provenance: Dict[str, Any] = {
        "executor": executor or "local",
        "timeout_s": timeout_s,
        "mem_mb": mem_mb,
        "call_spec": {
            "baseline": baseline_call_spec,
            "candidate": candidate_call_spec,
        },
        "call_spec_fingerprint": {
            "baseline": _fingerprint_payload(baseline_call_spec),
            "candidate": _fingerprint_payload(candidate_call_spec),
        },
    }
    sanitized_executor_config = result["config"].get("executor_config")
    if sanitized_executor_config is not None:
        sandbox_provenance["executor_config"] = sanitized_executor_config
        sandbox_provenance["executor_config_fingerprint"] = _fingerprint_payload(
            sanitized_executor_config
        )
    runtime_metadata: Dict[str, Any] = {}
    if baseline_runtime_meta:
        runtime_metadata["baseline"] = baseline_runtime_meta
    if candidate_runtime_meta:
        runtime_metadata["candidate"] = candidate_runtime_meta
    if runtime_metadata:
        sandbox_provenance["executions"] = runtime_metadata
        sandbox_provenance["executions_fingerprint"] = {
            role: _fingerprint_payload(meta) for role, meta in runtime_metadata.items()
        }
    provenance_data["sandbox"] = sandbox_provenance
    
    if provenance_data:
        result["provenance"] = provenance_data
    
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
    shrink_violations: bool = False,
) -> Dict[str, Any]:
    """Evaluate results against properties and metamorphic relations."""
    passes = 0
    total = len(results)
    prop_violations: list[Dict[str, Any]] = []
    mr_violations: list[Dict[str, Any]] = []
    pass_indicators: list[int] = []
    cluster_labels: list[Any] = []
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
        cluster_value = spec.cluster_key(args) if spec.cluster_key else idx
        cluster_labels.append(cluster_value)
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

    # Shrink violations if enabled
    if shrink_violations and shrink_input is not None:
        def _shrink_violation(violation: Dict[str, Any], original_args: Tuple[Any, ...]) -> Dict[str, Any]:
            """Shrink a violation's input while preserving the failure."""
            def test_fails(shrunken_args: Tuple[Any, ...]) -> bool:
                """Test if shrunken args still fail."""
                try:
                    result = rerun(shrunken_args)
                    if not result.get("success"):
                        return True
                    output = result.get("result")
                    # Check properties
                    for prop in spec.properties:
                        if prop.mode == "hard":
                            try:
                                if not prop.check(output, *shrunken_args):
                                    return True
                            except Exception:
                                return True
                    return False
                except Exception:
                    return True
            
            try:
                shrunk_args = shrink_input(original_args, test_fails)
                if shrunk_args != original_args:
                    violation["shrunk_input"] = spec.fmt_in(shrunk_args)
                    violation["original_input"] = violation.get("input")
                    violation["input"] = spec.fmt_in(shrunk_args)
            except Exception:
                # Shrinking failed, keep original
                pass
            return violation
        
        # Shrink prop violations
        for violation in prop_violations:
            test_case_idx = violation.get("test_case", 0)
            if test_case_idx < len(test_inputs):
                original_args = test_inputs[test_case_idx]
                _shrink_violation(violation, original_args)
        
        # Shrink MR violations
        for violation in mr_violations:
            test_case_idx = violation.get("test_case", 0)
            if test_case_idx < len(test_inputs):
                original_args = test_inputs[test_case_idx]
                _shrink_violation(violation, original_args)

    return {
        "passes": passes,
        "total": total,
        "pass_rate": passes / total if total else 0.0,
        "prop_violations": prop_violations,
        "mr_violations": mr_violations,
        "pass_indicators": pass_indicators,
        "cluster_labels": cluster_labels,
        "relation_stats": relation_stats,
    }


def _compute_paired_stats(
    baseline_indicators: Sequence[int],
    candidate_indicators: Sequence[int],
) -> Optional[Dict[str, Any]]:
    if not baseline_indicators or not candidate_indicators:
        return None

    total = min(len(baseline_indicators), len(candidate_indicators))
    if total <= 0:
        return None

    both_pass = both_fail = baseline_only = candidate_only = 0
    baseline_sum = candidate_sum = 0

    for b, c in zip(baseline_indicators, candidate_indicators):
        if b:
            baseline_sum += 1
        if c:
            candidate_sum += 1

        if b and c:
            both_pass += 1
        elif b and not c:
            baseline_only += 1
        elif not b and c:
            candidate_only += 1
        else:
            both_fail += 1

    discordant = baseline_only + candidate_only
    delta = (candidate_sum - baseline_sum) / total

    if discordant == 0:
        chi2 = 0.0
        p_value = 1.0
    else:
        diff = abs(baseline_only - candidate_only)
        numerator = max(diff - 1.0, 0.0)
        chi2 = (numerator * numerator) / discordant
        p_value = math.erfc(math.sqrt(max(chi2, 0.0)) / math.sqrt(2.0))

    return {
        "total": total,
        "both_pass": both_pass,
        "both_fail": both_fail,
        "baseline_only": baseline_only,
        "candidate_only": candidate_only,
        "discordant": discordant,
        "delta": delta,
        "mcnemar_chi2": chi2,
        "mcnemar_p": p_value,
        "method": "mcnemar_cc",
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
    method = method.lower().replace("-", "_")
    clusters = baseline_metrics.get("cluster_labels")
    if method in {"bootstrap_cluster", "bootstrap_cluster_bca"}:
        return _compute_bootstrap_ci(
            baseline_metrics["pass_indicators"],
            candidate_metrics["pass_indicators"],
            alpha=alpha,
            seed=seed,
            samples=samples,
            clusters=clusters,
            use_bca=method.endswith("bca"),
            observed_delta=candidate_metrics["pass_rate"] - baseline_metrics["pass_rate"],
        )
    if method in {"bootstrap", "bootstrap_bca"}:
        return _compute_bootstrap_ci(
            baseline_metrics["pass_indicators"],
            candidate_metrics["pass_indicators"],
            alpha=alpha,
            seed=seed,
            samples=samples,
            clusters=None,
            use_bca=method.endswith("bca"),
            observed_delta=candidate_metrics["pass_rate"] - baseline_metrics["pass_rate"],
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
    clusters: Optional[Sequence[Any]] = None,
    use_bca: bool = False,
    observed_delta: float | None = None,
) -> List[float]:
    """Compute a bootstrap confidence interval for the pass-rate delta."""
    n = len(baseline_indicators)
    if n == 0 or len(candidate_indicators) != n:
        return [0.0, 0.0]

    rng = random.Random(seed)
    deltas = _generate_bootstrap_deltas(
        baseline_indicators,
        candidate_indicators,
        rng=rng,
        samples=samples,
        clusters=clusters,
    )

    if not deltas:
        return [0.0, 0.0]

    if use_bca:
        if observed_delta is None:
            observed_delta = (sum(candidate_indicators) / n) - (sum(baseline_indicators) / n)
        return _compute_bca_interval(
            deltas,
            observed_delta=observed_delta,
            baseline_indicators=baseline_indicators,
            candidate_indicators=candidate_indicators,
            alpha=alpha,
            clusters=clusters,
        )

    lower_quantile = alpha / 2
    upper_quantile = 1 - alpha / 2
    ci_lower = _percentile(deltas, lower_quantile)
    ci_upper = _percentile(deltas, upper_quantile)
    return [float(ci_lower), float(ci_upper)]


def _generate_bootstrap_deltas(
    baseline_indicators: Sequence[int],
    candidate_indicators: Sequence[int],
    *,
    rng: random.Random,
    samples: int,
    clusters: Optional[Sequence[Any]] = None,
) -> List[float]:
    """Generate bootstrap deltas (candidate - baseline pass rate)."""
    n = len(baseline_indicators)
    if n == 0 or len(candidate_indicators) != n:
        return []

    deltas: List[float] = []

    if clusters:
        cluster_indices: Dict[Any, List[int]] = {}
        for idx, cluster_id in enumerate(clusters):
            cluster_indices.setdefault(cluster_id, []).append(idx)
        unique_clusters = list(cluster_indices.keys())
        if unique_clusters:
            cluster_count = len(unique_clusters)
            for _ in range(max(1, samples)):
                sampled_clusters = [
                    unique_clusters[rng.randrange(cluster_count)]
                    for _ in range(cluster_count)
                ]
                baseline_sample: List[int] = []
                candidate_sample: List[int] = []
                for cluster_id in sampled_clusters:
                    indices = cluster_indices[cluster_id]
                    baseline_sample.extend(baseline_indicators[i] for i in indices)
                    candidate_sample.extend(candidate_indicators[i] for i in indices)
                if not baseline_sample or len(baseline_sample) != len(candidate_sample):
                    continue
                p_baseline = sum(baseline_sample) / len(baseline_sample)
                p_candidate = sum(candidate_sample) / len(candidate_sample)
                deltas.append(p_candidate - p_baseline)
            if deltas:
                return deltas
        # fallback to iid if clusters missing/empty

    for _ in range(max(1, samples)):
        indices = [rng.randrange(n) for _ in range(n)]
        baseline_sum = sum(baseline_indicators[i] for i in indices)
        candidate_sum = sum(candidate_indicators[i] for i in indices)
        deltas.append((candidate_sum - baseline_sum) / n)

    return deltas


def _compute_bca_interval(
    deltas: Sequence[float],
    *,
    observed_delta: float,
    baseline_indicators: Sequence[int],
    candidate_indicators: Sequence[int],
    alpha: float,
    clusters: Optional[Sequence[Any]] = None,
) -> List[float]:
    """Compute the bias-corrected and accelerated (BCa) interval for bootstrap deltas."""
    if not deltas:
        return [0.0, 0.0]

    sorted_deltas = sorted(deltas)
    num_samples = len(sorted_deltas)
    # Bias correction
    proportion = sum(delta < observed_delta for delta in sorted_deltas) / num_samples
    if proportion <= 0.0:
        z0 = float("-inf")
    elif proportion >= 1.0:
        z0 = float("inf")
    else:
        z0 = NormalDist().inv_cdf(proportion)

    # Acceleration via jackknife
    n = len(baseline_indicators)
    total_baseline = sum(baseline_indicators)
    total_candidate = sum(candidate_indicators)

    jackknife: List[float] = []

    cluster_map: Dict[Any, List[int]] | None = None
    if clusters:
        cluster_map = {}
        for idx, cluster_id in enumerate(clusters):
            cluster_map.setdefault(cluster_id, []).append(idx)
        # Only keep clusters that have valid indices
        cluster_groups = [indices for indices in cluster_map.values() if indices]
        for indices in cluster_groups:
            denom = n - len(indices)
            if denom <= 0:
                continue
            baseline_loo_total = total_baseline - sum(baseline_indicators[i] for i in indices)
            candidate_loo_total = total_candidate - sum(candidate_indicators[i] for i in indices)
            p_b = baseline_loo_total / denom if denom else 0.0
            p_c = candidate_loo_total / denom if denom else 0.0
            jackknife.append(p_c - p_b)

    if not jackknife:
        if n <= 1:
            acceleration = 0.0
        else:
            for i in range(n):
                denom = n - 1
                if denom <= 0:
                    continue
                baseline_loo_total = total_baseline - baseline_indicators[i]
                candidate_loo_total = total_candidate - candidate_indicators[i]
                p_b = baseline_loo_total / denom if denom else 0.0
                p_c = candidate_loo_total / denom if denom else 0.0
                jackknife.append(p_c - p_b)

    if len(jackknife) < 2:
        acceleration = 0.0
    else:
        mean_jackknife = sum(jackknife) / len(jackknife)
        num = sum((mean_jackknife - jk) ** 3 for jk in jackknife)
        denom_sq = sum((mean_jackknife - jk) ** 2 for jk in jackknife)
        denom_pow = denom_sq ** 1.5 if denom_sq > 0 else 0.0
        if denom_pow == 0:
            acceleration = 0.0
        else:
            acceleration = num / (6.0 * denom_pow)

    def _adjusted_quantile(prob: float) -> float:
        if prob <= 0.0:
            return 0.0
        if prob >= 1.0:
            return 1.0
        if math.isinf(z0):
            return 0.0 if z0 < 0 else 1.0
        z_prob = NormalDist().inv_cdf(prob)
        denom = 1 - acceleration * (z0 + z_prob)
        if denom == 0:
            adjusted = 0.0 if z0 + z_prob < 0 else 1.0
        else:
            adjusted = NormalDist().cdf(z0 + (z0 + z_prob) / denom)
        return min(1.0, max(0.0, adjusted))

    lower_prob = _adjusted_quantile(alpha / 2)
    upper_prob = _adjusted_quantile(1 - alpha / 2)

    lower = _percentile(sorted_deltas, lower_prob)
    upper = _percentile(sorted_deltas, upper_prob)
    return [float(lower), float(upper)]


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


def _two_proportion_p_value(
    successes_a: int,
    total_a: int,
    successes_b: int,
    total_b: int,
) -> float:
    """Two-sided z-test for difference in proportions."""
    if total_a <= 0 or total_b <= 0:
        return 1.0

    p_a = successes_a / total_a
    p_b = successes_b / total_b
    pooled_successes = successes_a + successes_b
    pooled_total = total_a + total_b
    if pooled_total <= 0:
        return 1.0

    pooled = pooled_successes / pooled_total
    variance = pooled * (1 - pooled) * (1 / total_a + 1 / total_b)
    if variance <= 0:
        return 1.0

    z = abs(p_a - p_b) / math.sqrt(variance)
    p_value = 2 * (1 - NormalDist().cdf(z))
    return max(0.0, min(1.0, float(p_value)))


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
