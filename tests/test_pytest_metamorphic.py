"""Tests for pytest-metamorphic plugin."""

import pytest


@pytest.mark.metamorphic(
    task="top_k",
    baseline="examples/top_k_baseline.py",
    candidate="examples/top_k_improved.py",
    n=50,
    seed=42,
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
)
def test_top_k_bad_should_fail():
    """Example test that should fail due to bad candidate."""
    # This test should fail because the bad candidate doesn't meet the gate
    pass

