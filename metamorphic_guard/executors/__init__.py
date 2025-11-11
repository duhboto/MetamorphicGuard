"""
Executor plugins for different execution backends (local, docker, LLM, etc.).
"""

from typing import Any, Dict, Optional

__all__ = ["Executor", "LLMExecutor"]


class Executor:
    """Base class for execution backends."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}

    def execute(
        self,
        file_path: str,
        func_name: str,
        args: tuple,
        timeout_s: float = 2.0,
        mem_mb: int = 512,
    ) -> Dict[str, Any]:
        """
        Execute the requested function.

        Returns a dictionary with execution metadata:
        - success: bool
        - duration_ms: float
        - stdout: str
        - stderr: str
        - result: Any (on success)
        - error: str (on failure)
        - error_type: str (optional)
        - error_code: str (optional)
        """
        raise NotImplementedError


class LLMExecutor(Executor):
    """Base class for LLM API executors."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config)
        self.provider = config.get("provider", "openai") if config else "openai"
        self.model = config.get("model", "gpt-3.5-turbo") if config else "gpt-3.5-turbo"
        self.max_tokens = config.get("max_tokens", 512) if config else 512
        self.temperature = config.get("temperature", 0.0) if config else 0.0
        self.seed = config.get("seed") if config else None

    def execute(
        self,
        file_path: str,
        func_name: str,
        args: tuple,
        timeout_s: float = 2.0,
        mem_mb: int = 512,
    ) -> Dict[str, Any]:
        """
        Execute an LLM call.

        For LLM executors, file_path is the prompt template path or prompt string,
        func_name is the model identifier, and args contain the prompt variables.
        """
        raise NotImplementedError

    def _call_llm(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Make an LLM API call and return structured result.

        Returns:
            {
                "content": str,
                "tokens_prompt": int,
                "tokens_completion": int,
                "tokens_total": int,
                "cost_usd": float,
                "finish_reason": str,
            }
        """
        raise NotImplementedError

