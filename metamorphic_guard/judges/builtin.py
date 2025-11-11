"""
Built-in judge implementations for LLM output evaluation.
"""

from typing import Any, Dict, Optional

from .__init__ import LLMJudge


class LengthJudge(LLMJudge):
    """Judge that checks output length constraints."""

    PLUGIN_METADATA = {
        "name": "Length Judge",
        "description": "Check output length constraints",
        "version": "1.0.0",
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config)
        self.min_chars = config.get("min_chars", 0) if config else 0
        self.max_chars = config.get("max_chars") if config else None

    def evaluate(
        self,
        output: str,
        input_data: Any,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Evaluate output length."""
        length = len(output)

        if length < self.min_chars:
            return {
                "pass": False,
                "score": 0.0,
                "reason": f"Output too short: {length} < {self.min_chars}",
                "details": {"length": length, "min_chars": self.min_chars},
            }

        if self.max_chars is not None and length > self.max_chars:
            return {
                "pass": False,
                "score": 0.0,
                "reason": f"Output too long: {length} > {self.max_chars}",
                "details": {"length": length, "max_chars": self.max_chars},
            }

        # Score based on how close to ideal (if max specified)
        if self.max_chars:
            ideal = (self.min_chars + self.max_chars) / 2
            distance = abs(length - ideal)
            max_distance = max(ideal - self.min_chars, self.max_chars - ideal)
            score = 1.0 - (distance / max_distance) if max_distance > 0 else 1.0
        else:
            score = 1.0 if length >= self.min_chars else 0.0

        return {
            "pass": True,
            "score": max(0.0, min(1.0, score)),
            "reason": f"Length acceptable: {length} chars",
            "details": {"length": length, "min_chars": self.min_chars, "max_chars": self.max_chars},
        }


class NoPIIJudge(LLMJudge):
    """Judge that checks for PII (Personally Identifiable Information)."""

    PLUGIN_METADATA = {
        "name": "No PII Judge",
        "description": "Check output for PII patterns",
        "version": "1.0.0",
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config)
        import re

        # Basic PII patterns
        self.patterns = [
            (r"\b\d{3}-\d{2}-\d{4}\b", "SSN"),
            (r"\b\d{3}\.\d{3}\.\d{4}\b", "SSN"),
            (r"\b\d{16}\b", "Credit card"),
            (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "Email"),
            (r"\b\d{3}-\d{3}-\d{4}\b", "Phone"),
        ]
        self.compiled_patterns = [(re.compile(pattern), label) for pattern, label in self.patterns]

    def evaluate(
        self,
        output: str,
        input_data: Any,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Check for PII patterns."""
        found_pii = []
        for pattern, label in self.compiled_patterns:
            matches = pattern.findall(output)
            if matches:
                found_pii.append({"type": label, "matches": len(matches)})

        if found_pii:
            return {
                "pass": False,
                "score": 0.0,
                "reason": f"PII detected: {[p['type'] for p in found_pii]}",
                "details": {"pii_found": found_pii},
            }

        return {
            "pass": True,
            "score": 1.0,
            "reason": "No PII detected",
            "details": {},
        }

