"""
CLI module for Metamorphic Guard command-line interface.

This module has been refactored from a monolithic cli.py into smaller,
focused command modules for better maintainability.
"""

from .main import main

__all__ = ["main"]

