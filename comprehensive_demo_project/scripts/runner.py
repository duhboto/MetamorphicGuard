"""
Runner script for comprehensive demo.
Registers the task spec and invokes the CLI.
"""

import sys
import os
from pathlib import Path

# Add src to path to allow importing comprehensive_demo
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

try:
    from comprehensive_demo.task_spec import create_recommendation_task
except ImportError:
    # If running from repo root context without installation
    sys.path.insert(0, str(Path(__file__).parents[1]))
    from src.comprehensive_demo.task_spec import create_recommendation_task

from metamorphic_guard.specs import _TASK_REGISTRY
from metamorphic_guard.cli.main import main

# Register task manually since we're not installed as a plugin
_TASK_REGISTRY["recommendation"] = create_recommendation_task

if __name__ == "__main__":
    # Invoke the CLI
    main()

