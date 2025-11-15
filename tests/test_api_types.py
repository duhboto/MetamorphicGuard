"""
Tests for type safety in the public API.

Verifies that TypedDict definitions, JSONDict/JSONValue types, and type annotations
work correctly and maintain runtime compatibility.
"""

from __future__ import annotations

from typing import Dict, Mapping

import pytest

from metamorphic_guard.api import (
    EvaluationConfig,
    EvaluationResult,
    PolicyConfig,
    QueueConfig,
    ObservabilityConfig,
)
from metamorphic_guard.llm_harness import ExecutorConfig, EvaluationReport
from metamorphic_guard.types import JSONDict, JSONValue


class TestTypedDictDefinitions:
    """Test that TypedDict definitions work correctly."""

    def test_policy_config_accepts_valid_dict(self):
        """PolicyConfig should accept a valid policy dictionary."""
        policy: PolicyConfig = {
            "gating": {"min_delta": 0.02, "min_pass_rate": 0.80},
            "descriptor": {"name": "test-policy"},
            "name": "test-policy",
        }
        assert policy["name"] == "test-policy"
        assert policy["gating"]["min_delta"] == 0.02

    def test_policy_config_allows_partial(self):
        """PolicyConfig with total=False should allow partial dictionaries."""
        policy: PolicyConfig = {"name": "minimal-policy"}
        assert policy["name"] == "minimal-policy"

    def test_queue_config_accepts_valid_dict(self):
        """QueueConfig should accept a valid queue configuration."""
        queue: QueueConfig = {
            "backend": "redis",
            "url": "redis://localhost:6379/0",
            "heartbeat_timeout": 45.0,
            "enable_requeue": True,
        }
        assert queue["backend"] == "redis"
        assert queue["heartbeat_timeout"] == 45.0

    def test_observability_config_accepts_valid_dict(self):
        """ObservabilityConfig should accept valid observability settings."""
        obs: ObservabilityConfig = {
            "logging_enabled": True,
            "log_path": "/tmp/test.log",
            "metrics_enabled": True,
            "metrics_port": 9090,
        }
        assert obs["logging_enabled"] is True
        assert obs["metrics_port"] == 9090


class TestEvaluationConfigTypes:
    """Test that EvaluationConfig works with new types."""

    def test_evaluation_config_with_policy_config(self):
        """EvaluationConfig should accept PolicyConfig."""
        policy: PolicyConfig = {
            "gating": {"min_delta": 0.01, "min_pass_rate": 0.90},
            "name": "strict-policy",
        }
        config = EvaluationConfig(
            n=100,
            seed=42,
            policy_config=policy,
        )
        assert config.policy_config is not None
        assert config.policy_config["name"] == "strict-policy"

    def test_evaluation_config_with_extra_options(self):
        """EvaluationConfig should accept Dict[str, JSONValue] for extra_options."""
        extra: Dict[str, JSONValue] = {
            "parallel": 4,
            "executor": "docker",
            "executor_config": {"image": "python:3.11"},
        }
        config = EvaluationConfig(
            n=100,
            extra_options=extra,
        )
        assert config.extra_options["parallel"] == 4
        assert config.extra_options["executor"] == "docker"

    def test_evaluation_config_to_kwargs_returns_json_value(self):
        """to_kwargs() should return Dict[str, JSONValue]."""
        config = EvaluationConfig(n=100, seed=42)
        kwargs = config.to_kwargs()
        assert isinstance(kwargs, dict)
        assert kwargs["n"] == 100
        assert kwargs["seed"] == 42
        # Verify all values are JSON-serializable types
        for key, value in kwargs.items():
            assert isinstance(
                value,
                (str, int, float, bool, type(None), dict, list),
            ), f"Value for key '{key}' is not JSON-serializable: {type(value)}"


class TestEvaluationResultTypes:
    """Test that EvaluationResult works with JSONDict."""

    def test_evaluation_result_accepts_json_dict(self):
        """EvaluationResult should accept JSONDict for report."""
        report: JSONDict = {
            "task": "test_task",
            "n": 100,
            "seed": 42,
            "baseline": {"passes": 95, "total": 100, "pass_rate": 0.95},
            "candidate": {"passes": 98, "total": 100, "pass_rate": 0.98},
            "delta_pass_rate": 0.03,
            "delta_ci": [0.01, 0.05],
            "decision": {"adopt": True, "reason": "meets_gate"},
        }
        result = EvaluationResult(report=report)
        assert result.report["task"] == "test_task"
        assert result.adopt is True
        assert result.reason == "meets_gate"

    def test_evaluation_result_nested_structures(self):
        """EvaluationResult should handle nested JSON structures."""
        report: JSONDict = {
            "task": "test",
            "config": {
                "timeout_s": 2.0,
                "mem_mb": 512,
                "nested": {"deep": {"value": 42}},
            },
            "monitors": {
                "latency": {
                    "summary": {
                        "baseline": {"mean_ms": 10.5},
                        "candidate": {"mean_ms": 9.2},
                    }
                }
            },
        }
        result = EvaluationResult(report=report)
        assert result.report["config"]["nested"]["deep"]["value"] == 42
        assert result.report["monitors"]["latency"]["summary"]["baseline"]["mean_ms"] == 10.5


class TestLLMHarnessTypes:
    """Test that LLM harness types work correctly."""

    def test_executor_config_accepts_json_value(self):
        """ExecutorConfig should accept Dict[str, JSONValue]."""
        config: ExecutorConfig = {
            "provider": "openai",
            "model": "gpt-3.5-turbo",
            "api_key": "sk-test",
            "max_tokens": 512,
            "temperature": 0.0,
            "seed": 42,
            "nested_config": {"custom": "value"},
        }
        assert config["provider"] == "openai"
        assert config["model"] == "gpt-3.5-turbo"
        assert isinstance(config["nested_config"], dict)

    def test_evaluation_report_accepts_valid_dict(self):
        """EvaluationReport TypedDict should accept valid report structure."""
        report: EvaluationReport = {
            "task": "llm_eval",
            "n": 50,
            "seed": 123,
            "config": {"timeout_s": 5.0},
            "baseline": {"passes": 45, "total": 50, "pass_rate": 0.9},
            "candidate": {"passes": 48, "total": 50, "pass_rate": 0.96},
            "delta_pass_rate": 0.06,
            "delta_ci": [0.02, 0.10],
            "decision": {"adopt": True, "reason": "improvement"},
            "monitors": {},
            "llm_metrics": {
                "baseline": {"total_cost_usd": 0.05},
                "candidate": {"total_cost_usd": 0.06},
            },
        }
        assert report["task"] == "llm_eval"
        assert report["delta_pass_rate"] == 0.06
        assert report["llm_metrics"] is not None


class TestJSONValueCompatibility:
    """Test that JSONValue types work with actual JSON data."""

    def test_json_value_accepts_primitives(self):
        """JSONValue should accept all JSON primitive types."""
        values: list[JSONValue] = [
            "string",
            42,
            3.14,
            True,
            False,
            None,
        ]
        for value in values:
            assert isinstance(value, (str, int, float, bool, type(None)))

    def test_json_value_accepts_nested_structures(self):
        """JSONValue should accept nested dicts and lists."""
        nested: JSONDict = {
            "string": "value",
            "number": 42,
            "float": 3.14,
            "bool": True,
            "null": None,
            "list": [1, 2, 3, "four"],
            "nested_dict": {
                "deep": {
                    "value": 100,
                    "list": [{"item": 1}, {"item": 2}],
                }
            },
        }
        assert isinstance(nested, dict)
        assert nested["nested_dict"]["deep"]["value"] == 100
        assert isinstance(nested["list"], list)

    def test_json_dict_compatible_with_mapping(self):
        """JSONDict should be compatible with Mapping[str, JSONValue]."""
        data: JSONDict = {"key": "value", "number": 42}
        mapping: Mapping[str, JSONValue] = data
        assert mapping["key"] == "value"
        assert mapping["number"] == 42


class TestRuntimeCompatibility:
    """Test that type annotations don't break runtime behavior."""

    def test_evaluation_config_creation_runtime(self):
        """EvaluationConfig should work at runtime with new types."""
        config = EvaluationConfig(
            n=200,
            seed=999,
            policy_config={"name": "test", "gating": {"min_delta": 0.02}},
            extra_options={"custom": "value", "number": 42},
        )
        # Verify it works
        assert config.n == 200
        assert config.seed == 999
        assert config.policy_config is not None
        assert config.extra_options["custom"] == "value"

    def test_evaluation_result_properties_runtime(self):
        """EvaluationResult properties should work at runtime."""
        report: JSONDict = {
            "decision": {"adopt": False, "reason": "insufficient_improvement"},
            "baseline": {"pass_rate": 0.95},
            "candidate": {"pass_rate": 0.96},
        }
        result = EvaluationResult(report=report)
        assert result.adopt is False
        assert result.reason == "insufficient_improvement"

    def test_type_annotations_are_optional_at_runtime(self):
        """Type annotations should not be required at runtime."""
        # This should work without explicit type annotations
        config = EvaluationConfig()
        assert config.n == 400  # default value

        # Should accept dict literals without type hints
        config2 = EvaluationConfig(
            policy_config={"name": "test"},
            extra_options={"key": "value"},
        )
        assert config2.policy_config["name"] == "test"
        assert config2.extra_options["key"] == "value"

