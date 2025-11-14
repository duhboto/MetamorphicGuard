"""
Anthropic API executor for LLM calls.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional
from pathlib import Path

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
        default_pricing = {
            "claude-3-5-sonnet-20241022": {"prompt": 3.0, "completion": 15.0},
            "claude-3-opus-20240229": {"prompt": 15.0, "completion": 75.0},
            "claude-3-sonnet-20240229": {"prompt": 3.0, "completion": 15.0},
            "claude-3-haiku-20240307": {"prompt": 0.25, "completion": 1.25},
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

        # Validate model name
        if not model or not isinstance(model, str):
            return _validation_error(f"Invalid model name: {model}", "invalid_model")

        # Validate temperature range (Anthropic: 0-1)
        if self.temperature < 0 or self.temperature > 1:
            return _validation_error(
                f"Temperature must be between 0 and 1, got {self.temperature}",
                "invalid_parameter",
            )

        # Validate max_tokens (Anthropic: 1-4096)
        if self.max_tokens <= 0 or self.max_tokens > 4096:
            return _validation_error(
                f"max_tokens must be between 1 and 4096, got {self.max_tokens}",
                "invalid_parameter",
            )

        for attempt in range(self.max_retries + 1):
            try:
                result = self._call_llm(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    conversation_history=conversation_history,
                    model=model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    timeout=timeout_s,
                )
                duration_ms = (time.time() - start_time) * 1000
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
                    "finish_reason": result.get("finish_reason", "end_turn"),
                }
                return self._attach_retry_metadata(payload, attempts=attempt)
            except Exception as exc:
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

        duration_ms = (time.time() - start_time) * 1000
        fallback = "Unknown error"
        payload = {
            "success": False,
            "duration_ms": duration_ms,
            "stdout": "",
            "stderr": fallback,
            "error": fallback,
            "error_type": "RuntimeError",
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
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Make an Anthropic API call with optional conversation history."""
        model = model or self.model
        max_tokens = max_tokens or self.max_tokens
        temperature = temperature if temperature is not None else self.temperature

        # Build messages list from conversation history + new user message
        messages: List[Dict[str, str]] = []
        
        # Add conversation history
        if conversation_history:
            for msg in conversation_history:
                if isinstance(msg, dict) and msg.get("role") in ("user", "assistant"):
                    # Anthropic uses "user" and "assistant" roles
                    messages.append(msg)
        
        # Add new user message
        messages.append({"role": "user", "content": prompt})

        kwargs: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        
        # System prompt (Anthropic supports separate system parameter)
        final_system_prompt = system_prompt
        if not final_system_prompt and conversation_history:
            # Extract system prompt from history if present
            for msg in conversation_history:
                if isinstance(msg, dict) and msg.get("role") == "system":
                    final_system_prompt = msg.get("content", "")
                    break
        
        if final_system_prompt:
            kwargs["system"] = final_system_prompt

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

