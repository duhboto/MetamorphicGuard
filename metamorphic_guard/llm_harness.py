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
            self.executor = provider

    def run(
        self,
        case: Dict[str, Any],
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
            case: Test case with "system" and "user" keys (or prompt template)
            props: List of judges to evaluate outputs
            mrs: List of mutants to apply to inputs
            n: Number of test cases
            seed: Random seed
            bootstrap: Whether to compute bootstrap confidence intervals
            **kwargs: Additional arguments passed to run_eval

        Returns:
            Evaluation report dictionary
        """
        # For now, this is a placeholder that shows the intended API
        # Full implementation would:
        # 1. Create a task spec that uses LLM executor
        # 2. Apply mutants to generate test cases
        # 3. Run evaluation with judges as properties
        # 4. Return structured report

        # This is a simplified version - full implementation would integrate
        # with the existing run_eval infrastructure
        raise NotImplementedError(
            "LLMHarness.run() is not yet fully implemented. "
            "Use run_eval directly with executor='openai' for now."
        )

