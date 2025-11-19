"""
Mock LLM Executor for demonstration purposes.
Allows running LLM evaluations without API keys.
"""

from typing import Any, Dict, List, Optional
import random
import time

from metamorphic_guard.executors import Executor

class MockLLMExecutor(Executor):
    """
    A mock executor that simulates LLM responses.
    It behaves deterministically based on the input prompt to allow reproducible tests.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.config = config or {}
        self.latency_ms = self.config.get("latency_ms", 100)
        self.failure_rate = self.config.get("failure_rate", 0.0)
        self.model_name = self.config.get("model", "mock-gpt-4")

    def execute(
        self,
        file_path: str,
        func_name: str,
        args: tuple,
        timeout_s: float,
        mem_mb: int,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute a mock LLM call.
        """
        return self.run(file_path, func_name, args, timeout_s, mem_mb, **kwargs)

    def run(
        self,
        file_path: str,
        func_name: str,
        args: tuple,
        timeout_s: float = 2.0,
        mem_mb: int = 512,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Alias for execute to support module:callable loading which looks for .run()
        """
        # Simulate latency
        time.sleep(self.latency_ms / 1000.0)
        
        # Simulate random failures
        if random.random() < self.failure_rate:
            return {
                "success": False,
                "error": "Mock random failure",
                "error_code": "random_error",
                "retries": 0
            }

        user_prompt = args[0] if args else ""
        system_prompt = ""
        
        # In LLM harness, file_path often contains the system prompt text if it's a temp file
        try:
            with open(file_path, 'r') as f:
                system_prompt = f.read()
        except Exception:
            pass

        # Generate a deterministic "mock" response
        # If the candidate is "improved", we return better answers for specific keywords
        is_improved = "candidate" in file_path or "candidate" in func_name
        
        response_text = self._generate_response(user_prompt, system_prompt, is_improved)
        
        # Calculate mock token usage
        tokens_in = len(user_prompt.split()) + len(system_prompt.split())
        tokens_out = len(response_text.split())
        
        return {
            "success": True,
            "result": response_text,
            "tokens_prompt": tokens_in,
            "tokens_completion": tokens_out,
            "tokens_total": tokens_in + tokens_out,
            "cost_usd": (tokens_in * 0.00001) + (tokens_out * 0.00003),
            "duration_ms": self.latency_ms,
            "finish_reason": "stop",
            "retries": 0
        }

    def _generate_response(self, user: str, system: str, is_improved: bool) -> str:
        """Generate a mock response based on inputs."""
        user_lower = user.lower()
        
        if "summarize" in user_lower:
            if is_improved:
                return "This is a concise and accurate summary of the provided text. It captures the key points effectively."
            else:
                return "This is a summary. It is kinda long and maybe misses the point a bit. " * 3
        
        if "sentiment" in user_lower:
            return "Positive" if "good" in user_lower else "Negative"
            
        return f"Mock response to: {user}"

