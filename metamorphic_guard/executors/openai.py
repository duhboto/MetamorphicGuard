"""
OpenAI API executor for LLM calls.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from .__init__ import LLMExecutor
from ..redaction import get_redactor

try:
    import openai
except ImportError:
    openai = None  # type: ignore


class OpenAIExecutor(LLMExecutor):
    """Executor that calls OpenAI API."""

    PLUGIN_METADATA = {
        "name": "OpenAI Executor",
        "description": "Execute LLM calls via OpenAI API",
        "version": "1.0.0",
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config)
        if openai is None:
            raise ImportError(
                "OpenAI executor requires 'openai' package. Install with: pip install openai"
            )

        self.api_key = config.get("api_key") if config else None
        if not self.api_key:
            import os

            self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key required (config['api_key'] or OPENAI_API_KEY env var)")

        self.client = openai.OpenAI(api_key=self.api_key)
        # Pricing per 1K tokens (approximate, as of 2024 - verify current rates)
        self.pricing = {
            "gpt-4": {"prompt": 0.03, "completion": 0.06},
            "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
            "gpt-3.5-turbo": {"prompt": 0.0015, "completion": 0.002},
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
        
        # Validate model name (basic check)
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
        
        # Validate temperature range (OpenAI: 0-2)
        if self.temperature < 0 or self.temperature > 2:
            return {
                "success": False,
                "duration_ms": 0.0,
                "stdout": "",
                "stderr": f"Temperature must be between 0 and 2, got {self.temperature}",
                "error": f"Temperature must be between 0 and 2, got {self.temperature}",
                "error_type": "ValidationError",
                "error_code": "invalid_parameter",
            }
        
        # Validate max_tokens (OpenAI supports up to 128K for some models, but we'll be conservative)
        # Note: Actual limits vary by model - GPT-4 supports up to 128K, GPT-3.5-turbo supports 16K
        if self.max_tokens <= 0 or self.max_tokens > 128000:
            return {
                "success": False,
                "duration_ms": 0.0,
                "stdout": "",
                "stderr": f"max_tokens must be between 1 and 128000, got {self.max_tokens}",
                "error": f"max_tokens must be between 1 and 128000, got {self.max_tokens}",
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
                seed=self.seed,
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
                "finish_reason": result.get("finish_reason", "stop"),
            }
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            error_msg = str(e)
            # Redact potential API keys from error messages
            redacted_error = self._redactor.redact(error_msg)
            
            # Determine specific error code
            error_code = "llm_api_error"
            error_type = type(e).__name__
            
            # Handle specific OpenAI API errors
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
        seed: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Make an OpenAI API call."""
        model = model or self.model
        max_tokens = max_tokens or self.max_tokens
        temperature = temperature if temperature is not None else self.temperature

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if seed is not None:
            kwargs["seed"] = seed

        response = self.client.chat.completions.create(**kwargs, timeout=timeout)

        # Handle empty or malformed responses
        if not response.choices or len(response.choices) == 0:
            raise ValueError("API returned empty choices list")
        
        choice = response.choices[0]
        content = choice.message.content or ""

        # Calculate tokens and cost (handle missing usage data)
        if response.usage:
            tokens_prompt = response.usage.prompt_tokens or 0
            tokens_completion = response.usage.completion_tokens or 0
            tokens_total = response.usage.total_tokens or 0
        else:
            tokens_prompt = tokens_completion = tokens_total = 0

        # Get pricing for model (fallback to gpt-3.5-turbo if unknown)
        model_pricing = self.pricing.get(model, self.pricing.get("gpt-3.5-turbo", {"prompt": 0.0015, "completion": 0.002}))
        cost_usd = (tokens_prompt / 1000 * model_pricing["prompt"]) + (
            tokens_completion / 1000 * model_pricing["completion"]
        )

        return {
            "content": content,
            "tokens_prompt": tokens_prompt,
            "tokens_completion": tokens_completion,
            "tokens_total": tokens_total,
            "cost_usd": cost_usd,
            "finish_reason": choice.finish_reason or "stop",
        }

