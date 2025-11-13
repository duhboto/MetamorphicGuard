"""
LLM-as-Judge implementation for evaluating outputs using LLMs.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

from .__init__ import LLMJudge
from ..executors import LLMExecutor
from ..plugins import executor_plugins


class LLMAsJudge(LLMJudge):
    """
    Judge that uses an LLM to evaluate outputs against criteria.
    
    This judge uses an LLM executor to call a judge model (e.g., GPT-4) to evaluate
    candidate outputs. Supports rubric-based evaluation with structured scoring.
    """

    PLUGIN_METADATA = {
        "name": "LLM-as-Judge",
        "description": "Use LLM to evaluate outputs against rubric or criteria",
        "version": "1.0.0",
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config)
        cfg = config or {}
        
        # Judge model configuration
        self.judge_model = cfg.get("judge_model", "gpt-4")
        self.judge_provider = cfg.get("judge_provider", "openai")
        self.temperature = float(cfg.get("temperature", 0.0))  # Low temperature for consistency
        self.max_tokens = int(cfg.get("max_tokens", 512))
        
        # Rubric configuration
        rubric_raw = cfg.get("rubric")
        if isinstance(rubric_raw, str):
            try:
                self.rubric = json.loads(rubric_raw)
            except json.JSONDecodeError:
                self.rubric = {}
        elif isinstance(rubric_raw, dict):
            self.rubric = rubric_raw
        else:
            # Default rubric
            self.rubric = {
                "criteria": [
                    {"name": "completeness", "weight": 0.3, "description": "Addresses all aspects of the prompt"},
                    {"name": "accuracy", "weight": 0.4, "description": "Factually correct and reliable"},
                    {"name": "clarity", "weight": 0.3, "description": "Clear, understandable, and well-structured"},
                ],
                "threshold": 0.7,
            }
        
        # Initialize executor for judge LLM
        executor_config = cfg.get("executor_config", {})
        executor_config.setdefault("model", self.judge_model)
        executor_config.setdefault("temperature", self.temperature)
        executor_config.setdefault("max_tokens", self.max_tokens)
        
        # Get executor plugin
        executor_name = cfg.get("executor", self.judge_provider)
        executor_registry = executor_plugins()
        executor_def = executor_registry.get(executor_name)
        
        if executor_def is None:
            raise ValueError(
                f"Judge executor '{executor_name}' not found. "
                f"Available: {list(executor_registry.keys())}"
            )
        
        executor_factory = executor_def.factory
        # Merge API key if provided
        if cfg.get("api_key"):
            executor_config["api_key"] = cfg["api_key"]
        self.executor: LLMExecutor = executor_factory(config=executor_config)
        
        # Cost tracking
        self._total_cost = 0.0
        self._total_tokens = 0
        self._evaluation_count = 0

    def evaluate(
        self,
        output: str,
        input_data: Any,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Evaluate an output using LLM-as-judge.
        
        Args:
            output: The candidate output to evaluate
            input_data: The original input/prompt
            **kwargs: Additional context (expected_format, reference_output, etc.)
        
        Returns:
            {
                "pass": bool,
                "score": float (0.0-1.0),
                "reason": str,
                "details": Dict[str, Any],
                "judge_metadata": {
                    "cost_usd": float,
                    "tokens": int,
                    "model": str,
                }
            }
        """
        start_time = time.time()
        self._evaluation_count += 1
        
        # Build evaluation prompt
        evaluation_prompt = self._build_evaluation_prompt(output, input_data, **kwargs)
        system_prompt = self._build_system_prompt()
        
        # Call judge LLM
        try:
            result = self.executor._call_llm(
                prompt=evaluation_prompt,
                system_prompt=system_prompt,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            
            judge_response = result.get("content", "")
            tokens = result.get("tokens_total", 0)
            cost = result.get("cost_usd", 0.0)
            
            self._total_tokens += tokens
            self._total_cost += cost
            
            # Parse judge response
            parsed = self._parse_judge_response(judge_response)
            
            duration_ms = (time.time() - start_time) * 1000
            
            return {
                "pass": parsed["pass"],
                "score": parsed["score"],
                "reason": parsed["reason"],
                "details": {
                    **parsed.get("details", {}),
                    "rubric": self.rubric,
                    "judge_response": judge_response,
                },
                "judge_metadata": {
                    "cost_usd": cost,
                    "tokens": tokens,
                    "model": self.judge_model,
                    "duration_ms": duration_ms,
                },
            }
        except Exception as exc:
            # If judge LLM call fails, return a conservative evaluation
            return {
                "pass": False,
                "score": 0.0,
                "reason": f"Judge evaluation failed: {exc}",
                "details": {
                    "error": str(exc),
                    "rubric": self.rubric,
                },
                "judge_metadata": {
                    "cost_usd": 0.0,
                    "tokens": 0,
                    "model": self.judge_model,
                    "error": str(exc),
                },
            }

    def _build_system_prompt(self) -> str:
        """Build the system prompt for the judge LLM."""
        criteria = self.rubric.get("criteria", [])
        threshold = self.rubric.get("threshold", 0.7)
        
        criteria_text = "\n".join(
            f"- {c.get('name', 'unknown')} (weight: {c.get('weight', 1.0)}): {c.get('description', '')}"
            for c in criteria
        )
        
        return f"""You are an expert evaluator. Your task is to evaluate outputs against the following criteria:

{criteria_text}

Evaluation threshold: {threshold}

Provide your evaluation as a JSON object with the following structure:
{{
    "scores": {{
        "criterion_name": <score 0.0-1.0>
    }},
    "final_score": <weighted average 0.0-1.0>,
    "pass": <true if final_score >= threshold, else false>,
    "reason": "<brief explanation>",
    "details": {{
        "strengths": ["<strength 1>", ...],
        "weaknesses": ["<weakness 1>", ...]
    }}
}}

Be objective, fair, and consistent in your evaluations."""

    def _build_evaluation_prompt(
        self,
        output: str,
        input_data: Any,
        **kwargs: Any,
    ) -> str:
        """Build the evaluation prompt for the judge LLM."""
        prompt_parts = []
        
        # Original input/prompt
        if input_data:
            if isinstance(input_data, str):
                prompt_parts.append(f"Original Prompt:\n{input_data}\n")
            else:
                prompt_parts.append(f"Original Input:\n{json.dumps(input_data, indent=2)}\n")
        
        # Expected format (if provided)
        expected_format = kwargs.get("expected_format")
        if expected_format:
            prompt_parts.append(f"Expected Format:\n{expected_format}\n")
        
        # Reference output (if provided for comparison)
        reference_output = kwargs.get("reference_output")
        if reference_output:
            prompt_parts.append(f"Reference Output (for comparison):\n{reference_output}\n")
        
        # Candidate output to evaluate
        prompt_parts.append(f"Candidate Output to Evaluate:\n{output}\n")
        
        prompt_parts.append(
            "Please evaluate the candidate output against the criteria provided in the system prompt. "
            "Return your evaluation as a JSON object."
        )
        
        return "\n".join(prompt_parts)

    def _parse_judge_response(self, response: str) -> Dict[str, Any]:
        """Parse the judge LLM's response into structured evaluation."""
        # Try to extract JSON from response
        response = response.strip()
        
        # Look for JSON block
        json_start = response.find("{")
        json_end = response.rfind("}") + 1
        
        if json_start >= 0 and json_end > json_start:
            json_str = response[json_start:json_end]
            try:
                parsed = json.loads(json_str)
                
                # Extract scores
                scores = parsed.get("scores", {})
                final_score = float(parsed.get("final_score", 0.0))
                pass_flag = bool(parsed.get("pass", final_score >= self.rubric.get("threshold", 0.7)))
                reason = parsed.get("reason", f"Score: {final_score:.2f}")
                details = parsed.get("details", {})
                
                return {
                    "pass": pass_flag,
                    "score": max(0.0, min(1.0, final_score)),
                    "reason": reason,
                    "details": {
                        "scores": scores,
                        "final_score": final_score,
                        **details,
                    },
                }
            except (json.JSONDecodeError, ValueError, TypeError):
                pass
        
        # Fallback: try to extract score from text
        # Look for score patterns like "score: 0.8" or "0.8/1.0"
        import re
        score_patterns = [
            r"score[:\s]+([0-9.]+)",
            r"([0-9.]+)\s*/\s*1\.0",
            r"([0-9.]+)\s*out\s*of\s*1",
        ]
        
        for pattern in score_patterns:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                try:
                    score = float(match.group(1))
                    score = max(0.0, min(1.0, score))
                    threshold = self.rubric.get("threshold", 0.7)
                    return {
                        "pass": score >= threshold,
                        "score": score,
                        "reason": f"Extracted score: {score:.2f} (threshold: {threshold})",
                        "details": {
                            "raw_response": response,
                            "extraction_method": "pattern_match",
                        },
                    }
                except (ValueError, TypeError):
                    continue
        
        # Last resort: conservative default
        return {
            "pass": False,
            "score": 0.0,
            "reason": "Could not parse judge response",
            "details": {
                "raw_response": response,
                "extraction_method": "fallback",
            },
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about judge usage (cost, tokens, evaluations)."""
        return {
            "total_evaluations": self._evaluation_count,
            "total_cost_usd": self._total_cost,
            "total_tokens": self._total_tokens,
            "average_cost_per_evaluation": (
                self._total_cost / self._evaluation_count if self._evaluation_count > 0 else 0.0
            ),
            "judge_model": self.judge_model,
        }

    def reset_statistics(self) -> None:
        """Reset cost and token tracking."""
        self._total_cost = 0.0
        self._total_tokens = 0
        self._evaluation_count = 0

