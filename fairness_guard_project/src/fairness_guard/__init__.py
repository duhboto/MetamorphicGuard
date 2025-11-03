"""Fairness Guard package exports."""

from __future__ import annotations

# Import task specification for registration side-effects.
from . import spec as _spec  # noqa: F401
from .runner import EvaluationOutcome, FairnessMetrics, evaluate_candidate

__all__ = ["EvaluationOutcome", "FairnessMetrics", "evaluate_candidate"]
