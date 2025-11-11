"""
Anthropic API executor for LLM calls.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from .__init__ import LLMExecutor

try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore


class AnthropicExecutor(LLMExecutor):
    """Executor that calls Anthropic API."""

    PLUGIN_METADATA = {
        "name": "Anthropic Executor",
        "description": "Execute LLM calls via Anthropic API",
        "version": "1.0.0",
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config)
        if anthropic is None:
            raise ImportError(
                "Anthropic executor requires 'anthropic' package. Install with: pip install anthropic"
            )

        self.api_key = config.get("api_key") if config else None
        if not self.api_key:
            import os

            self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("Anthropic API key required (config['api_key'] or ANTHROPIC_API_KEY env var)")

        self.client = anthropic.Anthropic(api_key=self.api_key)
        # Pricing per 1M tokens (as of 2024, update as needed)
        self.pricing = {
            "claude-3-5-sonnet-20241022": {"prompt": 3.0, "completion": 15.0},
            "claude-3-opus-20240229": {"prompt": 15.0, "completion": 75.0},
            "claude-3-sonnet-20240229": {"prompt": 3.0, "completion": 15.0},
            "claude-3-haiku-20240307": {"prompt": 0.25, "completion": 1.25},
        }

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

        For LLM executors:
        - file_path: system prompt (or path to prompt template)
        - func_name: model name (overrides config)
        - args: (user_prompt,) or (user_prompt, system_prompt)
        """
        start_time = time.time()
        model = func_name if func_name else self.model
        user_prompt = args[0] if args else ""
        system_prompt = args[1] if len(args) > 1 else (file_path if file_path else None)

        try:
            result = self._call_llm(
                prompt=user_prompt,
                system_prompt=system_prompt,
                model=model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                timeout=timeout_s,
            )
            duration_ms = (time.time() - start_time) * 1000

            return {
                "success": True,
                "duration_ms": duration_ms,
                "stdout": result.get("content", ""),
                "stderr": "",
                "result": result.get("content"),
                "tokens_prompt": result.get("tokens_prompt", 0),
                "tokens_completion": result.get("tokens_completion", 0),
                "tokens_total": result.get("tokens_total", 0),
                "cost_usd": result.get("cost_usd", 0.0),
                "finish_reason": result.get("finish_reason", "end_turn"),
            }
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return {
                "success": False,
                "duration_ms": duration_ms,
                "stdout": "",
                "stderr": str(e),
                "error": str(e),
                "error_type": type(e).__name__,
                "error_code": "llm_api_error",
            }

    def _call_llm(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Make an Anthropic API call."""
        model = model or self.model
        max_tokens = max_tokens or self.max_tokens
        temperature = temperature if temperature is not None else self.temperature

        kwargs: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        # Anthropic doesn't support seed, but we can set temperature to 0 for determinism
        if self.seed is not None and temperature == 0.0:
            # Temperature 0 should be deterministic
            pass

        response = self.client.messages.create(**kwargs, timeout=timeout)

        content = ""
        if response.content:
            # Anthropic returns content as a list of text blocks
            content = "".join(
                block.text for block in response.content if hasattr(block, "text") and block.type == "text"
            )

        # Calculate tokens and cost
        tokens_prompt = response.usage.input_tokens if response.usage else 0
        tokens_completion = response.usage.output_tokens if response.usage else 0
        tokens_total = tokens_prompt + tokens_completion

        # Get pricing for model (fallback to claude-3-haiku if unknown)
        model_pricing = self.pricing.get(
            model, self.pricing.get("claude-3-haiku-20240307", {"prompt": 0.25, "completion": 1.25})
        )
        cost_usd = (tokens_prompt / 1_000_000 * model_pricing["prompt"]) + (
            tokens_completion / 1_000_000 * model_pricing["completion"]
        )

        finish_reason = response.stop_reason or "end_turn"

        return {
            "content": content,
            "tokens_prompt": tokens_prompt,
            "tokens_completion": tokens_completion,
            "tokens_total": tokens_total,
            "cost_usd": cost_usd,
            "finish_reason": finish_reason,
        }

