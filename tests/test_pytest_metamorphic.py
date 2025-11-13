"""Tests for pytest-metamorphic plugin."""

import pytest


@pytest.mark.metamorphic(
    task="top_k",
    baseline="examples/top_k_baseline.py",
    candidate="examples/top_k_improved.py",
    n=50,
    seed=42,
    min_delta=0.0,  # Allow candidate if it's at least as good as baseline
)
def test_top_k_improved():
    """Example test using pytest-metamorphic marker."""
    # The actual evaluation is handled by the plugin
    # This test will pass if adoption gate succeeds
    pass


@pytest.mark.metamorphic(
    task="top_k",
    baseline="examples/top_k_baseline.py",
    candidate="examples/top_k_bad.py",
    n=50,
    seed=42,
    expect_adopt=False,  # Expect adoption to fail (bad candidate should be rejected)
)
def test_top_k_bad_should_fail():
    """Example test that verifies bad candidate is correctly rejected."""
    # This test passes when the adoption gate correctly rejects the bad candidate
    pass

