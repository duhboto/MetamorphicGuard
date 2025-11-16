"""
Main evaluation entry point - orchestrates the full evaluation workflow.
"""

from __future__ import annotations

import hashlib
import json
import warnings
from typing import Any, Callable, Dict, Hashable, List, Optional, Sequence, Tuple

from ..audit import write_audit_entry
from ..dispatch import Dispatcher
from ..gate import decide_adopt
from ..monitoring import Monitor
from ..observability import increment_llm_retries, log_event
from ..sequential_testing import should_continue_sprt, sprt_boundary
from ..specs import Spec, get_task
from ..types import JSONDict, JSONValue
from ..util import (
    collect_job_metadata,
    compute_spec_fingerprint,
    get_environment_fingerprint,
    sha256_file,
    write_failed_artifacts,
)
from .execution import (
    ExecutionPlan,
    build_call_spec,
    execute_implementations,
    prepare_execution_plan,
)
from .reporting import (
    collect_metrics,
    compose_llm_metrics,
    evaluate_roles,
    summarize_llm_results,
    summarize_relations,
)
from .statistics import (
    compute_bayesian_posterior_predictive,
    compute_delta_ci,
    compute_paired_stats,
    compute_relative_risk,
    estimate_power,
)
from .trust import compute_trust_scores


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


def _fingerprint_payload(payload: JSONValue) -> str:
    """Compute SHA256 fingerprint of a JSON-serializable payload."""
    normalized = _serialize_for_report(payload)
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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
    from ..adaptive import AdaptiveConfig
    
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
    
    plan = prepare_execution_plan(
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
        from ..harness import adaptive_execution
        from ..early_stopping import EarlyStoppingConfig
        
        # Configure early stopping if adaptive testing is enabled
        early_stopping_config = EarlyStoppingConfig(
            enabled=True,
            method="combined",  # Use combined method for best results
            confidence_threshold=0.95,
            min_samples=adaptive_config.min_sample_size,
        )
        
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
            early_stopping_config=early_stopping_config,
        )
        
        # Update n to reflect actual samples run
        n = adaptive_metadata.get("final_n", n)
    else:
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
        adaptive_metadata = {"adaptive_testing": False}
    baseline_llm_summary = summarize_llm_results(baseline_results)
    candidate_llm_summary = summarize_llm_results(candidate_results)
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

    baseline_metrics, candidate_metrics = evaluate_roles(
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

    paired_stats = compute_paired_stats(
        baseline_metrics.get("pass_indicators", []),
        candidate_metrics.get("pass_indicators", []),
    )

    baseline_call_spec = _serialize_for_report(
        build_call_spec(
            baseline_path,
            timeout_s=timeout_s,
            mem_mb=mem_mb,
            executor=executor,
            executor_config=executor_config,
        )
    )
    candidate_call_spec = _serialize_for_report(
        build_call_spec(
            candidate_path,
            timeout_s=timeout_s,
            mem_mb=mem_mb,
            executor=executor,
            executor_config=executor_config,
        )
    )

    # Compute trust scores if applicable (for RAG evaluations)
    baseline_trust = compute_trust_scores(baseline_results, test_inputs, spec)
    candidate_trust = compute_trust_scores(candidate_results, test_inputs, spec)

    delta_ci = compute_delta_ci(
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
        return compute_delta_ci(
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
        from ..sequential_testing import SequentialTestConfig, apply_sequential_correction
        
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
    rr_value, rr_ci = compute_relative_risk(
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
        bayesian_stats = compute_bayesian_posterior_predictive(
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

    power_estimate, recommended_n = estimate_power(
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

    relation_summary, category_totals, correction_metadata = summarize_relations(
        spec,
        baseline_metrics,
        candidate_metrics,
        alpha=alpha,
        relation_correction=relation_correction,
    )

    if relation_summary:
        relation_coverage_payload: JSONDict = {
            "relations": relation_summary,
            "categories": category_totals,
        }
        if correction_metadata:
            relation_coverage_payload["correction"] = correction_metadata

        result["relation_coverage"] = relation_coverage_payload
        result["statistics"]["relation_categories"] = category_totals
        if correction_metadata:
            result["statistics"]["relation_correction"] = correction_metadata

    metrics_payload = collect_metrics(
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
    provenance_data: JSONDict = {}
    
    # Library version
    try:
        from .. import __version__
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

    sandbox_provenance: JSONDict = {
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
    runtime_metadata: JSONDict = {}
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

    llm_metrics_payload = compose_llm_metrics(baseline_llm_summary, candidate_llm_summary)
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



