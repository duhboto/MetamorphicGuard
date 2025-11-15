"""
Reporting and metrics functions for summarizing evaluation results.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import Callable, Dict, Hashable, List, Optional, Sequence, Tuple

from ..multiple_comparisons import apply_multiple_comparisons_correction
from ..observability import increment_metric
from ..sandbox import run_in_sandbox
from ..specs import Metric, Spec
from ..types import JSONDict
from .execution import relation_cache_key, relation_rng
from .statistics import percentile, two_proportion_p_value

try:
    from ..shrink import shrink_input
except ImportError:
    shrink_input = None  # type: ignore


def summarize_llm_results(results: Sequence[JSONDict]) -> JSONDict:
    """Summarize LLM execution results with cost, tokens, and latency metrics."""
    summary: JSONDict = {
        "count": 0,
        "successes": 0,
        "failures": 0,
        "total_cost_usd": 0.0,
        "total_tokens": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_latency_ms": 0.0,
        "avg_latency_ms": 0.0,
        "avg_cost_usd": 0.0,
        "avg_tokens": 0.0,
        "retry_total": 0,
        "avg_retries": 0.0,
        "max_retries": 0,
        "success_rate": 0.0,
    }

    for entry in results:
        if not isinstance(entry, dict):
            continue
        summary["count"] += 1
        if entry.get("success"):
            summary["successes"] += 1
        tokens_prompt = entry.get("tokens_prompt")
        tokens_completion = entry.get("tokens_completion")
        tokens_total = entry.get("tokens_total")
        cost = entry.get("cost_usd")
        latency = entry.get("duration_ms")
        retries = entry.get("retries", 0)

        if tokens_prompt is not None:
            summary["prompt_tokens"] += int(tokens_prompt)
        if tokens_completion is not None:
            summary["completion_tokens"] += int(tokens_completion)
        if tokens_total is not None:
            summary["total_tokens"] += int(tokens_total)
        elif tokens_prompt is not None or tokens_completion is not None:
            summary["total_tokens"] += int(tokens_prompt or 0) + int(tokens_completion or 0)

        if cost is not None:
            summary["total_cost_usd"] += float(cost)
        if latency is not None:
            summary["total_latency_ms"] += float(latency)
        if isinstance(retries, (int, float)):
            retry_value = int(retries)
            summary["retry_total"] += retry_value
            summary["max_retries"] = max(summary["max_retries"], retry_value)

    summary["failures"] = summary["count"] - summary["successes"]
    if summary["count"] > 0:
        summary["avg_latency_ms"] = summary["total_latency_ms"] / summary["count"]
        summary["avg_cost_usd"] = summary["total_cost_usd"] / summary["count"]
        summary["avg_tokens"] = summary["total_tokens"] / summary["count"]
        summary["avg_retries"] = summary["retry_total"] / summary["count"]
        summary["success_rate"] = summary["successes"] / summary["count"]
    return summary


def compose_llm_metrics(
    baseline_summary: JSONDict,
    candidate_summary: JSONDict,
) -> Optional[JSONDict]:
    """Compose LLM metrics from baseline and candidate summaries."""
    if not baseline_summary.get("count") and not candidate_summary.get("count"):
        return None

    payload: JSONDict = {
        "baseline": baseline_summary,
        "candidate": candidate_summary,
    }
    baseline_cost = float(baseline_summary.get("total_cost_usd", 0.0))
    candidate_cost = float(candidate_summary.get("total_cost_usd", 0.0))
    payload["cost_delta_usd"] = candidate_cost - baseline_cost
    payload["cost_ratio"] = (
        candidate_cost / baseline_cost if baseline_cost > 0 else None
    )

    baseline_tokens = int(baseline_summary.get("total_tokens", 0))
    candidate_tokens = int(candidate_summary.get("total_tokens", 0))
    payload["tokens_delta"] = candidate_tokens - baseline_tokens
    payload["token_ratio"] = (
        candidate_tokens / baseline_tokens if baseline_tokens > 0 else None
    )

    baseline_retries = int(baseline_summary.get("retry_total", 0))
    candidate_retries = int(candidate_summary.get("retry_total", 0))
    payload["retry_delta"] = candidate_retries - baseline_retries
    payload["retry_ratio"] = (
        candidate_retries / baseline_retries if baseline_retries > 0 else None
    )
    return payload


def evaluate_roles(
    *,
    spec: Spec,
    test_inputs: Sequence[Tuple[object, ...]],
    baseline_results: Sequence[JSONDict],
    candidate_results: Sequence[JSONDict],
    baseline_path: str,
    candidate_path: str,
    timeout_s: float,
    mem_mb: int,
    violation_cap: int,
    seed: int,
    executor: Optional[str],
    executor_config: JSONDict | None,
    shrink_violations: bool,
) -> Tuple[JSONDict, JSONDict]:
    """Evaluate baseline and candidate results against spec."""
    baseline_metrics = evaluate_results(
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
    candidate_metrics = evaluate_results(
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


def evaluate_results(
    results: Sequence[JSONDict],
    spec: Spec,
    test_inputs: Sequence[Tuple[object, ...]],
    violation_cap: int,
    *,
    role: str,
    seed: int,
    rerun: Callable[[Tuple[object, ...]], JSONDict],
    shrink_violations: bool = False,
) -> JSONDict:
    """Evaluate results against properties and metamorphic relations."""
    passes = 0
    total = len(results)
    prop_violations: list[JSONDict] = []
    mr_violations: list[JSONDict] = []
    pass_indicators: list[int] = []
    cluster_labels: list[Hashable] = []
    rerun_cache: Dict[str, JSONDict] = {}
    relation_stats: Dict[str, JSONDict] = {}
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
            except Exception as exc:
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
            relation_rng_obj = None
            if relation.accepts_rng:
                relation_rng_obj = relation_rng(seed, idx, relation_index, relation.name)
            try:
                if relation.accepts_rng:
                    transformed_args = relation.transform(*args, rng=relation_rng_obj)
                else:
                    transformed_args = relation.transform(*args)
            except Exception as exc:  # User-provided relation.transform may raise any exception
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

            cache_key = relation_cache_key(relation_index, transformed_args)
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
            else:
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
        def _shrink_violation(violation: JSONDict, original_args: Tuple[object, ...]) -> JSONDict:
            """Shrink a violation's input while preserving the failure."""
            def test_fails(shrunken_args: Tuple[object, ...]) -> bool:
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
            except Exception:  # shrink_input may raise any exception, keep original on failure
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


def summarize_relations(
    spec: Spec,
    baseline_metrics: JSONDict,
    candidate_metrics: JSONDict,
    *,
    alpha: float,
    relation_correction: Optional[str],
) -> Tuple[List[JSONDict], Dict[str, JSONDict], Optional[JSONDict]]:
    """Summarize metamorphic relation results with statistical analysis."""
    relation_summary: List[JSONDict] = []
    relation_p_values: List[float] = []
    category_totals: Dict[str, JSONDict] = {}

    def _pass_rate(total: int, failures: int) -> Optional[float]:
        if total <= 0:
            return None
        return (total - failures) / total

    baseline_relation_stats = baseline_metrics.get("relation_stats", {})
    candidate_relation_stats = candidate_metrics.get("relation_stats", {})
    candidate_total_cases = candidate_metrics.get("total", 0) or 0

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
        p_value = two_proportion_p_value(
            base_passes,
            base_total,
            cand_passes,
            cand_total,
        )
        relation_p_values.append(p_value)

        baseline_pass_rate = _pass_rate(base_total, base_fail)
        candidate_pass_rate = _pass_rate(cand_total, cand_fail)
        impact = None
        if baseline_pass_rate is not None and candidate_pass_rate is not None:
            impact = candidate_pass_rate - baseline_pass_rate
        coverage = (
            cand_total / candidate_total_cases if candidate_total_cases > 0 else None
        )

        relation_summary.append(
            {
                "name": name,
                "category": category,
                "description": description,
                "baseline": {
                    "total": base_total,
                    "failures": base_fail,
                    "pass_rate": baseline_pass_rate,
                },
                "candidate": {
                    "total": cand_total,
                    "failures": cand_fail,
                    "pass_rate": candidate_pass_rate,
                },
                "p_value": p_value,
                "impact_score": impact,
                "coverage": coverage,
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

    correction_metadata: Optional[JSONDict] = None
    if relation_summary and relation_correction and relation_p_values:
        if relation_correction == "holm":
            correction_method = "holm"
            method_name = "holm-bonferroni"
        elif relation_correction == "hochberg":
            correction_method = "hochberg"
            method_name = "hochberg"
        else:  # fdr
            correction_method = "fdr"
            method_name = "benjamini-hochberg"
        
        corrected = apply_multiple_comparisons_correction(
            relation_p_values,
            method=correction_method,
            alpha=alpha,
        )
        for index, adjusted_p, significant in corrected:
            relation_summary[index]["adjusted_p_value"] = adjusted_p
            relation_summary[index]["significant"] = significant
        correction_metadata = {
            "method": method_name,
            "alpha": alpha,
        }

    return relation_summary, category_totals, correction_metadata


def safe_extract_metric(metric: Metric, result: JSONDict, args: Tuple[object, ...]) -> Optional[float]:
    """Safely extract a metric value from a result."""
    if not result.get("success"):
        return None
    try:
        value = metric.extract(result.get("result"), args)
        if value is None:
            return None
        return float(value)
    except (ValueError, TypeError):
        return None


def metric_memo_key(metric: Metric) -> Optional[str]:
    """Get the memoization key for a metric."""
    if getattr(metric, "memoize_key", None):
        return metric.memoize_key
    if getattr(metric, "memoize", False):
        return metric.name
    return None


def get_or_compute_metric_value(
    metric: Metric,
    result: JSONDict,
    args: Tuple[object, ...],
    *,
    memo_key: Optional[str],
    cache: Dict[str, Dict[int, Optional[float]]],
    index: int,
) -> Optional[float]:
    """Get metric value from cache or compute it."""
    if memo_key is None:
        return safe_extract_metric(metric, result, args)
    bucket = cache.setdefault(memo_key, {})
    if index in bucket:
        return bucket[index]
    value = safe_extract_metric(metric, result, args)
    bucket[index] = value
    return value


def should_sample_metric(metric: Metric, index: int, global_seed: Optional[int]) -> bool:
    """Determine if a metric should be sampled for a given case."""
    rate = getattr(metric, "sample_rate", 1.0)
    try:
        rate = float(rate)
    except (ValueError, TypeError):
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


def aggregate_metric_values(
    values: Sequence[Optional[float]],
    *,
    kind: str,
    total_count: int,
) -> JSONDict:
    """Aggregate metric values into summary statistics."""
    summary: JSONDict = {"count": 0, "missing": total_count}
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


def bootstrap_metric_delta(
    deltas: Sequence[float],
    *,
    kind: str,
    samples: int,
    alpha: float,
    seed: Optional[int],
) -> Optional[JSONDict]:
    """Compute bootstrap confidence interval for metric deltas."""
    count = len(deltas)
    if count == 0 or samples <= 0:
        return None

    rng = random.Random(seed if seed is not None else 0)
    resampled_means: List[float] = []
    for _ in range(max(1, samples)):
        sample = [deltas[rng.randrange(count)] for _ in range(count)]
        resampled_means.append(sum(sample) / count)

    resampled_means.sort()
    lower_mean = percentile(resampled_means, alpha / 2)
    upper_mean = percentile(resampled_means, 1 - alpha / 2)

    observed_mean = sum(deltas) / count
    ci_payload: JSONDict = {
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


def collect_metrics(
    metrics: Sequence[Metric],
    baseline_results: Sequence[JSONDict],
    candidate_results: Sequence[JSONDict],
    test_inputs: Sequence[Tuple[object, ...]],
    *,
    seed: Optional[int],
) -> JSONDict:
    """Collect and aggregate metrics from baseline and candidate results."""
    if not metrics:
        return {}

    metrics_payload: JSONDict = {}
    global_seed = seed
    shared_baseline_cache: Dict[str, Dict[int, Optional[float]]] = defaultdict(dict)
    shared_candidate_cache: Dict[str, Dict[int, Optional[float]]] = defaultdict(dict)

    for metric in metrics:
        baseline_values: List[Optional[float]] = []
        candidate_values: List[Optional[float]] = []
        memo_key = metric_memo_key(metric)

        for index, (args, b_result, c_result) in enumerate(
            zip(test_inputs, baseline_results, candidate_results)
        ):
            include_case = should_sample_metric(metric, index, global_seed)
            if not include_case:
                baseline_values.append(None)
                candidate_values.append(None)
                continue

            baseline_values.append(
                get_or_compute_metric_value(
                    metric,
                    b_result,
                    args,
                    memo_key=memo_key,
                    cache=shared_baseline_cache,
                    index=index,
                )
            )
            candidate_values.append(
                get_or_compute_metric_value(
                    metric,
                    c_result,
                    args,
                    memo_key=memo_key,
                    cache=shared_candidate_cache,
                    index=index,
                )
            )

        total_count = len(baseline_values)
        baseline_summary = aggregate_metric_values(
            baseline_values,
            kind=metric.kind,
            total_count=total_count,
        )
        candidate_summary = aggregate_metric_values(
            candidate_values,
            kind=metric.kind,
            total_count=len(candidate_values),
        )

        delta_payload: JSONDict = {}
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
                ci_result = bootstrap_metric_delta(
                    paired_deltas,
                    kind=metric.kind,
                    samples=max(1, metric.bootstrap_samples),
                    alpha=metric.alpha,
                    seed=metric.seed,
                )
                if ci_result:
                    delta_payload["ci"] = ci_result
        
        # Compute effect sizes for continuous metrics
        if metric.kind == "continuous":
            from .statistics import compute_cohens_d
            effect_sizes = compute_cohens_d(baseline_values, candidate_values)
            if effect_sizes:
                delta_payload["effect_sizes"] = effect_sizes

        metric_entry: JSONDict = {
            "kind": metric.kind,
            "higher_is_better": metric.higher_is_better,
            "baseline": baseline_summary,
            "candidate": candidate_summary,
        }
        if delta_payload:
            metric_entry["delta"] = delta_payload

        metrics_payload[metric.name] = metric_entry

    return metrics_payload

