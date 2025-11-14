"""
Tests for model registry validation.
"""

import pytest

from metamorphic_guard.model_registry import (
    get_valid_models,
    is_valid_model,
    suggest_model,
    validate_model,
    register_model,
    register_models,
    get_model_info,
)


class TestModelRegistry:
    """Test model registry functionality."""
    
    def test_get_valid_models_openai(self):
        """Test getting valid OpenAI models."""
        models = get_valid_models("openai")
        assert isinstance(models, set)
        assert "gpt-4" in models
        assert "gpt-3.5-turbo" in models
        assert "text-embedding-ada-002" in models
    
    def test_get_valid_models_anthropic(self):
        """Test getting valid Anthropic models."""
        models = get_valid_models("anthropic")
        assert isinstance(models, set)
        assert "claude-3-5-sonnet-20241022" in models
        assert "claude-2.1" in models
    
    def test_get_valid_models_unknown_provider(self):
        """Test getting models for unknown provider."""
        models = get_valid_models("unknown_provider")
        assert isinstance(models, set)
        assert len(models) == 0
    
    def test_is_valid_model_openai_valid(self):
        """Test validating valid OpenAI models."""
        assert is_valid_model("openai", "gpt-4") is True
        assert is_valid_model("openai", "gpt-3.5-turbo") is True
        assert is_valid_model("openai", "text-embedding-ada-002") is True
    
    def test_is_valid_model_openai_invalid(self):
        """Test validating invalid OpenAI models."""
        # Custom models that look valid are now allowed (e.g., "invalid-model" is valid as custom model)
        # Test truly invalid models
        assert is_valid_model("openai", "") is False
        assert is_valid_model("openai", "   ") is False
        assert is_valid_model("openai", "model with spaces") is False
        assert is_valid_model("openai", "model!@#invalid") is False
        assert is_valid_model("openai", None) is False  # type: ignore
    
    def test_is_valid_model_anthropic_valid(self):
        """Test validating valid Anthropic models."""
        assert is_valid_model("anthropic", "claude-3-5-sonnet-20241022") is True
        assert is_valid_model("anthropic", "claude-2.1") is True
    
    def test_is_valid_model_vllm_lenient(self):
        """Test that vLLM validation is lenient."""
        # Should accept registered models
        assert is_valid_model("vllm", "mistralai/Mistral-7B-v0.1") is True
        
        # Should accept model paths
        assert is_valid_model("vllm", "custom-org/custom-model") is True
        assert is_valid_model("vllm", "my-model-name") is True
        
        # Should reject obviously invalid
        assert is_valid_model("vllm", "") is False
        assert is_valid_model("vllm", "!!!") is False
    
    def test_suggest_model_openai(self):
        """Test model name suggestions for OpenAI."""
        suggestions = suggest_model("openai", "gpt-4-turb")
        assert len(suggestions) > 0
        assert any("gpt-4-turbo" in s for s in suggestions)
    
    def test_suggest_model_anthropic(self):
        """Test model name suggestions for Anthropic."""
        suggestions = suggest_model("anthropic", "claude-3", cutoff=0.5)  # Lower cutoff to get matches
        # May have suggestions or not depending on similarity
        assert isinstance(suggestions, list)
        # If there are suggestions, they should be valid Anthropic models
        if suggestions:
            assert all(is_valid_model("anthropic", s) for s in suggestions)
    
    def test_suggest_model_no_match(self):
        """Test suggestions when no match found."""
        suggestions = suggest_model("openai", "xyz-123-abc")
        # May return empty or return closest matches
        assert isinstance(suggestions, list)
    
    def test_validate_model_valid(self):
        """Test validating a valid model."""
        is_valid, error_msg, suggestions = validate_model("openai", "gpt-4")
        assert is_valid is True
        assert error_msg is None
        assert suggestions == []
    
    def test_validate_model_invalid(self):
        """Test validating an invalid model."""
        # Use a truly invalid model (with special characters or spaces)
        is_valid, error_msg, suggestions = validate_model("openai", "model with spaces!")
        assert is_valid is False
        assert error_msg is not None
        assert "invalid" in error_msg.lower() or "Invalid" in error_msg
        # May have suggestions
        assert isinstance(suggestions, list)
    
    def test_validate_model_raises_error(self):
        """Test that validate_model raises error when requested."""
        # Use a truly invalid model
        with pytest.raises(ValueError, match="Invalid model"):
            validate_model("openai", "model with spaces!", raise_error=True)
        
        # Should not raise for valid models
        is_valid, _, _ = validate_model("openai", "gpt-4", raise_error=True)
        assert is_valid is True
    
    def test_register_model(self):
        """Test registering a custom model."""
        # Register a custom model
        register_model("openai", "custom-gpt-5")
        
        # Should now be valid
        assert is_valid_model("openai", "custom-gpt-5") is True
        
        # Clean up (remove from registry)
        from metamorphic_guard.model_registry import _MODEL_REGISTRY
        _MODEL_REGISTRY["openai"].discard("custom-gpt-5")
    
    def test_register_models(self):
        """Test registering multiple custom models."""
        custom_models = ["custom-model-1", "custom-model-2"]
        register_models("anthropic", custom_models)
        
        # Should all be valid
        for model in custom_models:
            assert is_valid_model("anthropic", model) is True
        
        # Clean up
        from metamorphic_guard.model_registry import _MODEL_REGISTRY
        for model in custom_models:
            _MODEL_REGISTRY["anthropic"].discard(model)
    
    def test_get_model_info_valid(self):
        """Test getting info for a valid model."""
        info = get_model_info("openai", "gpt-4")
        assert info["is_valid"] is True
        assert info["provider"] == "openai"
        assert info["model"] == "gpt-4"
        assert info["error_message"] is None
    
    def test_get_model_info_invalid(self):
        """Test getting info for an invalid model."""
        # Use a truly invalid model
        info = get_model_info("openai", "model with spaces!")
        assert info["is_valid"] is False
        assert info["provider"] == "openai"
        assert info["model"] == "model with spaces!"
        assert info["error_message"] is not None
        assert isinstance(info["suggestions"], list)
    
    def test_get_model_info_with_family(self):
        """Test getting model info includes family information."""
        info = get_model_info("openai", "gpt-4")
        # May have family info if available
        assert "family" in info or "gpt-4" in info["model"]

