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
            **kwargs: Additional arguments passed to run_eval

        Returns:
            Evaluation report dictionary
        """
        from .llm_specs import create_llm_spec, simple_llm_inputs
        from .specs import task

        # Parse case input
        if isinstance(case, str):
            prompts = [case]
            system_prompt = None
        elif isinstance(case, list):
            prompts = case
            system_prompt = None
        elif isinstance(case, dict):
            prompts = [case.get("user", "")]
            system_prompt = case.get("system")
        else:
            raise ValueError(f"Invalid case type: {type(case)}")

        # Create input generator
        gen_inputs_fn = simple_llm_inputs(prompts, system_prompt)

        # Create task spec
        spec = create_llm_spec(
            gen_inputs=gen_inputs_fn,
            judges=list(props) if props else None,
            mutants=list(mrs) if mrs else None,
        )

        # Register task temporarily
        task_name = f"llm_eval_{id(self)}"
        from .specs import _TASK_REGISTRY

        def get_spec() -> Spec:
            return spec

        _TASK_REGISTRY[task_name] = get_spec

        # For LLM evaluation, we need to create temporary "baseline" and "candidate" files
        # that represent the system prompts. The executor will use file_path as system prompt.
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            
            # Create baseline and candidate "files" (just system prompts)
            baseline_file = tmp_path / "baseline.txt"
            candidate_file = tmp_path / "candidate.txt"
            
            # For now, use the same system prompt for both (can be extended)
            baseline_system = system_prompt or ""
            candidate_system = system_prompt or ""
            
            baseline_file.write_text(baseline_system, encoding="utf-8")
            candidate_file.write_text(candidate_system, encoding="utf-8")

            # Run evaluation
            result = run_eval(
                task_name=task_name,
                baseline_path=str(baseline_file),
                candidate_path=str(candidate_file),
                n=n,
                seed=seed,
                executor=self.executor,
                executor_config=self.executor_config,
                bootstrap_samples=1000 if bootstrap else 0,
                **kwargs,
            )

        # Clean up temporary task
        if task_name in _TASK_REGISTRY:
            del _TASK_REGISTRY[task_name]

        return result

