"""
Task registry for the comprehensive demo.

Registers the recommendation task so it can be used via CLI.
"""

from metamorphic_guard.specs import register_spec
from .task_spec import create_recommendation_task

# Register the task
recommendation_task = create_recommendation_task()
register_spec("recommendation", recommendation_task)

__all__ = ["recommendation_task"]






