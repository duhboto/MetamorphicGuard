"""
Sandbox execution with resource limits and isolation.

This module is maintained for backward compatibility.
All functionality has been moved to the sandbox package.
"""

# Re-export from the refactored module structure
from .sandbox import run_in_sandbox

__all__ = ["run_in_sandbox"]
