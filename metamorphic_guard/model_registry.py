"""
Model registry for validating LLM model names across providers.

Provides a central registry of valid model names and validation utilities
to catch invalid models early with helpful error messages.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple
from difflib import get_close_matches


# Registry of valid models by provider
_MODEL_REGISTRY: Dict[str, Set[str]] = {
    "openai": {
        # GPT-4 family
        "gpt-4",
        "gpt-4-turbo",
        "gpt-4-turbo-preview",
        "gpt-4-0125-preview",
        "gpt-4-1106-preview",
        "gpt-4-vision-preview",
        "gpt-4-32k",
        "gpt-4-32k-0314",
        "gpt-4-32k-0613",
        # GPT-3.5 family
        "gpt-3.5-turbo",
        "gpt-3.5-turbo-16k",
        "gpt-3.5-turbo-1106",
        "gpt-3.5-turbo-0125",
        # Legacy models
        "gpt-3.5-turbo-instruct",
        "text-davinci-003",
        "text-davinci-002",
        "text-davinci-001",
        "text-curie-001",
        "text-babbage-001",
        "text-ada-001",
        # Embeddings
        "text-embedding-3-small",
        "text-embedding-3-large",
        "text-embedding-ada-002",
    },
    "anthropic": {
        # Claude 3 family
        "claude-3-5-sonnet-20241022",
        "claude-3-5-sonnet-20240620",
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
        # Claude 2 family
        "claude-2.1",
        "claude-2.0",
        "claude-instant-1.2",
        # Legacy
        "claude-v1",
        "claude-v1.3",
        "claude-instant-v1",
        "claude-instant-v1.1",
    },
    "vllm": {
        # Common model families (vLLM supports many models, this is a representative set)
        # Meta LLaMA
        "meta-llama/Llama-2-7b-hf",
        "meta-llama/Llama-2-13b-hf",
        "meta-llama/Llama-2-70b-hf",
        "meta-llama/Llama-2-7b-chat-hf",
        "meta-llama/Llama-2-13b-chat-hf",
        "meta-llama/Llama-2-70b-chat-hf",
        # Mistral
        "mistralai/Mistral-7B-v0.1",
        "mistralai/Mistral-7B-Instruct-v0.1",
        "mistralai/Mistral-7B-Instruct-v0.2",
        # Qwen
        "Qwen/Qwen-7B",
        "Qwen/Qwen-7B-Chat",
        # Other common models
        "microsoft/phi-2",
        "google/gemma-7b",
        "google/gemma-7b-it",
        # Note: vLLM supports many more models, but we list common ones
        # Users can still use other models by path, validation is lenient for vLLM
    },
}

# Model families for grouping and suggestions
_MODEL_FAMILIES: Dict[str, List[str]] = {
    "openai": {
        "gpt-4": ["gpt-4", "gpt-4-turbo", "gpt-4-turbo-preview", "gpt-4-32k"],
        "gpt-3.5": ["gpt-3.5-turbo", "gpt-3.5-turbo-16k", "gpt-3.5-turbo-1106"],
    },
    "anthropic": {
        "claude-3": [
            "claude-3-5-sonnet-20241022",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
        ],
        "claude-2": ["claude-2.1", "claude-2.0"],
    },
}


def get_valid_models(provider: str) -> Set[str]:
    """
    Get the set of valid model names for a provider.
    
    Args:
        provider: Provider name (openai, anthropic, vllm)
        
    Returns:
        Set of valid model names
    """
    normalized = provider.lower()
    return _MODEL_REGISTRY.get(normalized, set())


def is_valid_model(provider: str, model: str) -> bool:
    """
    Check if a model name is valid for a provider.
    
    Args:
        provider: Provider name (openai, anthropic, vllm)
        model: Model name to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not model or not isinstance(model, str):
        return False
    
    normalized_provider = provider.lower()
    valid_models = get_valid_models(normalized_provider)
    
    # For vLLM, be more lenient - support any model path
    if normalized_provider == "vllm":
        # Accept if it's in registry or looks like a valid model path
        if model in valid_models:
            return True
        # Accept paths like "org/model-name" or "model-name"
        if "/" in model or model.replace("-", "").replace("_", "").isalnum():
            return True
        return False
    
    # For OpenAI and Anthropic, be strict but allow custom models if they look valid
    if model in valid_models:
        return True
    
    # Allow custom/private models if they follow a reasonable naming pattern
    # (e.g., org-name/model-name, or model-name with alphanumeric/dashes)
    if "/" in model or model.replace("-", "").replace("_", "").replace(".", "").isalnum():
        # This might be a custom/private model - allow it but warn later
        return True
    
    # Otherwise reject
    return False


def suggest_model(provider: str, model: str, cutoff: float = 0.6, max_suggestions: int = 3) -> List[str]:
    """
    Suggest similar model names for a provider.
    
    Args:
        provider: Provider name (openai, anthropic, vllm)
        model: Invalid model name
        cutoff: Similarity cutoff (0.0-1.0)
        max_suggestions: Maximum number of suggestions
        
    Returns:
        List of suggested model names
    """
    if not model or not isinstance(model, str):
        return []
    
    normalized_provider = provider.lower()
    valid_models = list(get_valid_models(normalized_provider))
    
    if not valid_models:
        return []
    
    # Use difflib to find close matches
    suggestions = get_close_matches(
        model.lower(),
        [m.lower() for m in valid_models],
        n=max_suggestions,
        cutoff=cutoff,
    )
    
    # Map back to original case
    model_map = {m.lower(): m for m in valid_models}
    return [model_map[s.lower()] for s in suggestions if s.lower() in model_map]


def validate_model(
    provider: str,
    model: str,
    raise_error: bool = False,
) -> Tuple[bool, Optional[str], List[str]]:
    """
    Validate a model name for a provider.
    
    Args:
        provider: Provider name (openai, anthropic, vllm)
        model: Model name to validate
        raise_error: If True, raise ValueError for invalid models
        
    Returns:
        Tuple of (is_valid, error_message, suggestions)
        - is_valid: True if model is valid
        - error_message: Error message if invalid (None if valid)
        - suggestions: List of suggested model names
    """
    is_valid = is_valid_model(provider, model)
    
    if is_valid:
        return (True, None, [])
    
    # Generate suggestions
    suggestions = suggest_model(provider, model)
    
    # Build error message
    error_msg = f"Invalid model '{model}' for provider '{provider}'"
    if suggestions:
        suggestions_str = ", ".join(suggestions[:3])
        error_msg += f". Did you mean: {suggestions_str}?"
    else:
        valid_models = get_valid_models(provider)
        if valid_models:
            # Show a few examples
            examples = list(valid_models)[:3]
            examples_str = ", ".join(examples)
            error_msg += f". Valid models include: {examples_str}"
    
    if raise_error:
        raise ValueError(error_msg)
    
    return (False, error_msg, suggestions)


def register_model(provider: str, model: str) -> None:
    """
    Register a custom model name for a provider.
    
    Useful for adding new models that aren't in the default registry,
    or for custom/private models.
    
    Args:
        provider: Provider name (openai, anthropic, vllm)
        model: Model name to register
    """
    if not provider or not isinstance(provider, str):
        raise ValueError("Provider must be a non-empty string")
    if not model or not isinstance(model, str):
        raise ValueError("Model name must be a non-empty string")
    
    normalized_provider = provider.lower()
    if normalized_provider not in _MODEL_REGISTRY:
        _MODEL_REGISTRY[normalized_provider] = set()
    
    _MODEL_REGISTRY[normalized_provider].add(model)


def register_models(provider: str, models: List[str]) -> None:
    """
    Register multiple custom model names for a provider.
    
    Args:
        provider: Provider name (openai, anthropic, vllm)
        models: List of model names to register
    """
    for model in models:
        register_model(provider, model)


def get_model_info(provider: str, model: str) -> Dict[str, any]:
    """
    Get information about a model.
    
    Args:
        provider: Provider name (openai, anthropic, vllm)
        model: Model name
        
    Returns:
        Dictionary with model information (is_valid, suggestions, family, etc.)
    """
    is_valid, error_msg, suggestions = validate_model(provider, model)
    
    info: Dict[str, any] = {
        "provider": provider,
        "model": model,
        "is_valid": is_valid,
        "error_message": error_msg,
        "suggestions": suggestions,
    }
    
    # Try to identify model family
    normalized_provider = provider.lower()
    if normalized_provider in _MODEL_FAMILIES:
        families = _MODEL_FAMILIES[normalized_provider]
        for family_name, family_models in families.items():
            if model in family_models:
                info["family"] = family_name
                break
    
    return info

