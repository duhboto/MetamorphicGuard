"""
Cost estimation for LLM evaluations before running them.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Sequence

from .executors import LLMExecutor
from .judges import LLMJudge
from .mutants import PromptMutant
from .model_registry import get_pricing as get_registry_pricing
from .plugins import executor_plugins


class BudgetAction(Enum):
    """Action to take when budget threshold is exceeded."""
    
    ALLOW = "allow"  # Allow execution (no action)
    WARN = "warn"  # Warn user but allow execution
    ABORT = "abort"  # Abort execution immediately


class BudgetExceededError(Exception):
    """Raised when estimated cost exceeds hard budget limit."""
    
    def __init__(self, estimated_cost: float, budget_limit: float):
        self.estimated_cost = estimated_cost
        self.budget_limit = budget_limit
        super().__init__(
            f"Estimated cost ${estimated_cost:.4f} exceeds budget limit ${budget_limit:.4f}"
        )


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
    
    # Get model name for accurate token estimation
    model = executor_config.get("model", executor.model)
    
    # Estimate prompt tokens (with model-specific estimation)
    system_tokens = _estimate_tokens(system_prompt or "", model=model)
    user_prompts = user_prompts or [""]
    avg_user_tokens = sum(_estimate_tokens(p, model=model) for p in user_prompts) / max(1, len(user_prompts))
    
    # Account for mutants (each mutant creates additional test cases)
    mutant_multiplier = len(mutants) if mutants else 1
    total_test_cases = n * mutant_multiplier
    
    # Estimate tokens per call
    prompt_tokens_per_call = system_tokens + avg_user_tokens
    completion_tokens_per_call = max_tokens  # Assume max tokens used
    
    # Get pricing (try registry first, fall back to executor)
    model = executor_config.get("model", executor.model)
    pricing = get_registry_pricing(model, unit="1k")
    if pricing is None:
        # Fall back to executor's pricing
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
                        # Estimate judge prompt tokens (output + evaluation instructions)
                        judge_prompt_base = completion_tokens_per_call
                        judge_eval_prompt = "Evaluate the following response according to the criteria:"  # Typical judge prompt
                        judge_eval_tokens = _estimate_tokens(judge_eval_prompt, model=judge_model)
                        judge_prompt_tokens = judge_prompt_base + judge_eval_tokens
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


def _estimate_tokens(text: str, model: Optional[str] = None) -> int:
    """
    Estimate token count for text, with improved accuracy.
    
    Uses tiktoken for OpenAI models if available, otherwise uses
    improved heuristics based on model type.
    
    Args:
        text: Text to estimate tokens for
        model: Optional model name for model-specific estimation
    
    Returns:
        Estimated token count
    """
    if not text:
        return 0
    
    # Try tiktoken for OpenAI models (most accurate)
    if model and ("gpt" in model.lower() or "openai" in model.lower()):
        try:
            import tiktoken
            # Try to get encoding for the model
            try:
                encoding = tiktoken.encoding_for_model(model)
            except KeyError:
                # Fall back to cl100k_base (GPT-3.5/4 encoding)
                encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except ImportError:
            # tiktoken not available, fall through to heuristics
            pass
        except Exception:
            # Any error with tiktoken, fall through to heuristics
            pass
    
    # Improved heuristics based on model type
    if model and ("claude" in model.lower() or "anthropic" in model.lower()):
        # Anthropic models: ~3.5 characters per token (more efficient)
        return int(len(text) / 3.5)
    elif model and ("llama" in model.lower() or "mistral" in model.lower()):
        # LLaMA/Mistral models: ~3.8 characters per token
        return int(len(text) / 3.8)
    else:
        # Default: ~4 characters per token (conservative estimate)
        # Accounts for whitespace, punctuation, and special tokens
        base_estimate = len(text) / 4.0
        # Add overhead for special tokens and formatting (5-10%)
        overhead = base_estimate * 0.08
        return int(base_estimate + overhead)


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


def check_budget(
    estimated_cost: float,
    budget_limit: Optional[float] = None,
    warning_threshold: Optional[float] = None,
    action: BudgetAction = BudgetAction.WARN,
) -> Dict[str, Any]:
    """
    Check if estimated cost exceeds budget limits and take appropriate action.
    
    Args:
        estimated_cost: Estimated total cost in USD
        budget_limit: Hard budget limit (aborts if exceeded)
        warning_threshold: Warning threshold (warns if exceeded)
        action: Action to take when warning_threshold is exceeded
    
    Returns:
        Dictionary with budget check results:
        {
            "within_budget": bool,
            "exceeds_warning": bool,
            "exceeds_limit": bool,
            "action_taken": str,
            "message": str,
        }
    
    Raises:
        BudgetExceededError: If estimated_cost exceeds budget_limit
    """
    result = {
        "within_budget": True,
        "exceeds_warning": False,
        "exceeds_limit": False,
        "action_taken": "none",
        "message": "",
    }
    
    # Check hard limit first (only abort if action is ABORT)
    if budget_limit is not None and estimated_cost > budget_limit:
        result["within_budget"] = False
        result["exceeds_limit"] = True
        if action == BudgetAction.ABORT:
            result["action_taken"] = "abort"
            result["message"] = (
                f"Estimated cost ${estimated_cost:.4f} exceeds hard budget limit "
                f"${budget_limit:.4f}"
            )
            raise BudgetExceededError(estimated_cost, budget_limit)
        elif action == BudgetAction.WARN:
            result["action_taken"] = "warn"
            result["message"] = (
                f"⚠️  Estimated cost ${estimated_cost:.4f} exceeds budget limit "
                f"${budget_limit:.4f} but continuing due to ALLOW action"
            )
        else:  # ALLOW
            result["action_taken"] = "allow"
            result["message"] = (
                f"Estimated cost ${estimated_cost:.4f} exceeds budget limit "
                f"${budget_limit:.4f} but continuing"
            )
    
    # Check warning threshold
    if warning_threshold is not None and estimated_cost > warning_threshold:
        result["exceeds_warning"] = True
        if action == BudgetAction.WARN:
            result["action_taken"] = "warn"
            result["message"] = (
                f"⚠️  WARNING: Estimated cost ${estimated_cost:.4f} exceeds "
                f"warning threshold ${warning_threshold:.4f}"
            )
        elif action == BudgetAction.ABORT:
            result["action_taken"] = "abort"
            result["message"] = (
                f"Estimated cost ${estimated_cost:.4f} exceeds warning threshold "
                f"${warning_threshold:.4f} (abort mode enabled)"
            )
            raise BudgetExceededError(estimated_cost, warning_threshold)
    
    if result["within_budget"] and not result["exceeds_warning"]:
        result["message"] = f"Estimated cost ${estimated_cost:.4f} is within budget"
    
    return result


def estimate_and_check_budget(
    executor_name: str,
    executor_config: Dict[str, Any],
    n: int,
    budget_limit: Optional[float] = None,
    warning_threshold: Optional[float] = None,
    action: BudgetAction = BudgetAction.WARN,
    system_prompt: Optional[str] = None,
    user_prompts: Optional[List[str]] = None,
    max_tokens: int = 512,
    mutants: Optional[Sequence[PromptMutant]] = None,
    judges: Optional[Sequence[LLMJudge]] = None,
) -> Dict[str, Any]:
    """
    Estimate cost and check against budget limits in one call.
    
    Args:
        executor_name: Name of the executor plugin
        executor_config: Executor configuration
        n: Number of test cases
        budget_limit: Hard budget limit (aborts if exceeded)
        warning_threshold: Warning threshold (warns if exceeded)
        action: Action to take when warning_threshold is exceeded
        system_prompt: System prompt text (optional)
        user_prompts: List of user prompt templates (optional)
        max_tokens: Maximum tokens per response
        mutants: List of prompt mutants
        judges: List of judges
    
    Returns:
        Dictionary combining cost estimate and budget check results
    
    Raises:
        BudgetExceededError: If estimated cost exceeds budget_limit
    """
    estimate = estimate_llm_cost(
        executor_name=executor_name,
        executor_config=executor_config,
        n=n,
        system_prompt=system_prompt,
        user_prompts=user_prompts,
        max_tokens=max_tokens,
        mutants=mutants,
        judges=judges,
    )
    
    budget_check = check_budget(
        estimated_cost=estimate["total_cost_usd"],
        budget_limit=budget_limit,
        warning_threshold=warning_threshold,
        action=action,
    )
    
    return {
        **estimate,
        "budget_check": budget_check,
    }

