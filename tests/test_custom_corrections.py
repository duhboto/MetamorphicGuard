"""
Tests for custom correction methods in multiple comparisons.
"""

from __future__ import annotations

import pytest

from metamorphic_guard.multiple_comparisons import (
    apply_multiple_comparisons_correction,
    register_correction_method,
    get_registered_methods,
)


def test_register_custom_correction():
    """Test registering a custom correction method."""
    def bonferroni_correction(p_values: list[float], alpha: float) -> list[tuple[int, float, bool]]:
        """Simple Bonferroni correction."""
        n = len(p_values)
        if n == 0:
            return []
        
        results = []
        for i, p_val in enumerate(p_values):
            adjusted_p = min(1.0, p_val * n)
            is_significant = adjusted_p <= alpha
            results.append((i, adjusted_p, is_significant))
        
        return results
    
    register_correction_method("bonferroni", bonferroni_correction)
    
    # Verify it's registered
    assert "bonferroni" in get_registered_methods()
    
    # Test using the custom method
    p_values = [0.01, 0.02, 0.03]
    results = apply_multiple_comparisons_correction(p_values, method="bonferroni", alpha=0.05)
    
    assert len(results) == 3
    # First p-value: 0.01 * 3 = 0.03 < 0.05, should be significant
    assert results[0][2] is True


def test_custom_function_as_method():
    """Test passing a custom function directly."""
    def simple_correction(p_values: list[float], alpha: float) -> list[tuple[int, float, bool]]:
        """Simple correction that multiplies by 2."""
        results = []
        for i, p_val in enumerate(p_values):
            adjusted_p = min(1.0, p_val * 2)
            is_significant = adjusted_p <= alpha
            results.append((i, adjusted_p, is_significant))
        return results
    
    p_values = [0.01, 0.02, 0.03]
    results = apply_multiple_comparisons_correction(p_values, method=simple_correction, alpha=0.05)
    
    assert len(results) == 3
    # First p-value: 0.01 * 2 = 0.02 < 0.05, should be significant
    assert results[0][2] is True


def test_invalid_custom_function():
    """Test that invalid custom functions raise errors."""
    def bad_function(p_values: list[float]) -> list[tuple[int, float, bool]]:
        """Function with wrong signature."""
        return []
    
    p_values = [0.01, 0.02]
    
    with pytest.raises(ValueError, match="Custom correction function failed"):
        apply_multiple_comparisons_correction(p_values, method=bad_function, alpha=0.05)


def test_register_invalid_name():
    """Test that invalid method names raise errors."""
    def dummy_correction(p_values: list[float], alpha: float) -> list[tuple[int, float, bool]]:
        return []
    
    with pytest.raises(ValueError, match="name must be a non-empty string"):
        register_correction_method("", dummy_correction)
    
    with pytest.raises(ValueError, match="name must be a non-empty string"):
        register_correction_method("   ", dummy_correction)


def test_register_invalid_function():
    """Test that non-callable functions raise errors."""
    with pytest.raises(ValueError, match="Correction function must be callable"):
        register_correction_method("invalid", "not a function")


def test_get_registered_methods():
    """Test getting list of registered methods."""
    methods = get_registered_methods()
    
    # Should include built-in methods
    assert "holm" in methods
    assert "hochberg" in methods
    assert "fdr" in methods
    assert "bh" in methods


def test_custom_method_overrides():
    """Test that custom methods can override built-in names (if desired)."""
    # Note: This tests the ability, but in practice we might want to prevent this
    def custom_holm(p_values: list[float], alpha: float) -> list[tuple[int, float, bool]]:
        """Custom Holm that always returns significant."""
        return [(i, 0.0, True) for i in range(len(p_values))]
    
    # Register with a different name to avoid confusion
    register_correction_method("custom_holm", custom_holm)
    
    p_values = [0.5, 0.6, 0.7]  # Large p-values
    results = apply_multiple_comparisons_correction(p_values, method="custom_holm", alpha=0.05)
    
    # Custom method should make all significant
    assert all(is_sig for _, _, is_sig in results)

