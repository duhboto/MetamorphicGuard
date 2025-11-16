"""
Tests for harness evaluation and bootstrap CI calculation.
"""

from pathlib import Path
import textwrap

import pytest

from metamorphic_guard.harness import run_eval
from metamorphic_guard.harness.statistics import (
    compute_bootstrap_ci,
    compute_delta_ci,
    compute_relative_risk,
)
from metamorphic_guard.harness.reporting import (
    collect_metrics,
    compose_llm_metrics,
    evaluate_results,
    summarize_llm_results,
)
from metamorphic_guard.specs import (
    Metric,
    MetamorphicRelation,
    Property,
    Spec,
    task,
    register_spec,
    unregister_spec,
)
from metamorphic_guard.stability import multiset_equal


def test_bootstrap_ci_calculation():
    """Test bootstrap confidence interval calculation."""
    # Test case where candidate is clearly better
    baseline_indicators = [1, 0, 1, 0, 1] * 20  # 60% pass rate
    candidate_indicators = [1, 1, 1, 0, 1] * 20  # 80% pass rate
    
    ci = compute_bootstrap_ci(
        baseline_indicators,
        candidate_indicators,
        alpha=0.05,
        seed=123,
        samples=500,
    )
    
    assert len(ci) == 2
    assert ci[0] < ci[1]  # Lower bound < upper bound
    assert ci[0] > 0  # Should show improvement


def test_bootstrap_ci_no_improvement():
    """Test bootstrap CI when there's no improvement."""
    indicators = [1, 0, 1, 0, 1] * 20  # Same for both
    
    ci = compute_bootstrap_ci(indicators, indicators, alpha=0.05, seed=321, samples=500)
    
    assert len(ci) == 2
    # CI should contain 0 (no improvement)
    assert ci[0] <= 0 <= ci[1]


def test_bootstrap_cluster_ci():
    """Cluster-aware bootstrap should handle grouped observations."""
    baseline = [1, 1, 0, 0] * 10
    candidate = [1, 1, 1, 0] * 10
    clusters = [0, 0, 1, 1] * 10

    ci = compute_bootstrap_ci(
        baseline,
        candidate,
        alpha=0.1,
        seed=42,
        samples=200,
        clusters=clusters,
    )

    assert len(ci) == 2
    assert ci[0] <= ci[1]


def test_evaluate_results():
    """Test result evaluation against properties."""
    # Create a simple spec
    spec = Spec(
        gen_inputs=lambda n, seed: [(1, 2), (3, 4)],
        properties=[
            Property(
                check=lambda out, x, y: out == x + y,
                description="Sum property"
            )
        ],
        relations=[],
        equivalence=multiset_equal
    )
    
    # Mock results
    results = [
        {"success": True, "result": 3},  # 1 + 2 = 3 ✓
        {"success": True, "result": 8}   # 3 + 4 = 7, but result is 8 ✗
    ]
    test_inputs = [(1, 2), (3, 4)]
    
    metrics = evaluate_results(
        results,
        spec,
        test_inputs,
        violation_cap=10,
        role="candidate",
        seed=123,
        rerun=lambda args: {"success": True, "result": None},
    )
    
    assert metrics["passes"] == 1
    assert metrics["total"] == 2
    assert metrics["pass_rate"] == 0.5
    assert len(metrics["prop_violations"]) == 1
    assert metrics["prop_violations"][0]["test_case"] == 1


def test_evaluate_results_failure_handling():
    """Test evaluation handles execution failures."""
    spec = Spec(
        gen_inputs=lambda n, seed: [(1, 2)],
        properties=[
            Property(
                check=lambda out, x, y: out == x + y,
                description="Sum property"
            )
        ],
        relations=[],
        equivalence=multiset_equal
    )
    
    # Mock results with failures
    results = [
        {"success": False, "result": None, "error": "Timeout"}
    ]
    test_inputs = [(1, 2)]
    
    metrics = evaluate_results(
        results,
        spec,
        test_inputs,
        violation_cap=10,
        role="candidate",
        seed=123,
        rerun=lambda args: {"success": False, "error": "Timeout"},
    )
    
    assert metrics["passes"] == 0
    assert metrics["total"] == 1
    assert metrics["pass_rate"] == 0.0


def test_evaluate_results_cluster_labels():
    """Cluster labels should follow spec.cluster_key."""
    spec = Spec(
        gen_inputs=lambda n, seed: [(0, 1), (1, 1), (2, 1)],
        properties=[
            Property(
                check=lambda out, x, y: out == x + y,
                description="Sum property"
            )
        ],
        relations=[],
        equivalence=multiset_equal,
        cluster_key=lambda args: args[0] % 2,
    )

    results = [
        {"success": True, "result": 1},
        {"success": True, "result": 2},
        {"success": True, "result": 3},
    ]

    metrics = evaluate_results(
        results,
        spec,
        spec.gen_inputs(3, 0),
        violation_cap=5,
        role="baseline",
        seed=0,
        rerun=lambda args: {"success": True, "result": None},
    )

    assert metrics["cluster_labels"] == [0, 1, 0]


def test_metamorphic_relation_violations_detected():
    """Ensure metamorphic relations are re-run and violations recorded."""
    inputs = [([3, 1, 2], 2)]

    spec = Spec(
        gen_inputs=lambda n, seed: inputs,
        properties=[
            Property(
                check=lambda out, L, k: True,
                description="Always passes",
            )
        ],
        relations=[
            MetamorphicRelation(
                name="permute",
                transform=lambda L, k: (list(reversed(L)), k),
            )
        ],
        equivalence=lambda a, b: a == b,
    )

    run_results = [{"success": True, "result": [3, 2]}]

    def rerun(_args):
        return {"success": True, "result": [1, 2]}  # Different order to trigger failure

    metrics = evaluate_results(
        run_results,
        spec,
        inputs,
        violation_cap=5,
        role="candidate",
        seed=321,
        rerun=rerun,
    )

    assert metrics["passes"] == 0
    assert metrics["pass_indicators"] == [0]
    assert metrics["mr_violations"], "Expected metamorphic relation violation to be recorded"


def test_relation_rng_injection():
    """Metamorphic relations flagged as seeded receive deterministic RNGs."""
    calls: list[float] = []

    def transform(value: int, *, rng):
        calls.append(rng.random())
        return (value,)

    inputs = [(1,), (2,)]
    spec = Spec(
        gen_inputs=lambda n, seed: inputs,
        properties=[
            Property(
                check=lambda out, original: True,
                description="Always passes",
            )
        ],
        relations=[
            MetamorphicRelation(
                name="rng_relation",
                transform=transform,
                expect="equal",
                accepts_rng=True,
            )
        ],
        equivalence=lambda a, b: a == b,
    )

    results = [{"success": True, "result": (1,)}, {"success": True, "result": (2,)}]

    evaluate_results(
        results,
        spec,
        inputs,
        violation_cap=5,
        role="candidate",
        seed=123,
        rerun=lambda args: {"success": True, "result": args},
    )
    first_calls = list(calls)

    calls.clear()
    evaluate_results(
        results,
        spec,
        inputs,
        violation_cap=5,
        role="candidate",
        seed=123,
        rerun=lambda args: {"success": True, "result": args},
    )

    assert calls == first_calls


def test_relation_rerun_cache():
    """Identical transformed inputs should reuse sandbox results."""
    call_counter = {"count": 0}

    def transform(value: int):
        return (value,)

    def rerun(args):
        call_counter["count"] += 1
        return {"success": True, "result": args}

    inputs = [(1,), (1,)]
    spec = Spec(
        gen_inputs=lambda n, seed: inputs,
        properties=[
            Property(
                check=lambda out, original: True,
                description="Always passes",
            )
        ],
        relations=[
            MetamorphicRelation(
                name="identity",
                transform=transform,
            )
        ],
        equivalence=lambda a, b: a == b,
    )

    results = [{"success": True, "result": (1,)}, {"success": True, "result": (1,)}]

    evaluate_results(
        results,
        spec,
        inputs,
        violation_cap=5,
        role="candidate",
        seed=0,
        rerun=rerun,
    )

    assert call_counter["count"] == 1


def test_run_eval_applies_relation_correction_holm():
    repo_root = Path(__file__).resolve().parents[1]
    baseline = repo_root / "examples" / "top_k_baseline.py"
    candidate = repo_root / "examples" / "top_k_improved.py"

    result = run_eval(
        task_name="top_k",
        baseline_path=str(baseline),
        candidate_path=str(candidate),
        n=12,
        seed=7,
        bootstrap_samples=200,
        relation_correction="holm",
    )

    coverage = result.get("relation_coverage")
    assert coverage is not None
    correction = coverage.get("correction")
    assert correction is not None
    assert correction["method"] == "holm-bonferroni"
    assert correction["alpha"] == pytest.approx(0.05)

    for relation in coverage["relations"]:
        assert "p_value" in relation
        assert "adjusted_p_value" in relation
        assert "significant" in relation


@task("metric_demo")
def metric_demo_spec():
    return Spec(
        gen_inputs=lambda n, seed: [(i,) for i in range(n)],
        properties=[
            Property(
                check=lambda out, x: isinstance(out, dict) and "value" in out and "cost" in out,
                description="Output contains value and cost",
            )
        ],
        relations=[],
        equivalence=lambda a, b: a == b,
        metrics=[
            Metric(
                name="value_mean",
                extract=lambda output, args: output["value"],
                kind="mean",
                higher_is_better=True,
            ),
            Metric(
                name="total_cost",
                extract=lambda output, args: output["cost"],
                kind="sum",
                higher_is_better=False,
            ),
        ],
    )


def test_run_eval_collects_metrics(tmp_path):
    baseline_code = textwrap.dedent(
        """
        def solve(x):
            value = float(x)
            return {"value": value, "cost": value + 2.0}
        """
    )
    candidate_code = textwrap.dedent(
        """
        def solve(x):
            value = float(x)
            return {"value": value + 0.5, "cost": value + 1.5}
        """
    )

    baseline_file = tmp_path / "baseline_metrics.py"
    candidate_file = tmp_path / "candidate_metrics.py"
    baseline_file.write_text(baseline_code, encoding="utf-8")
    candidate_file.write_text(candidate_code, encoding="utf-8")

    result = run_eval(
        task_name="metric_demo",
        baseline_path=str(baseline_file),
        candidate_path=str(candidate_file),
        n=5,
        seed=42,
        min_delta=0.0,
    )

    metrics = result.get("metrics")
    assert metrics is not None

    value_metric = metrics["value_mean"]
    assert value_metric["baseline"]["count"] == 5
    assert value_metric["baseline"]["missing"] == 0
    assert value_metric["baseline"]["mean"] == pytest.approx(2.0, rel=1e-6)
    assert value_metric["candidate"]["mean"] == pytest.approx(2.5, rel=1e-6)
    assert value_metric["delta"]["difference"] == pytest.approx(0.5, rel=1e-6)
    assert value_metric["delta"]["paired_mean"] == pytest.approx(0.5, rel=1e-6)
    ci_payload = value_metric["delta"]["ci"]
    assert ci_payload["mean"]["estimate"] == pytest.approx(0.5, rel=1e-6)
    assert ci_payload["mean"]["upper"] >= ci_payload["mean"]["lower"]

    cost_metric = metrics["total_cost"]
    assert cost_metric["baseline"]["count"] == 5
    assert cost_metric["baseline"]["missing"] == 0
    assert cost_metric["baseline"]["sum"] == pytest.approx(20.0, rel=1e-6)
    assert cost_metric["candidate"]["sum"] == pytest.approx(17.5, rel=1e-6)
    assert cost_metric["delta"]["difference"] == pytest.approx(-2.5, rel=1e-6)
    assert cost_metric["delta"]["paired_mean"] == pytest.approx(-0.5, rel=1e-6)
    assert cost_metric["delta"]["ratio"] == pytest.approx(0.875, rel=1e-6)
    cost_ci = cost_metric["delta"]["ci"]
    assert cost_ci["sum"]["estimate"] == pytest.approx(-2.5, rel=1e-6)
    assert cost_ci["sum"]["upper"] >= cost_ci["sum"]["lower"]

    provenance = result.get("provenance")
    assert provenance is not None
    sandbox_info = provenance.get("sandbox")
    assert sandbox_info is not None
    assert sandbox_info["executor"] == "local"
    assert sandbox_info["call_spec_fingerprint"]["baseline"]
    executions = sandbox_info.get("executions")
    assert executions is not None
    assert executions["baseline"]["executor"] == "local"
    assert executions["baseline"]["run_state"] == "success"
    assert sandbox_info["executions_fingerprint"]["baseline"]


def testcollect_metrics_sampling_and_memoization():
    call_counts = {"baseline": 0, "candidate": 0}

    def extractor(output, args):
        role = output.get("role")
        if role in call_counts:
            call_counts[role] += 1
        return float(output["value"])

    metrics = [
        Metric(
            name="value_mean_sampled",
            extract=extractor,
            kind="mean",
            higher_is_better=True,
            ci_method=None,
            sample_rate=0.5,
            seed=99,
            memoize_key="value",
        ),
        Metric(
            name="value_sum_full",
            extract=extractor,
            kind="sum",
            higher_is_better=True,
            memoize_key="value",
        ),
    ]

    baseline_results = []
    candidate_results = []
    test_inputs = []
    for i in range(10):
        test_inputs.append((i,))
        baseline_results.append(
            {"success": True, "result": {"value": float(i), "role": "baseline"}}
        )
        candidate_results.append(
            {"success": True, "result": {"value": float(i) + 1.0, "role": "candidate"}}
        )

    payload = collect_metrics(
        metrics,
        baseline_results,
        candidate_results,
        test_inputs,
        seed=42,
    )

    sampled_metric = payload["value_mean_sampled"]
    sample_count = sampled_metric["baseline"]["count"]
    assert 0 < sample_count < len(test_inputs)
    assert sampled_metric["baseline"]["missing"] == len(test_inputs) - sample_count
    assert sampled_metric["candidate"]["count"] == sample_count

    sum_metric = payload["value_sum_full"]
    assert sum_metric["baseline"]["sum"] == pytest.approx(sum(range(10)), rel=1e-6)
    assert sum_metric["candidate"]["sum"] == pytest.approx(sum(range(10)) + 10.0, rel=1e-6)

    assert call_counts["baseline"] == len(test_inputs)
    assert call_counts["candidate"] == len(test_inputs)
def test_newcombe_ci_difference():
    baseline_metrics = {
        "passes": 60,
        "total": 100,
        "pass_indicators": [1] * 60 + [0] * 40,
    }
    candidate_metrics = {
        "passes": 90,
        "total": 100,
        "pass_indicators": [1] * 90 + [0] * 10,
    }

    ci = compute_delta_ci(
        baseline_metrics,
        candidate_metrics,
        alpha=0.05,
        seed=123,
        samples=500,
        method="newcombe",
    )

    assert ci[0] < ci[1]
    assert ci[0] > 0

    rr, rr_ci = compute_relative_risk(
        baseline_metrics,
        candidate_metrics,
        alpha=0.05,
        method="log",
    )

    assert rr > 1
    assert rr_ci[0] < rr_ci[1]


def testsummarize_llm_results_and_compose_metrics():
    baseline_results = [
        {
            "success": True,
            "tokens_prompt": 10,
            "tokens_completion": 5,
            "tokens_total": 15,
            "duration_ms": 120,
            "cost_usd": 0.02,
            "retries": 1,
        },
        {"success": False, "duration_ms": 140, "retries": 0},
    ]
    candidate_results = [
        {
            "success": True,
            "tokens_prompt": 12,
            "tokens_completion": 7,
            "tokens_total": 19,
            "duration_ms": 110,
            "cost_usd": 0.025,
            "retries": 2,
        }
    ]

    baseline_summary = summarize_llm_results(baseline_results)
    candidate_summary = summarize_llm_results(candidate_results)

    assert baseline_summary["count"] == 2
    assert baseline_summary["successes"] == 1
    assert baseline_summary["retry_total"] == 1
    assert baseline_summary["max_retries"] == 1
    assert baseline_summary["avg_latency_ms"] == pytest.approx(130.0, rel=1e-6)

    assert candidate_summary["count"] == 1
    assert candidate_summary["total_tokens"] == 19
    assert candidate_summary["retry_total"] == 2

    llm_metrics = compose_llm_metrics(baseline_summary, candidate_summary)
    assert llm_metrics is not None
    assert llm_metrics["cost_delta_usd"] == pytest.approx(0.005, rel=1e-6)
    assert llm_metrics["tokens_delta"] == 4
    assert llm_metrics["retry_delta"] == 1
    assert llm_metrics["cost_ratio"] == pytest.approx(0.025 / 0.02, rel=1e-6)


def test_run_eval_uses_role_specific_executor_configs(monkeypatch, tmp_path):
    """run_eval should dispatch role-specific executor configs to the sandbox."""

    calls = []

    def fake_run_in_sandbox(
        file_path,
        func_name,
        call_args,
        timeout_s,
        mem_mb,
        *,
        executor=None,
        executor_config=None,
    ):
        calls.append(
            {
                "executor": executor,
                "config": dict(executor_config or {}),
                "file_path": file_path,
                "args": call_args,
            }
        )
        return {
            "success": True,
            "result": {"value": executor_config.get("label") if executor_config else None},
            "stdout": "",
            "stderr": "",
            "duration_ms": 1.0,
        }

    # Patch run_in_sandbox in the execution module where it's actually used
    monkeypatch.setattr("metamorphic_guard.harness.execution.run_in_sandbox", fake_run_in_sandbox)

    spec = Spec(
        gen_inputs=lambda n, seed: [(i,) for i in range(n)],
        properties=[],
        relations=[],
        equivalence=lambda a, b: True,
    )
    register_spec("dummy_role_exec", spec, overwrite=True)

    baseline_file = tmp_path / "baseline_impl.py"
    candidate_file = tmp_path / "candidate_impl.py"
    baseline_file.write_text("def solve(*args):\n    return 'baseline'\n", encoding="utf-8")
    candidate_file.write_text("def solve(*args):\n    return 'candidate'\n", encoding="utf-8")

    try:
        report = run_eval(
            task_name="dummy_role_exec",
            baseline_path=str(baseline_file),
            candidate_path=str(candidate_file),
            n=2,
            seed=0,
            executor="local",
            baseline_executor="local",
            candidate_executor="local",
            baseline_executor_config={"label": "baseline_cfg"},
            candidate_executor_config={"label": "candidate_cfg"},
        )
    finally:
        unregister_spec("dummy_role_exec")

    assert len(calls) == 4  # two baseline + two candidate executions
    # Check that baseline and candidate calls have different configs
    baseline_calls = [call for call in calls if call["config"].get("label") == "baseline_cfg"]
    candidate_calls = [call for call in calls if call["config"].get("label") == "candidate_cfg"]

    assert baseline_calls, "Expected baseline executions using baseline executor config"
    assert candidate_calls, "Expected candidate executions using candidate executor config"

    assert all(call["config"]["label"] == "baseline_cfg" for call in baseline_calls)
    assert all(call["config"]["label"] == "candidate_cfg" for call in candidate_calls)

    assert report["config"]["baseline_executor"] == "local"
    assert report["config"]["candidate_executor"] == "local"
    assert report["config"]["baseline_executor_config"]["label"] == "baseline_cfg"
    assert report["config"]["candidate_executor_config"]["label"] == "candidate_cfg"
