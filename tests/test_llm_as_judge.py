"""
Tests for LLM-as-Judge functionality.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from metamorphic_guard.judges.llm_as_judge import LLMAsJudge


class TestLLMAsJudge:
    """Test LLM-as-Judge implementation."""

    def test_llm_as_judge_init_default(self):
        """Test LLMAsJudge initialization with defaults."""
        with patch("metamorphic_guard.judges.llm_as_judge.executor_plugins") as mock_plugins:
            mock_executor = MagicMock()
            mock_executor_def = MagicMock()
            mock_executor_def.factory.return_value = mock_executor
            mock_plugins.return_value = {"openai": mock_executor_def}
            
            judge = LLMAsJudge(config={"api_key": "test-key"})
            
            assert judge.judge_model == "gpt-4"
            assert judge.judge_provider == "openai"
            assert judge.temperature == 0.0
            assert judge.max_tokens == 512
            assert "criteria" in judge.rubric
            assert judge._total_cost == 0.0
            assert judge._total_tokens == 0
            assert judge._evaluation_count == 0

    def test_llm_as_judge_init_custom_config(self):
        """Test LLMAsJudge initialization with custom config."""
        with patch("metamorphic_guard.judges.llm_as_judge.executor_plugins") as mock_plugins:
            mock_executor = MagicMock()
            mock_executor_def = MagicMock()
            mock_executor_def.factory.return_value = mock_executor
            mock_plugins.return_value = {"anthropic": mock_executor_def}
            
            custom_rubric = {
                "criteria": [
                    {"name": "quality", "weight": 1.0, "description": "Overall quality"},
                ],
                "threshold": 0.8,
            }
            
            judge = LLMAsJudge(
                config={
                    "judge_model": "claude-3-opus",
                    "judge_provider": "anthropic",
                    "temperature": 0.1,
                    "max_tokens": 1024,
                    "rubric": custom_rubric,
                    "api_key": "test-key",
                }
            )
            
            assert judge.judge_model == "claude-3-opus"
            assert judge.judge_provider == "anthropic"
            assert judge.temperature == 0.1
            assert judge.max_tokens == 1024
            assert judge.rubric == custom_rubric

    def test_llm_as_judge_evaluate_success(self):
        """Test successful evaluation with JSON response."""
        with patch("metamorphic_guard.judges.llm_as_judge.executor_plugins") as mock_plugins:
            mock_executor = MagicMock()
            mock_executor_def = MagicMock()
            mock_executor_def.factory.return_value = mock_executor
            mock_plugins.return_value = {"openai": mock_executor_def}
            
            judge = LLMAsJudge(config={"api_key": "test-key"})
            
            # Mock successful LLM response
            judge_response = {
                "scores": {"completeness": 0.9, "accuracy": 0.8, "clarity": 0.85},
                "final_score": 0.85,
                "pass": True,
                "reason": "High quality output",
                "details": {"strengths": ["Clear", "Complete"], "weaknesses": []},
            }
            
            mock_executor._call_llm.return_value = {
                "content": json.dumps(judge_response),
                "tokens_total": 150,
                "cost_usd": 0.01,
            }
            
            result = judge.evaluate(
                output="This is a test output",
                input_data="Test prompt",
            )
            
            assert result["pass"] is True
            assert result["score"] == 0.85
            assert "reason" in result
            assert "judge_metadata" in result
            assert result["judge_metadata"]["cost_usd"] == 0.01
            assert result["judge_metadata"]["tokens"] == 150
            assert result["judge_metadata"]["model"] == "gpt-4"
            assert judge._total_cost == 0.01
            assert judge._total_tokens == 150
            assert judge._evaluation_count == 1

    def test_llm_as_judge_evaluate_fallback_extraction(self):
        """Test evaluation with fallback score extraction."""
        with patch("metamorphic_guard.judges.llm_as_judge.executor_plugins") as mock_plugins:
            mock_executor = MagicMock()
            mock_executor_def = MagicMock()
            mock_executor_def.factory.return_value = mock_executor
            mock_plugins.return_value = {"openai": mock_executor_def}
            
            judge = LLMAsJudge(config={"api_key": "test-key"})
            
            # Mock response without valid JSON
            mock_executor._call_llm.return_value = {
                "content": "The output quality is good. Score: 0.75 out of 1.0",
                "tokens_total": 100,
                "cost_usd": 0.005,
            }
            
            result = judge.evaluate(
                output="Test output",
                input_data="Test prompt",
            )
            
            assert result["score"] == 0.75
            assert result["pass"] is True  # 0.75 >= 0.7 threshold
            assert "extraction_method" in result["details"]

    def test_llm_as_judge_evaluate_error_handling(self):
        """Test error handling when judge LLM call fails."""
        with patch("metamorphic_guard.judges.llm_as_judge.executor_plugins") as mock_plugins:
            mock_executor = MagicMock()
            mock_executor_def = MagicMock()
            mock_executor_def.factory.return_value = mock_executor
            mock_plugins.return_value = {"openai": mock_executor_def}
            
            judge = LLMAsJudge(config={"api_key": "test-key"})
            
            # Mock executor error
            mock_executor._call_llm.side_effect = Exception("API error")
            
            result = judge.evaluate(
                output="Test output",
                input_data="Test prompt",
            )
            
            assert result["pass"] is False
            assert result["score"] == 0.0
            assert "error" in result["details"]
            assert result["judge_metadata"]["error"] == "API error"

    def test_llm_as_judge_statistics(self):
        """Test statistics tracking."""
        with patch("metamorphic_guard.judges.llm_as_judge.executor_plugins") as mock_plugins:
            mock_executor = MagicMock()
            mock_executor_def = MagicMock()
            mock_executor_def.factory.return_value = mock_executor
            mock_plugins.return_value = {"openai": mock_executor_def}
            
            judge = LLMAsJudge(config={"api_key": "test-key"})
            
            mock_executor._call_llm.return_value = {
                "content": json.dumps({"final_score": 0.8, "pass": True, "reason": "Good"}),
                "tokens_total": 100,
                "cost_usd": 0.01,
            }
            
            # Run multiple evaluations
            judge.evaluate("output1", "input1")
            judge.evaluate("output2", "input2")
            
            stats = judge.get_statistics()
            assert stats["total_evaluations"] == 2
            assert stats["total_cost_usd"] == 0.02
            assert stats["total_tokens"] == 200
            assert stats["average_cost_per_evaluation"] == 0.01
            assert stats["judge_model"] == "gpt-4"
            
            # Reset and verify
            judge.reset_statistics()
            stats = judge.get_statistics()
            assert stats["total_evaluations"] == 0
            assert stats["total_cost_usd"] == 0.0
            assert stats["total_tokens"] == 0

    def test_llm_as_judge_build_prompt(self):
        """Test evaluation prompt building."""
        with patch("metamorphic_guard.judges.llm_as_judge.executor_plugins") as mock_plugins:
            mock_executor = MagicMock()
            mock_executor_def = MagicMock()
            mock_executor_def.factory.return_value = mock_executor
            mock_plugins.return_value = {"openai": mock_executor_def}
            
            judge = LLMAsJudge(config={"api_key": "test-key"})
            
            mock_executor._call_llm.return_value = {
                "content": json.dumps({"final_score": 0.8, "pass": True, "reason": "Good"}),
                "tokens_total": 100,
                "cost_usd": 0.01,
            }
            
            judge.evaluate(
                output="Test output",
                input_data="Test prompt",
                expected_format="JSON",
                reference_output="Reference output",
            )
            
            # Verify executor was called with proper prompt
            assert mock_executor._call_llm.called
            call_args = mock_executor._call_llm.call_args
            prompt = call_args[1]["prompt"]
            
            assert "Test prompt" in prompt
            assert "Test output" in prompt
            assert "JSON" in prompt
            assert "Reference output" in prompt

    def test_llm_as_judge_rubric_from_string(self):
        """Test rubric parsing from JSON string."""
        with patch("metamorphic_guard.judges.llm_as_judge.executor_plugins") as mock_plugins:
            mock_executor = MagicMock()
            mock_executor_def = MagicMock()
            mock_executor_def.factory.return_value = mock_executor
            mock_plugins.return_value = {"openai": mock_executor_def}
            
            rubric_str = json.dumps({
                "criteria": [{"name": "test", "weight": 1.0, "description": "Test criterion"}],
                "threshold": 0.9,
            })
            
            judge = LLMAsJudge(config={"rubric": rubric_str, "api_key": "test-key"})
            
            assert judge.rubric["threshold"] == 0.9
            assert len(judge.rubric["criteria"]) == 1

