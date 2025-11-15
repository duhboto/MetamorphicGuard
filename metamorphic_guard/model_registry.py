"""
Centralized model registry with pricing, token limits, and constraints.

Provides a single source of truth for LLM model metadata across all executors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .types import JSONDict


@dataclass
class ModelMetadata:
    """Metadata for an LLM model."""
    
    name: str
    provider: str  # "openai", "anthropic", "vllm", etc.
    pricing: Dict[str, float]  # {"prompt": price_per_1k, "completion": price_per_1k}
    pricing_unit: str = "1k"  # "1k" for per-1K tokens, "1m" for per-1M tokens
    max_tokens: Optional[int] = None  # Maximum tokens per request
    max_context_length: Optional[int] = None  # Maximum context window
    supports_system_prompt: bool = True
    supports_streaming: bool = True
    temperature_range: tuple[float, float] = (0.0, 2.0)  # (min, max)
    description: Optional[str] = None
    constraints: Dict[str, Any] = field(default_factory=dict)  # Provider-specific constraints


# Default model registry
_MODEL_REGISTRY: Dict[str, ModelMetadata] = {}


def register_model(metadata: ModelMetadata) -> None:
    """Register a model in the global registry."""
    _MODEL_REGISTRY[metadata.name] = metadata


def get_model(name: str) -> Optional[ModelMetadata]:
    """Get model metadata by name."""
    return _MODEL_REGISTRY.get(name)


def list_models(provider: Optional[str] = None) -> list[ModelMetadata]:
    """List all registered models, optionally filtered by provider."""
    models = list(_MODEL_REGISTRY.values())
    if provider:
        models = [m for m in models if m.provider == provider]
    return sorted(models, key=lambda m: m.name)


def get_pricing(name: str, unit: str = "1k") -> Optional[Dict[str, float]]:
    """
    Get pricing for a model, normalized to the specified unit.
    
    Args:
        name: Model name
        unit: Target unit ("1k" for per-1K tokens, "1m" for per-1M tokens)
    
    Returns:
        Pricing dict with "prompt" and "completion" keys, or None if not found
    """
    model = get_model(name)
    if not model:
        return None
    
    pricing = model.pricing.copy()
    
    # Normalize to target unit
    if model.pricing_unit == "1k" and unit == "1m":
        # Convert from per-1K to per-1M
        pricing["prompt"] = pricing["prompt"] * 1000
        pricing["completion"] = pricing["completion"] * 1000
    elif model.pricing_unit == "1m" and unit == "1k":
        # Convert from per-1M to per-1K
        pricing["prompt"] = pricing["prompt"] / 1000
        pricing["completion"] = pricing["completion"] / 1000
    
    return pricing


def initialize_default_registry() -> None:
    """Initialize the registry with default models."""
    # OpenAI models
    register_model(ModelMetadata(
        name="gpt-4",
        provider="openai",
        pricing={"prompt": 0.03, "completion": 0.06},
        pricing_unit="1k",
        max_tokens=8192,
        max_context_length=8192,
        description="GPT-4 base model",
    ))
    
    register_model(ModelMetadata(
        name="gpt-4-turbo",
        provider="openai",
        pricing={"prompt": 0.01, "completion": 0.03},
        pricing_unit="1k",
        max_tokens=4096,
        max_context_length=128000,
        description="GPT-4 Turbo with extended context",
    ))
    
    register_model(ModelMetadata(
        name="gpt-3.5-turbo",
        provider="openai",
        pricing={"prompt": 0.0015, "completion": 0.002},
        pricing_unit="1k",
        max_tokens=4096,
        max_context_length=16385,
        description="GPT-3.5 Turbo, fast and cost-effective",
    ))
    
    # Anthropic models (pricing per 1M tokens)
    register_model(ModelMetadata(
        name="claude-3-5-sonnet-20241022",
        provider="anthropic",
        pricing={"prompt": 3.0, "completion": 15.0},
        pricing_unit="1m",
        max_tokens=8192,
        max_context_length=200000,
        temperature_range=(0.0, 1.0),
        description="Claude 3.5 Sonnet, latest version",
    ))
    
    register_model(ModelMetadata(
        name="claude-3-opus-20240229",
        provider="anthropic",
        pricing={"prompt": 15.0, "completion": 75.0},
        pricing_unit="1m",
        max_tokens=4096,
        max_context_length=200000,
        temperature_range=(0.0, 1.0),
        description="Claude 3 Opus, most capable",
    ))
    
    register_model(ModelMetadata(
        name="claude-3-sonnet-20240229",
        provider="anthropic",
        pricing={"prompt": 3.0, "completion": 15.0},
        pricing_unit="1m",
        max_tokens=4096,
        max_context_length=200000,
        temperature_range=(0.0, 1.0),
        description="Claude 3 Sonnet, balanced performance",
    ))
    
    register_model(ModelMetadata(
        name="claude-3-haiku-20240307",
        provider="anthropic",
        pricing={"prompt": 0.25, "completion": 1.25},
        pricing_unit="1m",
        max_tokens=4096,
        max_context_length=200000,
        temperature_range=(0.0, 1.0),
        description="Claude 3 Haiku, fastest and most affordable",
    ))
    
    # vLLM models (local, no API cost)
    register_model(ModelMetadata(
        name="vllm-local",
        provider="vllm",
        pricing={"prompt": 0.0, "completion": 0.0},
        pricing_unit="1k",
        max_tokens=None,  # Model-dependent
        max_context_length=None,  # Model-dependent
        description="Local vLLM inference (no API cost)",
        constraints={"requires_gpu": True, "local_only": True},
    ))


# Initialize default registry on import
initialize_default_registry()


def update_model_pricing(name: str, pricing: Dict[str, float]) -> None:
    """Update pricing for an existing model."""
    model = get_model(name)
    if model:
        model.pricing = pricing
    else:
        raise ValueError(f"Model '{name}' not found in registry")


def add_custom_model(
    name: str,
    provider: str,
    pricing: Dict[str, float],
    pricing_unit: str = "1k",
    max_tokens: Optional[int] = None,
    max_context_length: Optional[int] = None,
    description: Optional[str] = None,
    **kwargs: Any,
) -> None:
    """Add a custom model to the registry."""
    metadata = ModelMetadata(
        name=name,
        provider=provider,
        pricing=pricing,
        pricing_unit=pricing_unit,
        max_tokens=max_tokens,
        max_context_length=max_context_length,
        description=description,
        constraints=kwargs.get("constraints", {}),
    )
    register_model(metadata)


def get_model_info(name: str) -> Optional[JSONDict]:
    """Get model information as a JSON-serializable dict."""
    model = get_model(name)
    if not model:
        return None
    
    return {
        "name": model.name,
        "provider": model.provider,
        "pricing": model.pricing,
        "pricing_unit": model.pricing_unit,
        "max_tokens": model.max_tokens,
        "max_context_length": model.max_context_length,
        "supports_system_prompt": model.supports_system_prompt,
        "supports_streaming": model.supports_streaming,
        "temperature_range": list(model.temperature_range),
        "description": model.description,
        "constraints": model.constraints,
    }


def is_valid_model(provider: str, model_name: str) -> bool:
    """
    Check if a model name is valid for a given provider.
    
    Args:
        provider: Provider name (e.g., "openai", "anthropic")
        model_name: Model name to validate
    
    Returns:
        True if the model is registered for the provider, False otherwise
    """
    if not model_name or not isinstance(model_name, str) or not model_name.strip():
        return False
    
    models = list_models(provider=provider)
    return any(m.name == model_name.strip() for m in models)


def get_valid_models(provider: str) -> set[str]:
    """
    Get set of valid model names for a provider.
    
    Args:
        provider: Provider name (e.g., "openai", "anthropic")
    
    Returns:
        Set of valid model names
    """
    models = list_models(provider=provider)
    return {m.name for m in models}


def validate_model(
    provider: str,
    model_name: str,
    *,
    raise_error: bool = False,
) -> tuple[bool, Optional[str], list[str]]:
    """
    Validate a model name for a provider and optionally provide suggestions.
    
    Args:
        provider: Provider name (e.g., "openai", "anthropic")
        model_name: Model name to validate
        raise_error: If True, raise ValueError for invalid models
    
    Returns:
        Tuple of (is_valid, error_message, suggestions)
    """
    if not model_name or not isinstance(model_name, str) or not model_name.strip():
        error_msg = f"Invalid model name: model name cannot be empty"
        if raise_error:
            raise ValueError(error_msg)
        return False, error_msg, []
    
    model_name = model_name.strip()
    is_valid = is_valid_model(provider, model_name)
    
    if is_valid:
        return True, None, []
    
    # Generate suggestions (simple fuzzy matching by name similarity)
    valid_models = get_valid_models(provider)
    suggestions: list[str] = []
    
    # Simple substring matching for suggestions
    for valid_model in valid_models:
        if model_name.lower() in valid_model.lower() or valid_model.lower() in model_name.lower():
            suggestions.append(valid_model)
    
    # Limit suggestions
    suggestions = suggestions[:5]
    
    error_msg = f"Invalid model name '{model_name}' for provider '{provider}'"
    if suggestions:
        error_msg += f". Did you mean: {', '.join(suggestions[:3])}?"
    
    if raise_error:
        raise ValueError(error_msg)
    
    return False, error_msg, suggestions


# Initialize default registry on module import
initialize_default_registry()
