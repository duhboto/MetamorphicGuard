"""
vLLM executor for local LLM inference.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .__init__ import LLMExecutor

try:
    from vllm import LLM, SamplingParams
    from vllm.utils import random_uuid
except ImportError:
    LLM = None  # type: ignore
    SamplingParams = None  # type: ignore
    random_uuid = None  # type: ignore


class VLLMExecutor(LLMExecutor):
    """
    Executor that uses vLLM for local LLM inference.
    
    Supports high-throughput local inference with various model families.
    Useful for testing and evaluation without API costs.
    """

    PLUGIN_METADATA = {
        "name": "vLLM Executor",
        "description": "Execute LLM calls via local vLLM inference",
        "version": "1.0.0",
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config)
        if LLM is None:
            raise ImportError(
                "vLLM executor requires 'vllm' package. Install with: pip install vllm"
            )

        cfg = config or {}
        
        # Model configuration
        self.model_path = cfg.get("model_path") or cfg.get("model")
        if not self.model_path:
            raise ValueError("vLLM executor requires 'model_path' or 'model' in config")
        
        # vLLM-specific options
        self.tensor_parallel_size = int(cfg.get("tensor_parallel_size", 1))
        self.gpu_memory_utilization = float(cfg.get("gpu_memory_utilization", 0.9))
        self.max_model_len = cfg.get("max_model_len")
        self.trust_remote_code = bool(cfg.get("trust_remote_code", False))
        self.dtype = cfg.get("dtype", "auto")
        self.enable_prefix_caching = bool(cfg.get("enable_prefix_caching", False))
        
        # Initialize vLLM engine (lazy loading)
        self._llm_engine: Optional[LLM] = None
        self._model_loaded = False
        
        # Batch inference support
        self.batch_size = int(cfg.get("batch_size", 1))
        self.enable_batch = bool(cfg.get("enable_batch", False))

    @property
    def llm_engine(self) -> LLM:
        """Lazy-load the vLLM engine."""
        if self._llm_engine is None:
            kwargs: Dict[str, Any] = {
                "model": self.model_path,
                "tensor_parallel_size": self.tensor_parallel_size,
                "gpu_memory_utilization": self.gpu_memory_utilization,
                "trust_remote_code": self.trust_remote_code,
                "dtype": self.dtype,
            }
            if self.max_model_len is not None:
                kwargs["max_model_len"] = self.max_model_len
            if self.enable_prefix_caching:
                kwargs["enable_prefix_caching"] = self.enable_prefix_caching
            
            self._llm_engine = LLM(**kwargs)
            self._model_loaded = True
        return self._llm_engine

    def execute(
        self,
        file_path: str,
        func_name: str,
        args: tuple,
        timeout_s: float = 2.0,
        mem_mb: int = 512,
    ) -> Dict[str, Any]:
        """
        Execute an LLM call using vLLM.
        
        For vLLM executors:
        - file_path: system prompt (or path to prompt template)
        - func_name: model name override (optional)
        - args: (user_prompt,) or (user_prompt, system_prompt)
        """
        start_time = time.time()
        
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
                system_prompt = file_path

        # Build full prompt from conversation history or single turn
        # vLLM doesn't support separate system/user messages in all models, so we concatenate
        if conversation_history:
            # Build prompt from conversation history
            prompt_parts = []
            for msg in conversation_history:
                if isinstance(msg, dict):
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                    if role == "system" and system_prompt is None:
                        # Use system message if no separate system_prompt
                        prompt_parts.append(f"System: {content}")
                    elif role == "user":
                        prompt_parts.append(f"User: {content}")
                    elif role == "assistant":
                        prompt_parts.append(f"Assistant: {content}")
            prompt_parts.append(f"User: {user_prompt}")
            full_prompt = "\n\n".join(prompt_parts)
        else:
            # Single turn
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{user_prompt}"
            else:
                full_prompt = user_prompt

        # Validate temperature range
        if self.temperature < 0 or self.temperature > 2:
            return _validation_error(
                f"Temperature must be between 0 and 2, got {self.temperature}",
                "invalid_parameter",
            )

        # Validate max_tokens
        if self.max_tokens <= 0:
            return _validation_error(
                f"max_tokens must be positive, got {self.max_tokens}",
                "invalid_parameter",
            )

        try:
            result = self._call_llm(
                prompt=full_prompt,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                seed=self.seed,
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
                "cost_usd": 0.0,  # Local inference has no API cost
                "finish_reason": result.get("finish_reason", "stop"),
            }
            return self._attach_retry_metadata(payload, attempts=0)
        except (RuntimeError, ValueError, OSError) as exc:
            duration_ms = (time.time() - start_time) * 1000
            error_msg = str(exc)
            error_code = "vllm_error"
            error_type = type(exc).__name__
            
            # Map common vLLM errors
            if "CUDA" in error_msg or "GPU" in error_msg:
                error_code = "gpu_error"
            elif "OutOfMemory" in error_msg or "OOM" in error_msg:
                error_code = "out_of_memory"
            elif "model" in error_msg.lower() and "not found" in error_msg.lower():
                error_code = "model_not_found"

            payload = {
                "success": False,
                "duration_ms": duration_ms,
                "stdout": "",
                "stderr": error_msg,
                "error": error_msg,
                "error_type": error_type,
                "error_code": error_code,
            }
            return self._attach_retry_metadata(payload, attempts=0)

    def _call_llm(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        seed: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Make a vLLM inference call."""
        max_tokens = max_tokens or self.max_tokens
        temperature = temperature if temperature is not None else self.temperature

        # Create sampling parameters
        sampling_params = SamplingParams(
            temperature=temperature,
            max_tokens=max_tokens,
            seed=seed,
        )

        # Get engine and generate
        engine = self.llm_engine
        outputs = engine.generate([prompt], sampling_params)

        # Extract results (vLLM returns a list of RequestOutput objects)
        if not outputs or len(outputs) == 0:
            raise ValueError("vLLM returned empty outputs")
        
        output = outputs[0]
        
        # Extract generated text
        if not output.outputs or len(output.outputs) == 0:
            raise ValueError("vLLM output has no generated text")
        
        generated_text = output.outputs[0].text
        finish_reason = output.outputs[0].finish_reason or "stop"

        # Estimate tokens (vLLM doesn't always provide exact counts in all versions)
        # We can approximate based on prompt length and generated text
        # For more accurate counts, we'd need to use the tokenizer
        tokens_prompt = len(prompt.split()) * 1.3  # Rough approximation
        tokens_completion = len(generated_text.split()) * 1.3
        tokens_total = int(tokens_prompt + tokens_completion)

        # Try to get actual token counts if available
        if hasattr(output, "metrics") and hasattr(output.metrics, "num_prompt_tokens"):
            tokens_prompt = output.metrics.num_prompt_tokens
        if hasattr(output, "metrics") and hasattr(output.metrics, "num_generated_tokens"):
            tokens_completion = output.metrics.num_generated_tokens
            tokens_total = tokens_prompt + tokens_completion

        return {
            "content": generated_text,
            "tokens_prompt": int(tokens_prompt),
            "tokens_completion": int(tokens_completion),
            "tokens_total": int(tokens_total),
            "cost_usd": 0.0,  # Local inference
            "finish_reason": finish_reason,
        }

    def generate_batch(
        self,
        prompts: List[str],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        seed: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generate responses for multiple prompts in batch.
        
        This is more efficient than calling execute() multiple times.
        """
        max_tokens = max_tokens or self.max_tokens
        temperature = temperature if temperature is not None else self.temperature

        sampling_params = SamplingParams(
            temperature=temperature,
            max_tokens=max_tokens,
            seed=seed,
        )

        engine = self.llm_engine
        outputs = engine.generate(prompts, sampling_params)

        results = []
        for i, output in enumerate(outputs):
            if not output.outputs or len(output.outputs) == 0:
                results.append({
                    "content": "",
                    "tokens_prompt": 0,
                    "tokens_completion": 0,
                    "tokens_total": 0,
                    "cost_usd": 0.0,
                    "finish_reason": "error",
                    "error": "Empty output",
                })
                continue

            generated_text = output.outputs[0].text
            finish_reason = output.outputs[0].finish_reason or "stop"

            # Estimate tokens
            prompt = prompts[i]
            tokens_prompt = len(prompt.split()) * 1.3
            tokens_completion = len(generated_text.split()) * 1.3
            tokens_total = int(tokens_prompt + tokens_completion)

            # Try to get actual counts if available
            if hasattr(output, "metrics") and hasattr(output.metrics, "num_prompt_tokens"):
                tokens_prompt = output.metrics.num_prompt_tokens
            if hasattr(output, "metrics") and hasattr(output.metrics, "num_generated_tokens"):
                tokens_completion = output.metrics.num_generated_tokens
                tokens_total = tokens_prompt + tokens_completion

            results.append({
                "content": generated_text,
                "tokens_prompt": int(tokens_prompt),
                "tokens_completion": int(tokens_completion),
                "tokens_total": int(tokens_total),
                "cost_usd": 0.0,
                "finish_reason": finish_reason,
            })

        return results

    def unload_model(self) -> None:
        """Unload the model from memory to free GPU resources."""
        if self._llm_engine is not None:
            # vLLM doesn't have explicit unload, but we can delete the reference
            # and let Python GC handle it
            del self._llm_engine
            self._llm_engine = None
            self._model_loaded = False

