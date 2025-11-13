"""
Cost estimation for LLM evaluations before running them.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .executors import LLMExecutor
from .judges import LLMJudge
from .mutants import PromptMutant
from .plugins import executor_plugins, judge_plugins


def estimate_llm_cost(
    executor_name: str,
    executor_config: Dict[str, Any],
    n: int,
    system_prompt: Optional[str] = None,
    user_prompts: Optional[List[str]] = None,
    max_tokens: int = 512,
    mutants: Optional[Sequence[PromptMutant]] = None,
    judges: Optional[Sequence[LLMJudge]] = None,
) -> Dict[str, Any]:
    """
    Estimate the cost of running an LLM evaluation before executing it.
    
    Args:
        executor_name: Name of the executor plugin (e.g., "openai", "anthropic")
        executor_config: Executor configuration including model, pricing, etc.
        n: Number of test cases
        system_prompt: System prompt text (optional)
        user_prompts: List of user prompt templates (optional)
        max_tokens: Maximum tokens per response
        mutants: List of prompt mutants (multiplies test cases)
        judges: List of judges (may include LLM-as-judge which adds cost)
    
    Returns:
        Dictionary with cost estimates:
        {
            "baseline_cost_usd": float,
            "candidate_cost_usd": float,
            "judge_cost_usd": float,
            "total_cost_usd": float,
            "estimated_tokens": {
                "baseline": {"prompt": int, "completion": int, "total": int},
                "candidate": {"prompt": int, "completion": int, "total": int},
                "judge": {"prompt": int, "completion": int, "total": int},
            },
            "test_cases": {
                "baseline": int,
                "candidate": int,
                "judge": int,
            },
            "breakdown": {
                "baseline_calls": int,
                "candidate_calls": int,
                "judge_calls": int,
            }
        }
    """
    # Get executor to access pricing
    executor_registry = executor_plugins()
    executor_def = executor_registry.get(executor_name)
    if executor_def is None:
        raise ValueError(f"Executor '{executor_name}' not found")
    
    executor_factory = executor_def.factory
    executor: LLMExecutor = executor_factory(config=executor_config)
    
    # Estimate prompt tokens
    system_tokens = _estimate_tokens(system_prompt or "")
    user_prompts = user_prompts or [""]
    avg_user_tokens = sum(_estimate_tokens(p) for p in user_prompts) / max(1, len(user_prompts))
    
    # Account for mutants (each mutant creates additional test cases)
    mutant_multiplier = len(mutants) if mutants else 1
    total_test_cases = n * mutant_multiplier
    
    # Estimate tokens per call
    prompt_tokens_per_call = system_tokens + avg_user_tokens
    completion_tokens_per_call = max_tokens  # Assume max tokens used
    
    # Get pricing
    model = executor_config.get("model", executor.model)
    pricing = _get_pricing(executor, model)
    
    # Calculate baseline and candidate costs (same for now, but could differ)
    baseline_calls = total_test_cases
    candidate_calls = total_test_cases
    
    baseline_cost = _calculate_cost(
        baseline_calls,
        prompt_tokens_per_call,
        completion_tokens_per_call,
        pricing,
    )
    candidate_cost = _calculate_cost(
        candidate_calls,
        prompt_tokens_per_call,
        completion_tokens_per_call,
        pricing,
    )
    
    # Estimate judge costs (if LLM-as-judge is used)
    judge_cost = 0.0
    judge_tokens = {"prompt": 0, "completion": 0, "total": 0}
    judge_calls = 0
    
    if judges:
        for judge in judges:
            if isinstance(judge, LLMJudge):
                # Check if it's an LLM-as-judge
                judge_name = judge.name()
                if "LLMAsJudge" in judge_name or "llm_as_judge" in judge_name.lower():
                    # Estimate judge call cost
                    judge_config = getattr(judge, "config", {})
                    judge_executor_name = judge_config.get("executor", "openai")
                    judge_model = judge_config.get("judge_model", "gpt-4")
                    judge_max_tokens = judge_config.get("max_tokens", 512)
                    
                    # Get judge executor pricing
                    judge_executor_registry = executor_plugins()
                    judge_executor_def = judge_executor_registry.get(judge_executor_name)
                    if judge_executor_def:
                        judge_executor_factory = judge_executor_def.factory
                        judge_executor_config = judge_config.get("executor_config", {})
                        judge_executor_config.setdefault("model", judge_model)
                        judge_executor: LLMExecutor = judge_executor_factory(config=judge_executor_config)
                        judge_pricing = _get_pricing(judge_executor, judge_model)
                        
                        # Judge prompt includes original output + evaluation prompt
                        judge_prompt_tokens = completion_tokens_per_call + 200  # Evaluation prompt overhead
                        judge_completion_tokens = judge_max_tokens
                        judge_calls = total_test_cases * len(judges)  # Each judge evaluates each output
                        
                        judge_cost = _calculate_cost(
                            judge_calls,
                            judge_prompt_tokens,
                            judge_completion_tokens,
                            judge_pricing,
                        )
                        judge_tokens = {
                            "prompt": judge_prompt_tokens * judge_calls,
                            "completion": judge_completion_tokens * judge_calls,
                            "total": (judge_prompt_tokens + judge_completion_tokens) * judge_calls,
                        }
                        break  # Only count first LLM-as-judge
    
    total_cost = baseline_cost + candidate_cost + judge_cost
    
    return {
        "baseline_cost_usd": baseline_cost,
        "candidate_cost_usd": candidate_cost,
        "judge_cost_usd": judge_cost,
        "total_cost_usd": total_cost,
        "estimated_tokens": {
            "baseline": {
                "prompt": int(prompt_tokens_per_call * baseline_calls),
                "completion": int(completion_tokens_per_call * baseline_calls),
                "total": int((prompt_tokens_per_call + completion_tokens_per_call) * baseline_calls),
            },
            "candidate": {
                "prompt": int(prompt_tokens_per_call * candidate_calls),
                "completion": int(completion_tokens_per_call * candidate_calls),
                "total": int((prompt_tokens_per_call + completion_tokens_per_call) * candidate_calls),
            },
            "judge": judge_tokens,
        },
        "test_cases": {
            "baseline": baseline_calls,
            "candidate": candidate_calls,
            "judge": judge_calls,
        },
        "breakdown": {
            "baseline_calls": baseline_calls,
            "candidate_calls": candidate_calls,
            "judge_calls": judge_calls,
            "mutant_multiplier": mutant_multiplier,
            "num_judges": len(judges) if judges else 0,
        },
    }


def _estimate_tokens(text: str) -> int:
    """Rough token estimation: ~4 characters per token."""
    if not text:
        return 0
    return int(len(text) / 4)


def _get_pricing(executor: LLMExecutor, model: str) -> Dict[str, float]:
    """Get pricing information from executor."""
    if hasattr(executor, "pricing"):
        pricing_dict = executor.pricing
        if isinstance(pricing_dict, dict):
            # Check if pricing is per 1K tokens (OpenAI) or per 1M tokens (Anthropic)
            # OpenAI: {"prompt": 0.03, "completion": 0.06} per 1K
            # Anthropic: {"prompt": 3.0, "completion": 15.0} per 1M
            model_pricing = pricing_dict.get(model, {})
            if isinstance(model_pricing, dict) and "prompt" in model_pricing:
                # Determine if per 1K or 1M based on typical values
                prompt_price = model_pricing["prompt"]
                if prompt_price > 1.0:
                    # Likely per 1M tokens (Anthropic style)
                    return {
                        "prompt": prompt_price / 1000.0,  # Convert to per 1K
                        "completion": model_pricing.get("completion", 0.0) / 1000.0,
                    }
                else:
                    # Likely per 1K tokens (OpenAI style)
                    return {
                        "prompt": prompt_price,
                        "completion": model_pricing.get("completion", 0.0),
                    }
    
    # Default fallback pricing (OpenAI gpt-3.5-turbo)
    return {"prompt": 0.0015, "completion": 0.002}


def _calculate_cost(
    num_calls: int,
    prompt_tokens_per_call: int,
    completion_tokens_per_call: int,
    pricing: Dict[str, float],
) -> float:
    """Calculate total cost for given number of calls."""
    total_prompt_tokens = prompt_tokens_per_call * num_calls
    total_completion_tokens = completion_tokens_per_call * num_calls
    
    prompt_cost = (total_prompt_tokens / 1000.0) * pricing["prompt"]
    completion_cost = (total_completion_tokens / 1000.0) * pricing["completion"]
    
    return prompt_cost + completion_cost

