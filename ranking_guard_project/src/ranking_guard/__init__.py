"""Utilities for gating ranking algorithm releases with Metamorphic Guard."""

from .runner import evaluate_candidate, EvaluationOutcome

__all__ = ["evaluate_candidate", "EvaluationOutcome"]
