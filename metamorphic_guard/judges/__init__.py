"""
Judge system for evaluating LLM outputs.
"""

from typing import Any, Dict, Optional

__all__ = ["Judge", "LLMJudge"]


class Judge:
    """Base class for output evaluation judges."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}

    def evaluate(
        self,
        output: Any,
        input_data: Any,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Evaluate an output against criteria.

        Returns:
            {
                "pass": bool,
                "score": float (0.0-1.0),
                "reason": str,
                "details": Dict[str, Any],
            }
        """
        raise NotImplementedError

    def name(self) -> str:
        """Return the name of this judge."""
        return self.__class__.__name__


class LLMJudge(Judge):
    """Base class for LLM output evaluation."""

    def evaluate(
        self,
        output: str,
        input_data: Any,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Evaluate an LLM output string.

        Args:
            output: The LLM output text
            input_data: The original input/prompt
            **kwargs: Additional context (expected format, rubric, etc.)

        Returns:
            {
                "pass": bool,
                "score": float (0.0-1.0),
                "reason": str,
                "details": Dict[str, Any],
            }
        """
        raise NotImplementedError

