"""
Anthropic API executor for LLM calls.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from .__init__ import LLMExecutor
from ..redaction import get_redactor

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
        # Pricing per 1M tokens (approximate, as of 2024 - verify current rates)
        self.pricing = {
            "claude-3-5-sonnet-20241022": {"prompt": 3.0, "completion": 15.0},
            "claude-3-opus-20240229": {"prompt": 15.0, "completion": 75.0},
            "claude-3-sonnet-20240229": {"prompt": 3.0, "completion": 15.0},
            "claude-3-haiku-20240307": {"prompt": 0.25, "completion": 1.25},
        }
        self._redactor = get_redactor(config)

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
        
        # Validate inputs
        user_prompt = args[0] if args else ""
        if not isinstance(user_prompt, str) or not user_prompt.strip():
            return {
                "success": False,
                "duration_ms": 0.0,
                "stdout": "",
                "stderr": "Empty or invalid user prompt",
                "error": "Empty or invalid user prompt",
                "error_type": "ValidationError",
                "error_code": "invalid_input",
            }
        
        system_prompt = args[1] if len(args) > 1 else (file_path if file_path else None)
        
        # Validate model name
        if not model or not isinstance(model, str):
            return {
                "success": False,
                "duration_ms": 0.0,
                "stdout": "",
                "stderr": f"Invalid model name: {model}",
                "error": f"Invalid model name: {model}",
                "error_type": "ValidationError",
                "error_code": "invalid_model",
            }
        
        # Validate temperature range (Anthropic: 0-1)
        if self.temperature < 0 or self.temperature > 1:
            return {
                "success": False,
                "duration_ms": 0.0,
                "stdout": "",
                "stderr": f"Temperature must be between 0 and 1, got {self.temperature}",
                "error": f"Temperature must be between 0 and 1, got {self.temperature}",
                "error_type": "ValidationError",
                "error_code": "invalid_parameter",
            }
        
        # Validate max_tokens (Anthropic: 1-4096)
        if self.max_tokens <= 0 or self.max_tokens > 4096:
            return {
                "success": False,
                "duration_ms": 0.0,
                "stdout": "",
                "stderr": f"max_tokens must be between 1 and 4096, got {self.max_tokens}",
                "error": f"max_tokens must be between 1 and 4096, got {self.max_tokens}",
                "error_type": "ValidationError",
                "error_code": "invalid_parameter",
            }

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
            error_msg = str(e)
            # Redact potential API keys from error messages
            redacted_error = self._redactor.redact(error_msg)
            
            # Determine specific error code
            error_code = "llm_api_error"
            error_type = type(e).__name__
            
            # Handle specific Anthropic API errors
            if hasattr(e, "status_code"):
                if e.status_code == 401:
                    error_code = "authentication_error"
                elif e.status_code == 429:
                    error_code = "rate_limit_error"
                elif e.status_code == 400:
                    error_code = "invalid_request"
                elif e.status_code == 500:
                    error_code = "api_server_error"
            
            return {
                "success": False,
                "duration_ms": duration_ms,
                "stdout": "",
                "stderr": redacted_error,
                "error": redacted_error,
                "error_type": error_type,
                "error_code": error_code,
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

        # Handle empty or malformed responses
        content = ""
        if response.content:
            # Anthropic returns content as a list of text blocks
            text_blocks = [
                block.text for block in response.content 
                if hasattr(block, "text") and hasattr(block, "type") and block.type == "text"
            ]
            content = "".join(text_blocks)

        # Calculate tokens and cost (handle missing usage data)
        if response.usage:
            tokens_prompt = response.usage.input_tokens or 0
            tokens_completion = response.usage.output_tokens or 0
            tokens_total = tokens_prompt + tokens_completion
        else:
            tokens_prompt = tokens_completion = tokens_total = 0

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

