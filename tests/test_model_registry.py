"""
Tests for model registry.
"""

from __future__ import annotations

import pytest

from metamorphic_guard.model_registry import (
    ModelMetadata,
    add_custom_model,
    get_model,
    get_model_info,
    get_pricing,
    initialize_default_registry,
    list_models,
    register_model,
)


class TestModelRegistry:
    """Test model registry functionality."""
    
    def test_register_and_get_model(self):
        """Test registering and retrieving a model."""
        metadata = ModelMetadata(
            name="test-model",
            provider="openai",
            pricing={"prompt": 0.01, "completion": 0.02},
        )
        register_model(metadata)
        
        retrieved = get_model("test-model")
        assert retrieved is not None
        assert retrieved.name == "test-model"
        assert retrieved.provider == "openai"
        assert retrieved.pricing["prompt"] == 0.01
        
        # Clean up
        from metamorphic_guard.model_registry import _MODEL_REGISTRY
        _MODEL_REGISTRY.pop("test-model", None)
    
    def test_get_model_not_found(self):
        """Test getting a non-existent model."""
        model = get_model("non-existent-model")
        assert model is None
    
    def test_list_models(self):
        """Test listing all models."""
        initialize_default_registry()
        models = list_models()
        
        assert len(models) > 0
        assert all(isinstance(m, ModelMetadata) for m in models)
    
    def test_list_models_by_provider(self):
        """Test listing models filtered by provider."""
        initialize_default_registry()
        
        openai_models = list_models(provider="openai")
        assert len(openai_models) > 0
        assert all(m.provider == "openai" for m in openai_models)
        
        anthropic_models = list_models(provider="anthropic")
        assert len(anthropic_models) > 0
        assert all(m.provider == "anthropic" for m in anthropic_models)
    
    def test_get_pricing(self):
        """Test getting model pricing."""
        initialize_default_registry()
        
        pricing = get_pricing("gpt-4")
        assert pricing is not None
        assert "prompt" in pricing
        assert "completion" in pricing
        assert isinstance(pricing["prompt"], (int, float))
        assert isinstance(pricing["completion"], (int, float))
    
    def test_get_pricing_unit_conversion(self):
        """Test pricing unit conversion."""
        initialize_default_registry()
        
        # Get pricing in 1k units
        pricing_1k = get_pricing("gpt-4", unit="1k")
        assert pricing_1k is not None
        
        # Get pricing in 1m units
        pricing_1m = get_pricing("gpt-4", unit="1m")
        assert pricing_1m is not None
        
        # 1m should be 1000x 1k
        assert pricing_1m["prompt"] == pytest.approx(pricing_1k["prompt"] * 1000, rel=0.01)
        assert pricing_1m["completion"] == pytest.approx(pricing_1k["completion"] * 1000, rel=0.01)
    
    def test_get_pricing_not_found(self):
        """Test getting pricing for non-existent model."""
        pricing = get_pricing("non-existent-model")
        assert pricing is None
    
    def test_get_model_info(self):
        """Test getting model info as JSON dict."""
        initialize_default_registry()
        
        info = get_model_info("gpt-4")
        assert info is not None
        assert info["name"] == "gpt-4"
        assert info["provider"] == "openai"
        assert "pricing" in info
        assert "max_tokens" in info
    
    def test_get_model_info_not_found(self):
        """Test getting info for non-existent model."""
        info = get_model_info("non-existent-model")
        assert info is None
    
    def test_add_custom_model(self):
        """Test adding a custom model."""
        add_custom_model(
            name="custom-test-model",
            provider="openai",
            pricing={"prompt": 0.005, "completion": 0.01},
        )
        
        model = get_model("custom-test-model")
        assert model is not None
        assert model.name == "custom-test-model"
        assert model.provider == "openai"
        
        # Clean up
        from metamorphic_guard.model_registry import _MODEL_REGISTRY
        _MODEL_REGISTRY.pop("custom-test-model", None)
    
    def test_model_metadata_defaults(self):
        """Test ModelMetadata default values."""
        metadata = ModelMetadata(
            name="test",
            provider="openai",
            pricing={"prompt": 0.01, "completion": 0.02},
        )
        
        assert metadata.pricing_unit == "1k"
        assert metadata.max_tokens is None
        assert metadata.max_context_length is None
        assert metadata.supports_system_prompt is True
        assert metadata.supports_streaming is True
        assert metadata.temperature_range == (0.0, 2.0)
        assert metadata.description is None
        assert metadata.constraints == {}
    
    def test_initialize_default_registry(self):
        """Test that default registry initialization works."""
        # Clear registry first
        from metamorphic_guard.model_registry import _MODEL_REGISTRY
        _MODEL_REGISTRY.clear()
        
        initialize_default_registry()
        
        # Should have registered models
        assert len(_MODEL_REGISTRY) > 0
        
        # Check some expected models
        assert get_model("gpt-4") is not None
        assert get_model("gpt-4-turbo") is not None
        assert get_model("claude-3-5-sonnet-20241022") is not None
