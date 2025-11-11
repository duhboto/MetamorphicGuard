"""
Structured judges for evaluating LLM outputs with rubrics and citations.
"""

import json
from typing import Any, Dict, Optional

from .__init__ import LLMJudge


class RubricJudge(LLMJudge):
    """Judge that evaluates outputs against a structured rubric."""

    PLUGIN_METADATA = {
        "name": "Rubric Judge",
        "description": "Evaluate outputs against a structured rubric",
        "version": "1.0.0",
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config)
        # Rubric can be provided as JSON string or dict
        rubric_raw = config.get("rubric") if config else None
        if isinstance(rubric_raw, str):
            try:
                self.rubric = json.loads(rubric_raw)
            except json.JSONDecodeError:
                self.rubric = {}
        elif isinstance(rubric_raw, dict):
            self.rubric = rubric_raw
        else:
            # Default rubric structure
            self.rubric = {
                "criteria": [
                    {"name": "completeness", "weight": 0.3, "description": "Addresses all aspects"},
                    {"name": "accuracy", "weight": 0.4, "description": "Factually correct"},
                    {"name": "clarity", "weight": 0.3, "description": "Clear and understandable"},
                ],
                "threshold": 0.7,
            }

    def evaluate(
        self,
        output: str,
        input_data: Any,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Evaluate output against rubric."""
        criteria = self.rubric.get("criteria", [])
        threshold = self.rubric.get("threshold", 0.7)

        scores: Dict[str, float] = {}
        total_score = 0.0
        total_weight = 0.0

        for criterion in criteria:
            name = criterion.get("name", "unknown")
            weight = float(criterion.get("weight", 1.0))
            # Simple scoring: check if output contains keywords or meets basic criteria
            # In practice, this would use more sophisticated evaluation
            score = self._score_criterion(output, criterion)
            scores[name] = score
            total_score += score * weight
            total_weight += weight

        final_score = total_score / total_weight if total_weight > 0 else 0.0
        passes = final_score >= threshold

        return {
            "pass": passes,
            "score": final_score,
            "reason": f"Rubric score: {final_score:.2f} (threshold: {threshold})",
            "details": {
                "rubric": self.rubric,
                "scores": scores,
                "final_score": final_score,
                "threshold": threshold,
            },
        }

    def _score_criterion(self, output: str, criterion: Dict[str, Any]) -> float:
        """Score a single criterion (simplified implementation)."""
        # This is a placeholder - real implementation would use LLM-as-judge
        # or more sophisticated heuristics
        name = criterion.get("name", "").lower()
        description = criterion.get("description", "").lower()

        # Simple heuristics
        if "completeness" in name or "complete" in description:
            # Check if output has reasonable length
            return min(1.0, len(output) / 100.0)
        elif "accuracy" in name or "accurate" in description:
            # Can't really check accuracy without ground truth
            # Default to 0.8 as placeholder
            return 0.8
        elif "clarity" in name or "clear" in description:
            # Check for sentence structure
            sentences = output.split(".")
            return min(1.0, len(sentences) / 5.0)

        return 0.5  # Default score


class CitationJudge(LLMJudge):
    """Judge that checks for citations and attribution in outputs."""

    PLUGIN_METADATA = {
        "name": "Citation Judge",
        "description": "Check for citations and attribution",
        "version": "1.0.0",
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config)
        self.require_citations = bool(config.get("require_citations", False)) if config else False
        self.min_citations = int(config.get("min_citations", 1)) if config else 1
        import re

        # Patterns for citations
        self.citation_patterns = [
            re.compile(r"\[(\d+)\]"),  # [1], [2], etc.
            re.compile(r"\([A-Za-z]+\s+et\s+al\.\s+\d{4}\)"),  # (Author et al. 2024)
            re.compile(r"\([A-Za-z]+\s+\d{4}\)"),  # (Author 2024)
            re.compile(r"https?://[^\s]+"),  # URLs
        ]

    def evaluate(
        self,
        output: str,
        input_data: Any,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Check for citations in output."""
        citations_found = []
        for pattern in self.citation_patterns:
            matches = pattern.findall(output)
            citations_found.extend(matches)

        citation_count = len(citations_found)
        has_citations = citation_count >= self.min_citations

        if self.require_citations and not has_citations:
            return {
                "pass": False,
                "score": 0.0,
                "reason": f"No citations found (required: {self.min_citations}, found: {citation_count})",
                "details": {
                    "citation_count": citation_count,
                    "min_required": self.min_citations,
                    "citations": citations_found[:10],  # Limit to first 10
                },
            }

        # Score based on citation count
        score = min(1.0, citation_count / max(1, self.min_citations))

        return {
            "pass": True,
            "score": score,
            "reason": f"Found {citation_count} citation(s)",
            "details": {
                "citation_count": citation_count,
                "citations": citations_found[:10],
            },
        }

