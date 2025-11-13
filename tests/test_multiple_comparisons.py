"""
Tests for multiple comparisons correction methods.
"""

from __future__ import annotations

import pytest

from metamorphic_guard.multiple_comparisons import (
    holm_correction,
    hochberg_correction,
    benjamini_hochberg_correction,
    apply_multiple_comparisons_correction,
)


def test_holm_correction_basic():
    """Test basic Holm correction."""
    p_values = [0.01, 0.02, 0.03, 0.04, 0.05]
    alpha = 0.05
    
    results = holm_correction(p_values, alpha)
    
    assert len(results) == 5
    # First p-value (0.01) should be significant (0.01 <= 0.05/5 = 0.01)
    assert results[0][2] is True  # is_significant
    # Other p-values may or may not be significant depending on adjustment


def test_hochberg_correction_basic():
    """Test basic Hochberg correction."""
    p_values = [0.01, 0.02, 0.03, 0.04, 0.05]
    alpha = 0.05
    
    results = hochberg_correction(p_values, alpha)
    
    assert len(results) == 5
    # Hochberg should be at least as powerful as Holm
    # (may reject more hypotheses)


def test_hochberg_vs_holm_comparison():
    """Test that Hochberg is more powerful than Holm."""
    p_values = [0.01, 0.015, 0.02, 0.025, 0.03]
    alpha = 0.05
    
    holm_results = holm_correction(p_values, alpha)
    hochberg_results = hochberg_correction(p_values, alpha)
    
    # Count significant results
    holm_sig = sum(1 for _, _, sig in holm_results if sig)
    hochberg_sig = sum(1 for _, _, sig in hochberg_results if sig)
    
    # Hochberg should be at least as powerful (equal or more rejections)
    assert hochberg_sig >= holm_sig


def test_benjamini_hochberg_correction_basic():
    """Test basic Benjamini-Hochberg correction."""
    p_values = [0.01, 0.02, 0.03, 0.04, 0.05]
    alpha = 0.05
    
    results = benjamini_hochberg_correction(p_values, alpha)
    
    assert len(results) == 5
    # FDR correction is less conservative, may reject more


def test_apply_correction_holm():
    """Test apply_multiple_comparisons_correction with Holm."""
    p_values = [0.01, 0.02, 0.03]
    results = apply_multiple_comparisons_correction(p_values, method="holm")
    
    assert len(results) == 3


def test_apply_correction_hochberg():
    """Test apply_multiple_comparisons_correction with Hochberg."""
    p_values = [0.01, 0.02, 0.03]
    results = apply_multiple_comparisons_correction(p_values, method="hochberg")
    
    assert len(results) == 3


def test_apply_correction_fdr():
    """Test apply_multiple_comparisons_correction with FDR."""
    p_values = [0.01, 0.02, 0.03]
    results = apply_multiple_comparisons_correction(p_values, method="fdr")
    
    assert len(results) == 3


def test_apply_correction_invalid_method():
    """Test that invalid method raises error."""
    p_values = [0.01, 0.02]
    
    with pytest.raises(ValueError, match="Unknown correction method"):
        apply_multiple_comparisons_correction(p_values, method="invalid")


def test_empty_p_values():
    """Test correction with empty p-values list."""
    results = holm_correction([], 0.05)
    assert results == []
    
    results = hochberg_correction([], 0.05)
    assert results == []
    
    results = benjamini_hochberg_correction([], 0.05)
    assert results == []


def test_hochberg_properties():
    """Test properties of Hochberg correction."""
    p_values = [0.001, 0.002, 0.003, 0.004, 0.005]
    alpha = 0.05
    
    results = hochberg_correction(p_values, alpha)
    
    # All results should have adjusted p-values >= original
    for i, (idx, adjusted_p, is_sig) in enumerate(results):
        original_p = p_values[idx]
        assert adjusted_p >= original_p
    
    # Results should be sorted by original p-value (ascending)
    # (adjusted p-values may not be in order due to different adjustments)
    original_p_vals = [p_values[idx] for idx, _, _ in results]
    assert original_p_vals == sorted(original_p_vals)


def test_hochberg_all_significant():
    """Test Hochberg when all p-values are significant."""
    p_values = [0.001, 0.002, 0.003]
    alpha = 0.05
    
    results = hochberg_correction(p_values, alpha)
    
    # All should be significant since all are very small
    for _, _, is_sig in results:
        assert is_sig is True


def test_hochberg_none_significant():
    """Test Hochberg when no p-values are significant."""
    p_values = [0.5, 0.6, 0.7]
    alpha = 0.05
    
    results = hochberg_correction(p_values, alpha)
    
    # None should be significant
    for _, _, is_sig in results:
        assert is_sig is False

