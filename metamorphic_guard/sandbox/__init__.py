"""
Sandbox execution with resource limits and isolation.

This package provides sandbox execution capabilities split across modules:
- core: Main entry point (run_in_sandbox)
- local: Local subprocess execution
- docker: Docker container execution
- plugins: Executor plugin resolution
- utils: Utility functions for result processing
"""

from .core import run_in_sandbox

__all__ = ["run_in_sandbox"]



