"""
Prompt mutation system for testing LLM robustness.
"""

from typing import Any, Callable, Dict, Optional

__all__ = ["Mutant", "PromptMutant"]


class Mutant:
    """Base class for input mutation strategies."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}

    def transform(self, input_data: Any, **kwargs: Any) -> Any:
        """
        Transform the input data.

        Args:
            input_data: The input to transform
            **kwargs: Additional context (e.g., rng for randomness)

        Returns:
            Transformed input
        """
        raise NotImplementedError

    def name(self) -> str:
        """Return the name of this mutant."""
        return self.__class__.__name__


class PromptMutant(Mutant):
    """Base class for prompt-specific mutations."""

    def transform(self, prompt: str, **kwargs: Any) -> str:
        """
        Transform a prompt string.

        Args:
            prompt: The prompt to transform
            **kwargs: Additional context (rng, intensity, etc.)

        Returns:
            Transformed prompt
        """
        raise NotImplementedError

