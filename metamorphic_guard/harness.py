"""
Test harness for running evaluations and computing bootstrap confidence intervals.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from statistics import NormalDist
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
import warnings
from .specs import Metric, Spec, get_task
from .types import JSONDict, JSONValue
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


def _serialize_for_report(value: Any) -> JSONValue:
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
from .dispatch import Dispatcher
from .monitoring import Monitor
from .observability import increment_llm_retries, log_event
from .gate import decide_adopt
from .audit import write_audit_entry
from .sequential_testing import should_continue_sprt, sprt_boundary

# Import from refactored modules
from .harness.statistics import (
    compute_delta_ci as _compute_delta_ci_new,
    compute_paired_stats as _compute_paired_stats_new,
    compute_relative_risk as _compute_relative_risk_new,
    estimate_power as _estimate_power_new,
    compute_bayesian_posterior_predictive as _compute_bayesian_posterior_predictive,
)
from .harness.execution import (
    ExecutionPlan,
    build_call_spec as _build_call_spec_new,
    execute_implementations as _execute_implementations_new,
    prepare_execution_plan as _prepare_execution_plan_new,
    relation_cache_key as _relation_cache_key_new,
    relation_rng as _relation_rng_new,
)
from .harness.reporting import (
    aggregate_metric_values as _aggregate_metric_values_new,
    bootstrap_metric_delta as _bootstrap_metric_delta_new,
    collect_metrics as _collect_metrics_new,
    compose_llm_metrics as _compose_llm_metrics_new,
    evaluate_results as _evaluate_results_new,
    evaluate_roles as _evaluate_roles_new,
    get_or_compute_metric_value as _get_or_compute_metric_value_new,
    safe_extract_metric as _safe_extract_metric_new,
    should_sample_metric as _should_sample_metric_new,
    summarize_llm_results as _summarize_llm_results_new,
    summarize_relations as _summarize_relations_new,
)
from .harness.trust import compute_trust_scores as _compute_trust_scores_new


# Backward compatibility aliases - use new module functions
def _compute_trust_scores(
    results: Sequence[JSONDict],
    test_inputs: Sequence[Tuple[object, ...]],
    spec: Spec,
) -> Optional[JSONDict]:
    """Backward compatibility wrapper for compute_trust_scores."""
    return _compute_trust_scores_new(results, test_inputs, spec)


# Backward compatibility alias
def _estimate_power(
    p_baseline: float,
    p_candidate: float,
    sample_size: int,
    alpha_value: float,
    delta_value: float,
    power_target: float,
) -> Tuple[float, Optional[int]]:
    """Backward compatibility wrapper for estimate_power."""
    return _estimate_power_new(
        p_baseline, p_candidate, sample_size, alpha_value, delta_value, power_target
    )


def _fingerprint_payload(payload: JSONValue) -> str:
    normalized = _serialize_for_report(payload)
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


# Use ExecutionPlan from new module (already imported above)
# ExecutionPlan is re-exported for backward compatibility

# Backward compatibility alias
def _prepare_execution_plan(
    *,
    task_name: str,
    spec: Spec,
    n: int,
    seed: int,
    parallel: Optional[int],
    dispatcher: Dispatcher | str | None,
    queue_config: JSONDict | None,
    monitors: Sequence[Monitor] | None,
    explicit_inputs: Optional[List[Tuple[object, ...]]],
    executor: Optional[str],
) -> ExecutionPlan:
    """Backward compatibility wrapper for prepare_execution_plan."""
    return _prepare_execution_plan_new(
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


# Backward compatibility alias
def _execute_implementations(
    plan: ExecutionPlan,
    *,
    baseline_path: str,
    candidate_path: str,
    timeout_s: float,
    mem_mb: int,
    executor: Optional[str],
    executor_config: JSONDict | None,
    baseline_executor: Optional[str],
    baseline_executor_config: JSONDict | None,
    candidate_executor: Optional[str],
    candidate_executor_config: JSONDict | None,
) -> Tuple[List[JSONDict], List[JSONDict]]:
    """Backward compatibility wrapper for execute_implementations."""
    return _execute_implementations_new(
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


# Backward compatibility alias
def _summarize_llm_results(results: Sequence[JSONDict]) -> JSONDict:
    """Backward compatibility wrapper for summarize_llm_results."""
    return _summarize_llm_results_new(results)


# Backward compatibility alias
def _compose_llm_metrics(
    baseline_summary: JSONDict,
    candidate_summary: JSONDict,
) -> Optional[JSONDict]:
    """Backward compatibility wrapper for compose_llm_metrics."""
    return _compose_llm_metrics_new(baseline_summary, candidate_summary)


# Backward compatibility alias
def _evaluate_roles(
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
    """Backward compatibility wrapper for evaluate_roles."""
    return _evaluate_roles_new(
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


# Backward compatibility alias
def _summarize_relations(
    spec: Spec,
    baseline_metrics: JSONDict,
    candidate_metrics: JSONDict,
    *,
    alpha: float,
    relation_correction: Optional[str],
) -> Tuple[List[JSONDict], Dict[str, JSONDict], Optional[JSONDict]]:
    """Backward compatibility wrapper for summarize_relations."""
    return _summarize_relations_new(
        spec, baseline_metrics, candidate_metrics, alpha=alpha, relation_correction=relation_correction
    )


# Backward compatibility aliases for metric functions
def _safe_extract_metric(metric: Metric, result: JSONDict, args: Tuple[object, ...]) -> Optional[float]:
    """Backward compatibility wrapper."""
    return _safe_extract_metric_new(metric, result, args)

def _metric_memo_key(metric: Metric) -> Optional[str]:
    """Backward compatibility wrapper."""
    if getattr(metric, "memoize_key", None):
        return metric.memoize_key
    if getattr(metric, "memoize", False):
        return metric.name
    return None

def _get_or_compute_metric_value(
    metric: Metric,
    result: JSONDict,
    args: Tuple[object, ...],
    *,
    memo_key: Optional[str],
    cache: Dict[str, Dict[int, Optional[float]]],
    index: int,
) -> Optional[float]:
    """Backward compatibility wrapper."""
    return _get_or_compute_metric_value_new(metric, result, args, memo_key=memo_key, cache=cache, index=index)

def _should_sample_metric(metric: Metric, index: int, global_seed: Optional[int]) -> bool:
    """Backward compatibility wrapper."""
    return _should_sample_metric_new(metric, index, global_seed)

def _aggregate_metric_values(
    values: Sequence[Optional[float]],
    *,
    kind: str,
    total_count: int,
) -> JSONDict:
    """Backward compatibility wrapper."""
    return _aggregate_metric_values_new(values, kind=kind, total_count=total_count)

def _bootstrap_metric_delta(
    deltas: Sequence[float],
    *,
    kind: str,
    samples: int,
    alpha: float,
    seed: Optional[int],
) -> Optional[JSONDict]:
    """Backward compatibility wrapper."""
    return _bootstrap_metric_delta_new(deltas, kind=kind, samples=samples, alpha=alpha, seed=seed)

def _collect_metrics(
    metrics: Sequence[Metric],
    baseline_results: Sequence[JSONDict],
    candidate_results: Sequence[JSONDict],
    test_inputs: Sequence[Tuple[object, ...]],
    *,
    seed: Optional[int],
) -> JSONDict:
    """Backward compatibility wrapper."""
    return _collect_metrics_new(metrics, baseline_results, candidate_results, test_inputs, seed=seed)


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
    min_delta: float = 0.02,
    bootstrap_samples: int = 1000,
    ci_method: str = "bootstrap",
    rr_ci_method: str = "log",
    bayesian_hierarchical: bool = False,
    bayesian_posterior_predictive: bool = False,
    bayesian_samples: int = 5000,
    executor: str | None = None,
    executor_config: JSONDict | None = None,
    baseline_executor: str | None = None,
    candidate_executor: str | None = None,
    baseline_executor_config: JSONDict | None = None,
    candidate_executor_config: JSONDict | None = None,
    dispatcher: Dispatcher | str | None = None,
    queue_config: JSONDict | None = None,
    monitors: Sequence[Monitor] | None = None,
    failed_artifact_limit: Optional[int] = None,
    failed_artifact_ttl_days: Optional[int] = None,
    policy_version: Optional[str] = None,
    explicit_inputs: Optional[List[Tuple[object, ...]]] = None,
    min_pass_rate: float = 0.80,
    power_target: float = 0.8,
    policy_config: Optional[JSONDict] = None,
    shrink_violations: bool = False,
    sequential_method: str = "none",
    max_looks: int = 1,
    look_number: int = 1,
    relation_correction: Optional[str] = None,
    adaptive_testing: bool = False,
    adaptive_min_sample_size: int = 50,
    adaptive_check_interval: int = 50,
    adaptive_power_threshold: float = 0.95,
    adaptive_max_sample_size: Optional[int] = None,
    adaptive_group_sequential: bool = False,
    adaptive_sequential_method: str = "pocock",
    adaptive_max_looks: int = 5,
    **deprecated_kwargs: Any,
) -> JSONDict:
    """
    Run evaluation comparing baseline and candidate implementations.

    Returns comprehensive metrics including bootstrap confidence intervals.
    """
    if "improve_delta" in deprecated_kwargs:
        warnings.warn(
            "The 'improve_delta' argument to run_eval is deprecated; use 'min_delta' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        min_delta = deprecated_kwargs.pop("improve_delta")
    if deprecated_kwargs:
        unexpected = ", ".join(sorted(deprecated_kwargs))
        raise TypeError(f"run_eval() got unexpected keyword arguments: {unexpected}")

    spec = get_task(task_name)

    baseline_exec = baseline_executor or executor
    candidate_exec = candidate_executor or executor

    baseline_exec_config = (
        baseline_executor_config if baseline_executor_config is not None else executor_config
    )
    candidate_exec_config = (
        candidate_executor_config if candidate_executor_config is not None else executor_config
    )

    # Check if adaptive testing is enabled
    from .adaptive import AdaptiveConfig
    
    adaptive_config = AdaptiveConfig(
        enabled=adaptive_testing,
        min_sample_size=adaptive_min_sample_size,
        check_interval=adaptive_check_interval,
        power_threshold=adaptive_power_threshold,
        max_sample_size=adaptive_max_sample_size,
        early_stop_enabled=True,
        group_sequential=adaptive_group_sequential,
        sequential_method=adaptive_sequential_method,
        max_looks=adaptive_max_looks,
        look_times=None,  # Can be extended to support custom look times
    )
    
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
        executor=candidate_exec or baseline_exec,
    )

    test_inputs = plan.test_inputs
    n = plan.total_cases
    worker_count = plan.worker_count
    dispatcher_obj = plan.dispatcher
    monitor_objs = plan.monitors
    run_id = plan.run_id

    # Use adaptive execution if enabled, otherwise normal execution
    if adaptive_testing:
        from .harness import adaptive_execution
        
        baseline_results, candidate_results, adaptive_metadata = adaptive_execution.execute_adaptively(
            plan=plan,
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
            alpha=alpha,
            min_delta=min_delta,
            power_target=power_target,
            adaptive_config=adaptive_config,
            violation_cap=violation_cap,
            seed=seed,
            shrink_violations=shrink_violations,
            spec=spec,
        )
        
        # Update n to reflect actual samples run
        n = adaptive_metadata.get("final_n", n)
    else:
        baseline_results, candidate_results = _execute_implementations(
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
        adaptive_metadata = {"adaptive_testing": False}
    baseline_llm_summary = _summarize_llm_results(baseline_results)
    candidate_llm_summary = _summarize_llm_results(candidate_results)
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

    paired_stats = _compute_paired_stats_new(
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

    delta_ci = _compute_delta_ci_new(
        baseline_metrics,
        candidate_metrics,
        alpha=alpha,
        seed=seed,
        samples=bootstrap_samples,
        method=ci_method,
        hierarchical=bayesian_hierarchical,
        bayesian_samples=bayesian_samples,
    )

    def _recompute_delta_ci(new_alpha: float) -> List[float]:
        return _compute_delta_ci_new(
            baseline_metrics,
            candidate_metrics,
            alpha=new_alpha,
            seed=seed,
            samples=bootstrap_samples,
            method=ci_method,
            hierarchical=bayesian_hierarchical,
            bayesian_samples=bayesian_samples,
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
    rr_value, rr_ci = _compute_relative_risk_new(
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
            "min_delta": min_delta,
            "improve_delta": min_delta,  # Deprecated alias for backwards compatibility
            "min_pass_rate": min_pass_rate,
            "violation_cap": violation_cap,
            "parallel": worker_count,
            "bootstrap_samples": bootstrap_samples,
            "ci_method": ci_method,
            "rr_ci_method": rr_ci_method,
            "bayesian_hierarchical": bayesian_hierarchical,
            "bayesian_posterior_predictive": bayesian_posterior_predictive,
            "bayesian_samples": bayesian_samples,
            "executor": executor or candidate_exec or baseline_exec,
            "executor_config": _serialize_for_report(
                executor_config if executor_config is not None else candidate_exec_config
            ),
            "baseline_executor": baseline_exec or executor,
            "candidate_executor": candidate_exec or executor,
            "baseline_executor_config": _serialize_for_report(baseline_exec_config),
            "candidate_executor_config": _serialize_for_report(candidate_exec_config),
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

    if bayesian_posterior_predictive:
        bayesian_stats = _compute_bayesian_posterior_predictive(
            baseline_metrics,
            candidate_metrics,
            samples=bayesian_samples,
            hierarchical=bayesian_hierarchical,
            seed=seed,
        )
        result["bayesian"] = {
            "posterior_predictive": bayesian_stats,
            "hierarchical": bayesian_hierarchical,
            "samples": bayesian_samples,
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
            min_delta=min_delta,
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

    power_estimate, recommended_n = _estimate_power_new(
        baseline_metrics["pass_rate"],
        candidate_metrics["pass_rate"],
        n,
        alpha,
        min_delta,
        power_target,
    )
    result["statistics"] = {
        "power_estimate": power_estimate,
        "power_target": power_target,
        "recommended_n": recommended_n,
        "min_delta": min_delta,
        "alpha": alpha,
    }
    
    # Add adaptive testing metadata if enabled
    if adaptive_testing:
        result["adaptive"] = adaptive_metadata
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

    metrics_payload = _collect_metrics_new(
        spec.metrics,
        baseline_results,
        candidate_results,
        test_inputs,
        seed=seed,
    )
    if metrics_payload:
        result["metrics"] = metrics_payload

    if sequential_method == "sprt":
        lower_bound, upper_bound = sprt_boundary(
            alpha=alpha,
            beta=1 - power_target,
            effect_size=min_delta,
            baseline_rate=baseline_metrics["pass_rate"],
            sample_size=n,
        )
        continue_sampling, sprt_reason = should_continue_sprt(
            observed_rate=candidate_metrics["pass_rate"],
            baseline_rate=baseline_metrics["pass_rate"],
            effect_size=min_delta,
            alpha=alpha,
            beta=1 - power_target,
            sample_size=n,
        )
        result.setdefault("sequential", {})["sprt"] = {
            "continue_sampling": continue_sampling,
            "reason": sprt_reason,
            "lower_bound": lower_bound,
            "upper_bound": upper_bound,
        }

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
        "executor": result["config"]["executor"] or "local",
        "baseline_executor": result["config"].get("baseline_executor") or "local",
        "candidate_executor": result["config"].get("candidate_executor") or "local",
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
    baseline_executor_config_payload = result["config"].get("baseline_executor_config")
    if baseline_executor_config_payload is not None:
        sandbox_provenance["baseline_executor_config"] = baseline_executor_config_payload
        sandbox_provenance["baseline_executor_config_fingerprint"] = _fingerprint_payload(
            baseline_executor_config_payload
        )
    candidate_executor_config_payload = result["config"].get("candidate_executor_config")
    if candidate_executor_config_payload is not None:
        sandbox_provenance["candidate_executor_config"] = candidate_executor_config_payload
        sandbox_provenance["candidate_executor_config_fingerprint"] = _fingerprint_payload(
            candidate_executor_config_payload
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

    llm_metrics_payload = _compose_llm_metrics(baseline_llm_summary, candidate_llm_summary)
    if llm_metrics_payload:
        result["llm_metrics"] = llm_metrics_payload
        baseline_provider = baseline_exec or executor or "unknown"
        candidate_provider = candidate_exec or executor or "unknown"

        baseline_retries = int(baseline_llm_summary.get("retry_total", 0))
        candidate_retries = int(candidate_llm_summary.get("retry_total", 0))

        if baseline_retries > 0:
            increment_llm_retries(baseline_provider, "baseline", baseline_retries)
        if candidate_retries > 0:
            increment_llm_retries(candidate_provider, "candidate", candidate_retries)

        log_event(
            "llm_retry_summary",
            baseline={
                "provider": baseline_provider,
                "retries": baseline_retries,
                "success_rate": baseline_llm_summary.get("success_rate"),
            },
            candidate={
                "provider": candidate_provider,
                "retries": candidate_retries,
                "success_rate": candidate_llm_summary.get("success_rate"),
            },
        )

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

    try:
        write_audit_entry(result)
    except Exception as audit_exc:  # pragma: no cover - best-effort logging
        log_event("audit_log_failed", error=str(audit_exc))

    return result


# Backward compatibility alias
def _evaluate_results(
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
    """Backward compatibility wrapper for evaluate_results."""
    return _evaluate_results_new(
        results, spec, test_inputs, violation_cap,
        role=role, seed=seed, rerun=rerun, shrink_violations=shrink_violations
    )


def _compute_paired_stats(
    baseline_indicators: Sequence[int],
    candidate_indicators: Sequence[int],
) -> Optional[JSONDict]:
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


# Backward compatibility aliases
def _relation_rng(
    seed: int,
    case_index: int,
    relation_index: int,
    relation_name: str,
) -> random.Random:
    """Backward compatibility wrapper for relation_rng."""
    return _relation_rng_new(seed, case_index, relation_index, relation_name)

def _relation_cache_key(relation_index: int, args: Tuple[object, ...]) -> str:
    """Backward compatibility wrapper for relation_cache_key."""
    return _relation_cache_key_new(relation_index, args)

def _build_call_spec(
    file_path: str,
    *,
    timeout_s: float,
    mem_mb: int,
    executor: str | None,
    executor_config: JSONDict | None,
) -> JSONDict:
    """Backward compatibility wrapper for build_call_spec."""
    return _build_call_spec_new(file_path, timeout_s=timeout_s, mem_mb=mem_mb, executor=executor, executor_config=executor_config)


def _compute_delta_ci(
    baseline_metrics: JSONDict,
    candidate_metrics: JSONDict,
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
