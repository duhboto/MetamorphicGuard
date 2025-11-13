"""
Tests for the LLMHarness convenience wrapper.
"""

from __future__ import annotations

from typing import Any, Dict

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

