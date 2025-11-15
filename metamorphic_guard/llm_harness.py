"""
LLM Harness for easy integration of LLM evaluation with Metamorphic Guard.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Union, TypedDict

from .harness import run_eval
from .judges import Judge, LLMJudge
from .mutants import Mutant, PromptMutant
from .types import JSONDict, JSONValue


# Type definitions for LLM evaluation
LLMCaseInput = Union[Dict[str, str], List[str], str]
"""Type for LLM case input: dict with system/user, list of prompts, or single prompt string."""


# ExecutorConfig: Use Dict[str, JSONValue] for runtime flexibility
# TypedDict doesn't work well for mutable dicts that are updated at runtime
ExecutorConfig = Dict[str, JSONValue]
"""Type for executor configuration dictionaries. Allows provider-specific fields."""


class EvaluationReport(TypedDict, total=False):
    """Type for evaluation report dictionaries returned by run_eval."""

    task: str
    n: int
    seed: int
    config: JSONDict
    baseline: JSONDict
    candidate: JSONDict
    delta_pass_rate: float
    delta_ci: List[float]
    decision: JSONDict
    monitors: JSONDict
    llm_metrics: Optional[JSONDict]
    # Note: TypedDict with total=False allows additional keys beyond those defined


class LLMHarness:
    """
    High-level wrapper for evaluating LLM models with Metamorphic Guard.

    Example:
        from metamorphic_guard.llm_harness import LLMHarness
        from metamorphic_guard.judges.builtin import LengthJudge
        from metamorphic_guard.mutants.builtin import ParaphraseMutant

        h = LLMHarness(
            model="gpt-3.5-turbo",
            provider="openai",
            executor_config={"api_key": "sk-..."}
        )

        case = {"system": "You are a helpful assistant", "user": "Summarize AI safety"}
        props = [LengthJudge(max_chars=300)]
        mrs = [ParaphraseMutant()]

        report = h.run(case, props=props, mrs=mrs, n=100)
    """

    def __init__(
        self,
        model: str = "gpt-3.5-turbo",
        provider: str = "openai",
        executor_config: Optional[ExecutorConfig] = None,
        max_tokens: int = 512,
        temperature: float = 0.0,
        seed: Optional[int] = None,
        baseline_model: Optional[str] = None,
        baseline_provider: Optional[str] = None,
        baseline_executor_config: Optional[ExecutorConfig] = None,
    ) -> None:
        """
        Initialize LLM harness.

        Args:
            model: Model identifier (e.g., "gpt-3.5-turbo", "gpt-4")
            provider: Provider name ("openai", "anthropic", "vllm")
            executor_config: Executor-specific configuration for candidate
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0 for deterministic)
            seed: Random seed for reproducibility
            baseline_model: Optional model identifier for baseline (defaults to candidate model)
            baseline_provider: Optional provider for baseline (defaults to candidate provider)
            baseline_executor_config: Optional executor config for baseline (defaults to candidate config)
        """
        self.model = model
        self.provider = provider
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.seed = seed
        self.baseline_model = baseline_model
        self.baseline_provider = baseline_provider

        # Build executor config for candidate
        self.executor_config = executor_config or {}
        self.executor_config.update(
            {
                "provider": provider,
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "seed": seed,
            }
        )

        # Build executor config for baseline
        self.baseline_executor_config = baseline_executor_config or {}
        if baseline_executor_config is None:
            # Start with candidate config and override
            self.baseline_executor_config = dict(self.executor_config)
        else:
            self.baseline_executor_config = dict(baseline_executor_config)
        
        baseline_prov = baseline_provider or provider
        baseline_mod = baseline_model or model
        self.baseline_executor_config.update(
            {
                "provider": baseline_prov,
                "model": baseline_mod,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "seed": seed,
            }
        )

        # Determine executor name based on provider
        if provider == "openai":
            self.executor = "openai"
        elif provider == "anthropic":
            self.executor = "anthropic"
        elif provider == "vllm":
            self.executor = "vllm"
        elif provider.startswith("local:"):
            self.executor = "vllm"
            self.executor_config["model_path"] = provider.split(":", 1)[1]
        else:
            # Try to use provider name directly as executor
            self.executor = provider

        # Determine baseline executor name
        if baseline_prov == "openai":
            self.baseline_executor = "openai"
        elif baseline_prov == "anthropic":
            self.baseline_executor = "anthropic"
        elif baseline_prov == "vllm":
            self.baseline_executor = "vllm"
        elif baseline_prov and baseline_prov.startswith("local:"):
            self.baseline_executor = "vllm"
            self.baseline_executor_config["model_path"] = baseline_prov.split(":", 1)[1]
        else:
            self.baseline_executor = baseline_prov or self.executor

    def run(
        self,
        case: LLMCaseInput,
        props: Optional[Sequence[Judge | LLMJudge]] = None,
        mrs: Optional[Sequence[Mutant | PromptMutant]] = None,
        n: int = 100,
        seed: int = 42,
        bootstrap: bool = True,
        baseline_model: Optional[str] = None,
        baseline_system: Optional[str] = None,
        **kwargs: JSONValue,
    ) -> EvaluationReport:
        """
        Run evaluation of LLM on test cases.

        Args:
            case: Can be:
                - Dict with:
                  - "system" and "user" keys (single turn)
                  - "conversation" key (list of message dicts for multi-turn)
                  - "conversation" and "user" keys (multi-turn with new user message)
                - List of user prompts (strings) - single turn
                - Single user prompt (string) - single turn
            props: List of judges to evaluate outputs
            mrs: List of mutants to apply to inputs
            n: Number of test cases
            seed: Random seed
            bootstrap: Whether to compute bootstrap confidence intervals
            baseline_model: Optional model name for baseline (defaults to candidate model)
            baseline_system: Optional system prompt for baseline (defaults to candidate system)
            **kwargs: Additional arguments passed to run_eval

        Returns:
            Evaluation report dictionary
        """
        from .llm_specs import create_llm_spec, simple_llm_inputs, multi_turn_llm_inputs
        from .specs import Spec

        # Parse case input - support multi-turn conversations
        is_multi_turn = False
        conversation_history: Optional[List[Dict[str, str]]] = None
        
        if isinstance(case, str):
            prompts = [case]
            candidate_system = None
        elif isinstance(case, list):
            # Could be list of prompts or list of message dicts
            if case and isinstance(case[0], dict) and "role" in case[0]:
                # Multi-turn: list of message dicts
                is_multi_turn = True
                conversation_history = case  # type: ignore[assignment]
                prompts = None  # Will extract user prompts from history
            else:
                # Single turn: list of user prompts
                prompts = case
                candidate_system = None
        elif isinstance(case, dict):
            # Check for multi-turn format
            if "conversation" in case:
                is_multi_turn = True
                conv = case.get("conversation", [])
                conversation_history = conv if isinstance(conv, list) else []  # type: ignore[assignment]
                if "user" in case:
                    # New user message to append
                    user_msg = case.get("user", "")
                    prompts = [user_msg] if isinstance(user_msg, str) else []
                else:
                    # Use last user message from history
                    prompts = None
                candidate_system = case.get("system")
            else:
                # Single turn: system + user
                user_msg = case.get("user", "")
                prompts = [user_msg] if isinstance(user_msg, str) else []
                candidate_system = case.get("system")
        else:
            raise ValueError(f"Invalid case type: {type(case)}")

        candidate_system_prompt = candidate_system
        baseline_model = baseline_model or self.model
        baseline_system_prompt = baseline_system if baseline_system is not None else candidate_system_prompt

        # Create input generator (support multi-turn if conversation history provided)
        if is_multi_turn and conversation_history:
            gen_inputs_fn = multi_turn_llm_inputs(conversation_history, prompts, candidate_system_prompt)
        else:
            gen_inputs_fn = simple_llm_inputs(prompts or [""], candidate_system_prompt)

        # Create task spec
        spec = create_llm_spec(
            gen_inputs=gen_inputs_fn,
            judges=list(props) if props else None,
            mutants=list(mrs) if mrs else None,
        )

        # Register task temporarily with unique name
        import uuid
        task_name = f"llm_eval_{uuid.uuid4().hex[:8]}"
        from .specs import _TASK_REGISTRY

        def get_spec() -> Spec:
            return spec

        _TASK_REGISTRY[task_name] = get_spec

        # For LLM evaluation, we need to create temporary "baseline" and "candidate" files
        # that represent the system prompts. The executor will use file_path as system prompt
        # and func_name as model name.
        import tempfile
        from pathlib import Path

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                
                # Create baseline and candidate "files" (just system prompts)
                baseline_file = tmp_path / "baseline.txt"
                candidate_file = tmp_path / "candidate.txt"
                
                baseline_file.write_text(baseline_system_prompt or "", encoding="utf-8")
                candidate_file.write_text(candidate_system_prompt or "", encoding="utf-8")

                # Create separate executor configs for baseline and candidate
                baseline_config = dict(self.baseline_executor_config)
                if baseline_model:
                    baseline_config["model"] = baseline_model
                if baseline_system_prompt is not None:
                    baseline_config["system_prompt"] = baseline_system_prompt

                candidate_config = dict(self.executor_config)
                candidate_config["model"] = self.model
                if candidate_system_prompt is not None:
                    candidate_config["system_prompt"] = candidate_system_prompt

                baseline_executor_name = self.baseline_executor
                candidate_executor_name = self.executor
                primary_executor_name = candidate_executor_name or baseline_executor_name

                # Run evaluation
                result = run_eval(
                    task_name=task_name,
                    baseline_path=str(baseline_file),
                    candidate_path=str(candidate_file),
                    n=n,
                    seed=seed,
                    executor=primary_executor_name,
                    baseline_executor=baseline_executor_name,
                    candidate_executor=candidate_executor_name,
                    baseline_executor_config=baseline_config,
                    candidate_executor_config=candidate_config,
                    bootstrap_samples=1000 if bootstrap else 0,
                    **kwargs,
                )
                
                # Aggregate cost and latency metrics from results
                # Cast result to EvaluationReport since run_eval returns Dict[str, Any]
                result_dict: JSONDict = result  # type: ignore[assignment]
                result = self._aggregate_llm_metrics(result_dict)  # type: ignore[arg-type]
        finally:
            # Clean up temporary task
            if task_name in _TASK_REGISTRY:
                del _TASK_REGISTRY[task_name]

        return result  # type: ignore[return-value]
    
    def _aggregate_llm_metrics(self, result: JSONDict) -> EvaluationReport:
        """
        Aggregate cost and latency metrics from evaluation results.
        
        Extracts token usage, costs, and latency from individual test results
        and adds summary statistics to the report.
        """
        llm_metrics_raw = result.get("llm_metrics")
        if llm_metrics_raw and isinstance(llm_metrics_raw, dict):
            llm_metrics: JSONDict = llm_metrics_raw
            baseline_raw = llm_metrics.get("baseline", {})
            candidate_raw = llm_metrics.get("candidate", {})
            baseline: JSONDict = baseline_raw if isinstance(baseline_raw, dict) else {}
            candidate: JSONDict = candidate_raw if isinstance(candidate_raw, dict) else {}
            if "cost_delta_usd" not in llm_metrics:
                baseline_cost = baseline.get("total_cost_usd")
                candidate_cost = candidate.get("total_cost_usd")
                baseline_cost_val = baseline_cost if isinstance(baseline_cost, (int, float)) else 0.0
                candidate_cost_val = candidate_cost if isinstance(candidate_cost, (int, float)) else 0.0
                llm_metrics["cost_delta_usd"] = candidate_cost_val - baseline_cost_val
            if "cost_ratio" not in llm_metrics:
                baseline_cost = baseline.get("total_cost_usd")
                candidate_cost = candidate.get("total_cost_usd")
                baseline_cost_val = baseline_cost if isinstance(baseline_cost, (int, float)) else 0.0
                candidate_cost_val = candidate_cost if isinstance(candidate_cost, (int, float)) else 0.0
                llm_metrics["cost_ratio"] = (
                    candidate_cost_val / baseline_cost_val if baseline_cost_val else None
                )
            if "tokens_delta" not in llm_metrics:
                baseline_tokens = baseline.get("total_tokens")
                candidate_tokens = candidate.get("total_tokens")
                baseline_tokens_val = baseline_tokens if isinstance(baseline_tokens, int) else 0
                candidate_tokens_val = candidate_tokens if isinstance(candidate_tokens, int) else 0
                llm_metrics["tokens_delta"] = candidate_tokens_val - baseline_tokens_val
            if "retry_delta" not in llm_metrics:
                baseline_retry = baseline.get("retry_total")
                candidate_retry = candidate.get("retry_total")
                baseline_retry_val = baseline_retry if isinstance(baseline_retry, int) else 0
                candidate_retry_val = candidate_retry if isinstance(candidate_retry, int) else 0
                llm_metrics["retry_delta"] = candidate_retry_val - baseline_retry_val
            result["llm_metrics"] = llm_metrics
            return result  # type: ignore[return-value]

        # Fallback: compute minimal metrics from monitors if harness skipped aggregation
        baseline_metrics: JSONDict = {"total_cost_usd": 0.0, "total_tokens": 0}
        candidate_metrics: JSONDict = {"total_cost_usd": 0.0, "total_tokens": 0}
        monitors_raw = result.get("monitors", {})
        if isinstance(monitors_raw, dict):
            for monitor_data in monitors_raw.values():
                if isinstance(monitor_data, dict):
                    summary_raw = monitor_data.get("summary", {})
                    if isinstance(summary_raw, dict):
                        summary: JSONDict = summary_raw
                        baseline_raw = summary.get("baseline", {})
                        candidate_raw = summary.get("candidate", {})
                        if isinstance(baseline_raw, dict):
                            baseline_metrics.update(baseline_raw)
                        if isinstance(candidate_raw, dict):
                            candidate_metrics.update(candidate_raw)

        result["llm_metrics"] = {
            "baseline": baseline_metrics,
            "candidate": candidate_metrics,
            "cost_delta_usd": (
                (candidate_metrics.get("total_cost_usd") if isinstance(candidate_metrics.get("total_cost_usd"), (int, float)) else 0.0)
                - (baseline_metrics.get("total_cost_usd") if isinstance(baseline_metrics.get("total_cost_usd"), (int, float)) else 0.0)
            ),
        }
        return result  # type: ignore[return-value]

