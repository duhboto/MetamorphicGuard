"""
CLI preset configurations for common evaluation workflows.

Presets provide sensible defaults for different use cases, reducing the number
of flags users need to specify while still allowing overrides.
"""

from __future__ import annotations

from typing import Any, Dict


# Preset definitions
PRESETS: Dict[str, Dict[str, Any]] = {
    "minimal": {
        "description": "Minimal configuration - only core options",
        "options": {
            # Only task, baseline, candidate, and n are required
            # All other options use their defaults
        },
    },
    "standard": {
        "description": "Standard evaluation with common defaults",
        "options": {
            "n": 400,
            "seed": 42,
            "timeout_s": 2.0,
            "alpha": 0.05,
            "min_delta": 0.02,
            "ci_method": "bootstrap",
            "bootstrap_samples": 1000,
        },
    },
    "sequential": {
        "description": "Sequential testing preset for iterative PR workflows",
        "options": {
            "n": 400,
            "seed": 42,
            "timeout_s": 2.0,
            "alpha": 0.05,
            "min_delta": 0.02,
            "ci_method": "bootstrap",
            "bootstrap_samples": 1000,
            "sequential_method": "pocock",
            "max_looks": 5,
            "look_number": 1,
        },
    },
    "adaptive": {
        "description": "Adaptive testing preset with automatic sample size determination",
        "options": {
            "n": 400,  # Initial sample size
            "seed": 42,
            "timeout_s": 2.0,
            "alpha": 0.05,
            "min_delta": 0.02,
            "ci_method": "bootstrap",
            "bootstrap_samples": 1000,
            "adaptive_testing": True,
            "adaptive_min_sample_size": 50,
            "adaptive_check_interval": 50,
            "adaptive_power_threshold": 0.95,
            "adaptive_max_sample_size": None,
            "adaptive_group_sequential": False,
            "adaptive_sequential_method": "pocock",
            "adaptive_max_looks": 5,
        },
    },
    "full": {
        "description": "Full configuration - all options available (current default behavior)",
        "options": {
            # Empty dict means use all defaults - no preset overrides
            # This is equivalent to not using a preset
        },
    },
}


def apply_preset(preset_name: str, user_options: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply preset configuration to user options.
    
    Preset options are applied first, then user options override them.
    This allows users to override any preset value with explicit flags.
    
    Args:
        preset_name: Name of the preset to apply
        user_options: User-provided options (from CLI flags)
    
    Returns:
        Combined options with preset defaults and user overrides
    
    Raises:
        ValueError: If preset_name is not recognized
    """
    if preset_name not in PRESETS:
        available = ", ".join(PRESETS.keys())
        raise ValueError(
            f"Unknown preset: {preset_name}. Available presets: {available}"
        )
    
    preset_options = PRESETS[preset_name]["options"].copy()
    
    # User options override preset options
    preset_options.update(user_options)
    
    return preset_options


def get_preset_description(preset_name: str) -> str:
    """Get the description for a preset."""
    if preset_name not in PRESETS:
        return ""
    return PRESETS[preset_name]["description"]


def list_presets() -> Dict[str, str]:
    """List all available presets with their descriptions."""
    return {
        name: preset["description"]
        for name, preset in PRESETS.items()
    }



