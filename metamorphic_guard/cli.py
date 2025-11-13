"""
Backward compatibility module for CLI.

This module has been refactored into metamorphic_guard.cli package.
All commands are now in separate modules for better maintainability.
"""

# Import main from the new CLI module for backward compatibility
from .cli import main

__all__ = ["main"]
