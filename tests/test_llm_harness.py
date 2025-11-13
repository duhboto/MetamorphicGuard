"""
Tests for the LLMHarness convenience wrapper.
"""

from __future__ import annotations

from typing import Any, Dict

import pytest

from metamorphic_guard.llm_harness import LLMHarness


def test_llm_harness_passes_role_specific_configs(monkeypatch):
    """LLMHarness should forward distinct baseline/candidate configs to run_eval."""

    captured: Dict[str, Any] = {}

    def fake_run_eval(*args, **kwargs):
        captured["kwargs"] = kwargs
        return {
            "baseline": {
                "passes": 1,
                "total": 1,
                "pass_rate": 1.0,
                "prop_violations": [],
                "mr_violations": [],
            },
            "candidate": {
                "passes": 1,
                "total": 1,
                "pass_rate": 1.0,
                "prop_violations": [],
                "mr_violations": [],
            },
            "delta_ci": [0.0, 0.0],
            "decision": {"adopt": True, "reason": "meets_gate"},
            "statistics": {},
        }

    monkeypatch.setattr("metamorphic_guard.llm_harness.run_eval", fake_run_eval)

    harness = LLMHarness(model="gpt-4", provider="openai", executor_config={"api_key": "test-key"})
    result = harness.run(
        case={"system": "candidate-system", "user": "hello"},
        baseline_model="gpt-3.5-turbo",
        baseline_system="baseline-system",
        n=1,
        seed=123,
        bootstrap=False,
    )

    kwargs = captured["kwargs"]
    assert kwargs["baseline_executor_config"]["model"] == "gpt-3.5-turbo"
    assert kwargs["baseline_executor_config"]["system_prompt"] == "baseline-system"
    assert kwargs["candidate_executor_config"]["model"] == "gpt-4"
    assert kwargs["candidate_executor_config"]["system_prompt"] == "candidate-system"
    assert kwargs["baseline_executor"] == "openai"
    assert kwargs["candidate_executor"] == "openai"
    assert kwargs["executor"] == "openai"

    llm_metrics = result.get("llm_metrics")
    assert llm_metrics is not None
    assert "baseline" in llm_metrics and "candidate" in llm_metrics


def test_llm_harness_retains_llm_metrics(monkeypatch):
    """LLMHarness should keep harness-provided llm_metrics intact."""

    metrics_payload = {
        "baseline": {"count": 1, "total_cost_usd": 0.05, "total_tokens": 120, "retry_total": 0},
        "candidate": {"count": 1, "total_cost_usd": 0.04, "total_tokens": 110, "retry_total": 0},
        "cost_delta_usd": -0.01,
        "cost_ratio": 0.8,
    }

    def fake_run_eval(*args, **kwargs):
        return {
            "baseline": {"passes": 1, "total": 1, "pass_rate": 1.0, "prop_violations": [], "mr_violations": []},
            "candidate": {"passes": 1, "total": 1, "pass_rate": 1.0, "prop_violations": [], "mr_violations": []},
            "delta_ci": [0.0, 0.0],
            "decision": {"adopt": True, "reason": "meets_gate"},
            "statistics": {},
            "llm_metrics": metrics_payload,
        }

    monkeypatch.setattr("metamorphic_guard.llm_harness.run_eval", fake_run_eval)

    harness = LLMHarness(model="gpt-4", provider="openai", executor_config={"api_key": "test-key"})
    result = harness.run(case="hello", bootstrap=False)

    assert result["llm_metrics"]["cost_delta_usd"] == pytest.approx(-0.01, rel=1e-6)
    assert result["llm_metrics"]["cost_ratio"] == pytest.approx(0.8, rel=1e-6)

