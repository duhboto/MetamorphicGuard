"""
Pytest configuration and fixtures for deterministic testing.
"""

import os
import random
from typing import Generator

import numpy as np
import pytest


@pytest.fixture(autouse=True)
def deterministic_env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """
    Automatically apply deterministic settings for all tests.
    
    - Fix random seeds for Python's random and numpy.random
    - Set environment variables for test-friendly defaults
    - Use deterministic CI method (newcombe) instead of bootstrap
    - Relax timeout/parallel settings for CI environments
    """
    # Fix random seeds
    seed = 12345
    random.seed(seed)
    np.random.seed(seed)
    
    # Set environment variables for deterministic behavior
    monkeypatch.setenv("PYTHONHASHSEED", "0")
    
    # Test-friendly defaults
    monkeypatch.setenv("MG_TEST_TIMEOUT_S", "5.0")
    monkeypatch.setenv("MG_TEST_PARALLEL", "1")
    monkeypatch.setenv("MG_DEFAULT_CI_METHOD", "newcombe")
    
    yield
    
    # Cleanup if needed
    pass

