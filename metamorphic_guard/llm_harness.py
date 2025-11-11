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
    ) -> None:
        """
        Initialize LLM harness.

        Args:
            model: Model identifier (e.g., "gpt-3.5-turbo", "gpt-4")
            provider: Provider name ("openai", "anthropic", "local")
            executor_config: Executor-specific configuration
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0 for deterministic)
            seed: Random seed for reproducibility
        """
        self.model = model
        self.provider = provider
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.seed = seed

        # Build executor config
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

        # Determine executor name based on provider
        if provider == "openai":
            self.executor = "openai"
        elif provider == "anthropic":
            self.executor = "anthropic"
        elif provider.startswith("local:"):
            self.executor = "local_llm"
            self.executor_config["model_path"] = provider.split(":", 1)[1]
        else:
            # Try to use provider name directly as executor
            self.executor = provider

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

        # Use baseline overrides if provided, otherwise use candidate values
        baseline_model = baseline_model or self.model
        baseline_system = baseline_system or candidate_system

        # Create input generator (use candidate system for test inputs)
        gen_inputs_fn = simple_llm_inputs(prompts, candidate_system)

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
                
                baseline_file.write_text(baseline_system or "", encoding="utf-8")
                candidate_file.write_text(candidate_system or "", encoding="utf-8")

                # Create separate executor configs for baseline and candidate
                baseline_config = (self.executor_config or {}).copy()
                baseline_config["model"] = baseline_model
                
                candidate_config = (self.executor_config or {}).copy()
                candidate_config["model"] = self.model

                # Run evaluation
                result = run_eval(
                    task_name=task_name,
                    baseline_path=str(baseline_file),
                    candidate_path=str(candidate_file),
                    n=n,
                    seed=seed,
                    executor=self.executor,
                    executor_config=candidate_config,  # Use candidate config (baseline handled via func_name)
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
        # Extract metrics from baseline and candidate results
        baseline_metrics = {
            "total_cost_usd": 0.0,
            "total_tokens": 0,
            "total_latency_ms": 0.0,
            "avg_latency_ms": 0.0,
            "count": 0,
        }
        candidate_metrics = {
            "total_cost_usd": 0.0,
            "total_tokens": 0,
            "total_latency_ms": 0.0,
            "avg_latency_ms": 0.0,
            "count": 0,
        }
        
        # Aggregate from individual test results if available
        # Note: Individual results may not be in the report, so we check monitors
        if "monitors" in result:
            for monitor_id, monitor_data in result["monitors"].items():
                if monitor_id == "llm_cost":
                    summary = monitor_data.get("summary", {})
                    if "baseline" in summary:
                        baseline_metrics["total_cost_usd"] = summary["baseline"].get("total_cost_usd", 0.0)
                        baseline_metrics["total_tokens"] = summary["baseline"].get("total_tokens", 0)
                    if "candidate" in summary:
                        candidate_metrics["total_cost_usd"] = summary["candidate"].get("total_cost_usd", 0.0)
                        candidate_metrics["total_tokens"] = summary["candidate"].get("total_tokens", 0)
        
        # Add aggregated metrics to result
        if "llm_metrics" not in result:
            result["llm_metrics"] = {}
        
        result["llm_metrics"]["baseline"] = baseline_metrics
        result["llm_metrics"]["candidate"] = candidate_metrics
        result["llm_metrics"]["cost_delta_usd"] = candidate_metrics["total_cost_usd"] - baseline_metrics["total_cost_usd"]
        result["llm_metrics"]["cost_ratio"] = (
            candidate_metrics["total_cost_usd"] / baseline_metrics["total_cost_usd"]
            if baseline_metrics["total_cost_usd"] > 0
            else float("inf")
        )
        
        return result

