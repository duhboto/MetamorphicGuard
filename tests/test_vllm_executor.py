"""
Tests for vLLM executor.
"""

from unittest.mock import MagicMock, patch

import pytest

from metamorphic_guard.executors.vllm import VLLMExecutor


class TestVLLMExecutor:
    """Test vLLM executor implementation."""

    def test_vllm_executor_init_missing_vllm(self):
        """Test that VLLMExecutor raises ImportError when vllm is not installed."""
        with patch("metamorphic_guard.executors.vllm.LLM", None):
            with pytest.raises(ImportError, match="vllm"):
                VLLMExecutor(config={"model_path": "test-model"})

    def test_vllm_executor_init_missing_model(self):
        """Test that VLLMExecutor requires model_path."""
        with patch("metamorphic_guard.executors.vllm.LLM") as mock_llm_class:
            with pytest.raises(ValueError, match="model_path"):
                VLLMExecutor(config={})

    def test_vllm_executor_init_success(self):
        """Test successful VLLMExecutor initialization."""
        with patch("metamorphic_guard.executors.vllm.LLM") as mock_llm_class:
            mock_llm_instance = MagicMock()
            mock_llm_class.return_value = mock_llm_instance
            
            executor = VLLMExecutor(
                config={
                    "model_path": "meta-llama/Llama-2-7b-chat-hf",
                    "tensor_parallel_size": 2,
                    "gpu_memory_utilization": 0.8,
                    "max_model_len": 4096,
                }
            )
            
            assert executor.model_path == "meta-llama/Llama-2-7b-chat-hf"
            assert executor.tensor_parallel_size == 2
            assert executor.gpu_memory_utilization == 0.8
            assert executor.max_model_len == 4096
            assert executor._llm_engine is None  # Lazy loading

    def test_vllm_executor_lazy_loading(self):
        """Test that vLLM engine is loaded lazily."""
        with patch("metamorphic_guard.executors.vllm.LLM") as mock_llm_class:
            mock_llm_instance = MagicMock()
            mock_llm_class.return_value = mock_llm_instance
            
            executor = VLLMExecutor(config={"model_path": "test-model"})
            
            # Engine not loaded yet
            assert executor._llm_engine is None
            
            # Access property triggers loading
            engine = executor.llm_engine
            assert engine == mock_llm_instance
            mock_llm_class.assert_called_once()

    def test_vllm_executor_execute_success(self):
        """Test successful execution."""
        with patch("metamorphic_guard.executors.vllm.LLM") as mock_llm_class, \
             patch("metamorphic_guard.executors.vllm.SamplingParams") as mock_sampling:
            mock_llm_instance = MagicMock()
            mock_llm_class.return_value = mock_llm_instance
            
            # Mock output
            mock_output = MagicMock()
            mock_output.outputs = [MagicMock()]
            mock_output.outputs[0].text = "Generated response"
            mock_output.outputs[0].finish_reason = "stop"
            mock_output.metrics = MagicMock()
            mock_output.metrics.num_prompt_tokens = 10
            mock_output.metrics.num_generated_tokens = 20
            
            mock_llm_instance.generate.return_value = [mock_output]
            
            executor = VLLMExecutor(config={"model_path": "test-model"})
            executor._llm_engine = mock_llm_instance  # Skip lazy loading
            
            result = executor.execute(
                file_path="",
                func_name="",
                args=("Test prompt",),
            )
            
            assert result["success"] is True
            assert result["stdout"] == "Generated response"
            assert result["tokens_prompt"] == 10
            assert result["tokens_completion"] == 20
            assert result["tokens_total"] == 30
            assert result["cost_usd"] == 0.0  # Local inference
            assert mock_llm_instance.generate.called

    def test_vllm_executor_execute_with_system_prompt(self):
        """Test execution with system prompt."""
        with patch("metamorphic_guard.executors.vllm.LLM") as mock_llm_class, \
             patch("metamorphic_guard.executors.vllm.SamplingParams") as mock_sampling:
            mock_llm_instance = MagicMock()
            mock_llm_class.return_value = mock_llm_instance
            
            mock_output = MagicMock()
            mock_output.outputs = [MagicMock()]
            mock_output.outputs[0].text = "Response"
            mock_output.outputs[0].finish_reason = "stop"
            mock_output.metrics = MagicMock()
            mock_output.metrics.num_prompt_tokens = 5
            mock_output.metrics.num_generated_tokens = 10
            
            mock_llm_instance.generate.return_value = [mock_output]
            
            executor = VLLMExecutor(config={"model_path": "test-model"})
            executor._llm_engine = mock_llm_instance
            
            result = executor.execute(
                file_path="",
                func_name="",
                args=("User prompt", "System prompt"),
            )
            
            assert result["success"] is True
            # Verify prompt was combined
            call_args = mock_llm_instance.generate.call_args
            prompts = call_args[0][0]
            assert "System prompt" in prompts[0]
            assert "User prompt" in prompts[0]

    def test_vllm_executor_execute_validation_error(self):
        """Test validation error handling."""
        with patch("metamorphic_guard.executors.vllm.LLM") as mock_llm_class:
            mock_llm_instance = MagicMock()
            mock_llm_class.return_value = mock_llm_instance
            
            executor = VLLMExecutor(config={"model_path": "test-model"})
            
            # Empty prompt
            result = executor.execute("", "", args=("",))
            assert result["success"] is False
            assert result["error_code"] == "invalid_input"
            
            # Invalid temperature
            executor.temperature = 3.0
            result = executor.execute("", "", args=("Valid prompt",))
            assert result["success"] is False
            assert result["error_code"] == "invalid_parameter"

    def test_vllm_executor_execute_error_handling(self):
        """Test error handling during execution."""
        with patch("metamorphic_guard.executors.vllm.LLM") as mock_llm_class, \
             patch("metamorphic_guard.executors.vllm.SamplingParams") as mock_sampling:
            mock_llm_instance = MagicMock()
            mock_llm_class.return_value = mock_llm_instance
            
            mock_llm_instance.generate.side_effect = RuntimeError("CUDA out of memory")
            
            executor = VLLMExecutor(config={"model_path": "test-model"})
            executor._llm_engine = mock_llm_instance
            
            result = executor.execute("", "", args=("Test prompt",))
            
            assert result["success"] is False
            assert result["error_code"] == "gpu_error"
            assert "CUDA" in result["error"] or "out of memory" in result["error"]

    def test_vllm_executor_generate_batch(self):
        """Test batch generation."""
        with patch("metamorphic_guard.executors.vllm.LLM") as mock_llm_class, \
             patch("metamorphic_guard.executors.vllm.SamplingParams") as mock_sampling:
            mock_llm_instance = MagicMock()
            mock_llm_class.return_value = mock_llm_instance
            
            # Mock multiple outputs
            mock_outputs = []
            for i in range(3):
                mock_output = MagicMock()
                mock_output.outputs = [MagicMock()]
                mock_output.outputs[0].text = f"Response {i}"
                mock_output.outputs[0].finish_reason = "stop"
                mock_output.metrics = MagicMock()
                mock_output.metrics.num_prompt_tokens = 10
                mock_output.metrics.num_generated_tokens = 20
                mock_outputs.append(mock_output)
            
            mock_llm_instance.generate.return_value = mock_outputs
            
            executor = VLLMExecutor(config={"model_path": "test-model"})
            executor._llm_engine = mock_llm_instance
            
            prompts = ["Prompt 1", "Prompt 2", "Prompt 3"]
            results = executor.generate_batch(prompts)
            
            assert len(results) == 3
            assert all(r["content"] == f"Response {i}" for i, r in enumerate(results))
            assert all(r["tokens_total"] == 30 for r in results)
            assert all(r["cost_usd"] == 0.0 for r in results)

    def test_vllm_executor_unload_model(self):
        """Test model unloading."""
        with patch("metamorphic_guard.executors.vllm.LLM") as mock_llm_class:
            mock_llm_instance = MagicMock()
            mock_llm_class.return_value = mock_llm_instance
            
            executor = VLLMExecutor(config={"model_path": "test-model"})
            executor._llm_engine = mock_llm_instance
            executor._model_loaded = True
            
            executor.unload_model()
            
            assert executor._llm_engine is None
            assert executor._model_loaded is False

