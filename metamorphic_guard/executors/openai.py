"""
OpenAI API executor for LLM calls.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional
from pathlib import Path

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
        default_pricing = {
            "gpt-4": {"prompt": 0.03, "completion": 0.06},
            "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
            "gpt-3.5-turbo": {"prompt": 0.0015, "completion": 0.002},
        }
        cfg_pricing = (config or {}).get("pricing")
        if isinstance(cfg_pricing, dict):
            merged = {**default_pricing}
            for model_name, model_prices in cfg_pricing.items():
                if isinstance(model_prices, dict):
                    base = merged.get(model_name, {})
                    base_prompt = model_prices.get("prompt", base.get("prompt"))
                    base_completion = model_prices.get("completion", base.get("completion"))
                    merged[model_name] = {
                        "prompt": float(base_prompt) if base_prompt is not None else base.get("prompt", 0.0),
                        "completion": float(base_completion) if base_completion is not None else base.get("completion", 0.0),
                    }
            self.pricing = merged
        else:
            self.pricing = default_pricing
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

        def _validation_error(message: str, code: str) -> Dict[str, Any]:
            payload = {
                "success": False,
                "duration_ms": 0.0,
                "stdout": "",
                "stderr": message,
                "error": message,
                "error_type": "ValidationError",
                "error_code": code,
            }
            return self._attach_retry_metadata(payload, attempts=0)

        # Validate inputs and extract conversation history, user prompt, and system prompt
        # Support multiple formats:
        # 1. (conversation_history, user_prompt) - multi-turn with history
        # 2. (user_prompt,) - single turn
        # 3. (user_prompt, system_prompt) - single turn with explicit system prompt
        
        conversation_history: Optional[List[Dict[str, str]]] = None
        user_prompt: str = ""
        system_prompt: Optional[str] = None
        
        if not args:
            return _validation_error("Empty or invalid arguments", "invalid_input")
        
        # Check if first arg is conversation history (list of message dicts)
        if len(args) >= 2 and isinstance(args[0], list):
            # Format: (conversation_history, user_prompt)
            conversation_history = args[0]
            user_prompt = args[1] if len(args) > 1 else ""
            # System prompt from history or config
            if conversation_history and isinstance(conversation_history[0], dict):
                first_msg = conversation_history[0]
                if first_msg.get("role") == "system":
                    system_prompt = first_msg.get("content", "")
        else:
            # Single turn: (user_prompt,) or (user_prompt, system_prompt)
            user_prompt = args[0] if args else ""
            if len(args) > 1 and isinstance(args[1], str) and args[1].strip():
                system_prompt = args[1]
        
        # Validate user prompt
        if not isinstance(user_prompt, str) or not user_prompt.strip():
            return _validation_error("Empty or invalid user prompt", "invalid_input")
        
        # Get system prompt from config if not provided
        if not system_prompt:
            if isinstance(self.system_prompt, str) and self.system_prompt.strip():
                system_prompt = self.system_prompt
            elif isinstance(self.config.get("system_prompt"), str) and self.config["system_prompt"].strip():
                system_prompt = self.config["system_prompt"]
            elif file_path:
                try:
                    path_obj = Path(file_path)
                    if path_obj.exists():
                        system_prompt = path_obj.read_text(encoding="utf-8")
                    else:
                        system_prompt = file_path
                except Exception:
                    system_prompt = file_path

        # Validate model name (basic check)
        if not model or not isinstance(model, str):
            return _validation_error(f"Invalid model name: {model}", "invalid_model")

        # Validate temperature range (OpenAI: 0-2)
        if self.temperature < 0 or self.temperature > 2:
            return _validation_error(
                f"Temperature must be between 0 and 2, got {self.temperature}",
                "invalid_parameter",
            )

        # Validate max_tokens (OpenAI supports up to 128K for some models, but we'll be conservative)
        # Note: Actual limits vary by model - GPT-4 supports up to 128K, GPT-3.5-turbo supports 16K
        if self.max_tokens <= 0 or self.max_tokens > 128000:
            return _validation_error(
                f"max_tokens must be between 1 and 128000, got {self.max_tokens}",
                "invalid_parameter",
            )

        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                result = self._call_llm(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    conversation_history=conversation_history,
                    model=model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    seed=self.seed,
                    timeout=timeout_s,
                )
                duration_ms = (time.time() - start_time) * 1000
                # Build full messages list for trace recording
                full_messages = []
                if system_prompt:
                    full_messages.append({"role": "system", "content": system_prompt})
                if conversation_history:
                    for msg in conversation_history:
                        if isinstance(msg, dict) and msg.get("role") in ("user", "assistant"):
                            full_messages.append(msg)
                full_messages.append({"role": "user", "content": user_prompt})
                
                payload = {
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
                    "conversation_history": full_messages,  # Include for trace recording
                }
                return self._attach_retry_metadata(payload, attempts=attempt)
            except Exception as exc:
                last_error = exc
                if self._should_retry(exc, attempt):
                    self._sleep_with_backoff(attempt)
                    continue

                duration_ms = (time.time() - start_time) * 1000
                error_msg = self._redactor.redact(str(exc))
                error_code = "llm_api_error"
                error_type = type(exc).__name__
                if hasattr(exc, "status_code"):
                    if exc.status_code == 401:
                        error_code = "authentication_error"
                    elif exc.status_code == 429:
                        error_code = "rate_limit_error"
                    elif exc.status_code == 400:
                        error_code = "invalid_request"
                    elif exc.status_code == 500:
                        error_code = "api_server_error"

                payload = {
                    "success": False,
                    "duration_ms": duration_ms,
                    "stdout": "",
                    "stderr": error_msg,
                    "error": error_msg,
                    "error_type": error_type,
                    "error_code": error_code,
                }
                return self._attach_retry_metadata(payload, attempts=attempt)

        # Should never reach here, but keep defensive fallback
        duration_ms = (time.time() - start_time) * 1000
        description = self._redactor.redact(str(last_error)) if last_error else "Unknown error"
        payload = {
            "success": False,
            "duration_ms": duration_ms,
            "stdout": "",
            "stderr": description,
            "error": description,
            "error_type": type(last_error).__name__ if last_error else "RuntimeError",
            "error_code": "llm_api_error",
        }
        return self._attach_retry_metadata(payload, attempts=self.max_retries)

    def _call_llm(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        seed: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Make an OpenAI API call with optional conversation history."""
        model = model or self.model
        max_tokens = max_tokens or self.max_tokens
        temperature = temperature if temperature is not None else self.temperature

        messages = []
        
        # Add system prompt (only if not already in history)
        if system_prompt:
            # Check if history already has a system message
            has_system = False
            if conversation_history:
                has_system = any(msg.get("role") == "system" for msg in conversation_history if isinstance(msg, dict))
            if not has_system:
                messages.append({"role": "system", "content": system_prompt})
        
        # Add conversation history (excluding system message if we already added it)
        if conversation_history:
            for msg in conversation_history:
                if isinstance(msg, dict) and msg.get("role") == "system":
                    # Skip system messages from history if we have a separate system_prompt
                    if not system_prompt:
                        messages.append(msg)
                elif isinstance(msg, dict) and msg.get("role") in ("user", "assistant"):
                    messages.append(msg)
        
        # Add new user message
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

