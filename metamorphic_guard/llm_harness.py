"""
LLM Harness for easy integration of LLM evaluation with Metamorphic Guard.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .harness import run_eval
from .judges import Judge, LLMJudge
from .mutants import Mutant, PromptMutant


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
        executor_config: Optional[Dict[str, Any]] = None,
        max_tokens: int = 512,
        temperature: float = 0.0,
        seed: Optional[int] = None,
        baseline_model: Optional[str] = None,
        baseline_provider: Optional[str] = None,
        baseline_executor_config: Optional[Dict[str, Any]] = None,
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
        case: Dict[str, Any] | List[str] | str,
        props: Optional[Sequence[Judge | LLMJudge]] = None,
        mrs: Optional[Sequence[Mutant | PromptMutant]] = None,
        n: int = 100,
        seed: int = 42,
        bootstrap: bool = True,
        baseline_model: Optional[str] = None,
        baseline_system: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Run evaluation of LLM on test cases.

        Args:
            case: Can be:
                - Dict with "system" and "user" keys
                - List of user prompts (strings)
                - Single user prompt (string)
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
        from .llm_specs import create_llm_spec, simple_llm_inputs
        from .specs import Spec

        # Parse case input
        if isinstance(case, str):
            prompts = [case]
            candidate_system = None
        elif isinstance(case, list):
            prompts = case
            candidate_system = None
        elif isinstance(case, dict):
            prompts = [case.get("user", "")]
            candidate_system = case.get("system")
        else:
            raise ValueError(f"Invalid case type: {type(case)}")

        candidate_system_prompt = candidate_system
        baseline_model = baseline_model or self.model
        baseline_system_prompt = baseline_system if baseline_system is not None else candidate_system_prompt

        # Create input generator (system prompts are supplied via executor configs)
        gen_inputs_fn = simple_llm_inputs(prompts)

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
                result = self._aggregate_llm_metrics(result)
        finally:
            # Clean up temporary task
            if task_name in _TASK_REGISTRY:
                del _TASK_REGISTRY[task_name]

        return result
    
    def _aggregate_llm_metrics(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Aggregate cost and latency metrics from evaluation results.
        
        Extracts token usage, costs, and latency from individual test results
        and adds summary statistics to the report.
        """
        llm_metrics = result.get("llm_metrics")
        if llm_metrics:
            baseline = llm_metrics.get("baseline", {})
            candidate = llm_metrics.get("candidate", {})
            if "cost_delta_usd" not in llm_metrics:
                llm_metrics["cost_delta_usd"] = candidate.get("total_cost_usd", 0.0) - baseline.get("total_cost_usd", 0.0)
            if "cost_ratio" not in llm_metrics:
                baseline_cost = baseline.get("total_cost_usd", 0.0)
                candidate_cost = candidate.get("total_cost_usd", 0.0)
                llm_metrics["cost_ratio"] = (
                    candidate_cost / baseline_cost if baseline_cost else None
                )
            if "tokens_delta" not in llm_metrics:
                llm_metrics["tokens_delta"] = candidate.get("total_tokens", 0) - baseline.get("total_tokens", 0)
            if "retry_delta" not in llm_metrics:
                llm_metrics["retry_delta"] = candidate.get("retry_total", 0) - baseline.get("retry_total", 0)
            result["llm_metrics"] = llm_metrics
            return result

        # Fallback: compute minimal metrics from monitors if harness skipped aggregation
        baseline_metrics = {"total_cost_usd": 0.0, "total_tokens": 0}
        candidate_metrics = {"total_cost_usd": 0.0, "total_tokens": 0}
        for monitor_data in result.get("monitors", {}).values():
            summary = monitor_data.get("summary", {})
            baseline_metrics.update(summary.get("baseline", {}))
            candidate_metrics.update(summary.get("candidate", {}))

        result["llm_metrics"] = {
            "baseline": baseline_metrics,
            "candidate": candidate_metrics,
            "cost_delta_usd": candidate_metrics.get("total_cost_usd", 0.0)
            - baseline_metrics.get("total_cost_usd", 0.0),
        }
        return result

