"""
Structured judges for evaluating LLM outputs with rubrics and citations.

Includes specialized judges for RAG (Retrieval-Augmented Generation) applications:
- CitationJudge: Checks for citations and citation formats
- AttributionJudge: Verifies attribution overlap and content matching
"""

import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple

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
    """
    Judge that checks for citations and attribution in outputs.
    
    Enhanced for RAG applications with:
    - Multiple citation format detection (numbered, author-date, URLs)
    - Citation format validation
    - Minimum citation requirements
    - Citation density analysis
    """

    PLUGIN_METADATA = {
        "name": "Citation Judge",
        "description": "Check for citations and attribution with format validation",
        "version": "2.0.0",
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config)
        cfg = config or {}
        self.require_citations = bool(cfg.get("require_citations", False))
        self.min_citations = int(cfg.get("min_citations", 1))
        self.validate_format = bool(cfg.get("validate_format", True))
        self.check_density = bool(cfg.get("check_density", False))
        self.min_density = float(cfg.get("min_density", 0.1))  # Citations per 100 words
        
        # Enhanced patterns for citations
        self.citation_patterns = [
            # Numbered citations: [1], [2-5], [1,2,3]
            re.compile(r"\[(\d+(?:[-,]\d+)*(?:,\s*\d+)*)\]"),
            # Author-date: (Author et al. 2024), (Author 2024)
            re.compile(r"\(([A-Z][A-Za-z]+(?:\s+et\s+al\.)?\s+\d{4})\)"),
            # Inline author-date: Author (2024), Author(2024)
            re.compile(r"([A-Z][A-Za-z]+)\s*\((\d{4})\)"),
            # URLs: http://..., https://...
            re.compile(r"(https?://[^\s\)]+)"),
            # DOI: doi:10.1234/...
            re.compile(r"(doi:10\.\d+/[^\s\)]+)", re.IGNORECASE),
            # arXiv: arXiv:1234.5678
            re.compile(r"(arxiv:\d+\.\d+)", re.IGNORECASE),
            # ISBN: ISBN 978-...
            re.compile(r"(ISBN[- ]?(?:\d[- ]?){10,13})", re.IGNORECASE),
        ]

    def evaluate(
        self,
        output: str,
        input_data: Any,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Check for citations in output with enhanced validation.
        
        Args:
            output: The text output to check
            input_data: Optional input data (not used)
            **kwargs: Additional arguments
            
        Returns:
            Dictionary with pass, score, reason, and details
        """
        citations_found: List[str] = []
        citation_types: Dict[str, int] = {}
        
        for pattern in self.citation_patterns:
            matches = list(pattern.finditer(output))
            if matches:
                for match in matches:
                    # Get full match or captured groups
                    if pattern.groups > 0:
                        # Use captured groups if available
                        groups = match.groups()
                        citation_text = groups[0] if groups else match.group()
                    else:
                        citation_text = match.group()
                    
                    if citation_text:
                        citations_found.append(citation_text)
                        # Track citation type
                        pattern_name = self._get_pattern_name(pattern)
                        citation_types[pattern_name] = citation_types.get(pattern_name, 0) + 1
        
        # Remove duplicates while preserving order
        unique_citations = []
        seen = set()
        for citation in citations_found:
            if citation not in seen:
                unique_citations.append(citation)
                seen.add(citation)
        
        citation_count = len(unique_citations)
        has_citations = citation_count >= self.min_citations
        
        # Calculate citation density (citations per 100 words)
        word_count = len(output.split())
        density = (citation_count / word_count * 100) if word_count > 0 else 0.0
        
        # Validate citation formats if requested
        format_valid = True
        format_issues: List[str] = []
        if self.validate_format and citations_found:
            format_valid, format_issues = self._validate_citation_formats(unique_citations)
        
        # Check citation density if requested
        density_pass = True
        if self.check_density:
            density_pass = density >= self.min_density
        
        # Determine overall pass status
        # If require_citations is False, always pass (just score lower)
        # If require_citations is True, must meet all requirements
        if self.require_citations:
            passes = has_citations and format_valid and (density_pass if self.check_density else True)
        else:
            # Not required - always pass, but score reflects quality
            passes = True
        
        # Calculate score
        score = 0.0
        if citation_count > 0:
            score = min(1.0, citation_count / max(1, self.min_citations))
            if format_valid:
                score *= 1.0
            else:
                score *= 0.8  # Penalize for format issues
            if self.check_density and density_pass:
                score *= 1.0
            elif self.check_density:
                score *= 0.9  # Slight penalty for low density
        else:
            score = 0.0
        
        reason = f"Found {citation_count} unique citation(s)"
        if not has_citations and self.require_citations:
            reason = f"Insufficient citations (required: {self.min_citations}, found: {citation_count})"
        elif not format_valid:
            reason = f"Citation format issues: {', '.join(format_issues[:2])}"
        elif self.check_density and not density_pass:
            reason = f"Low citation density ({density:.2f} per 100 words, required: {self.min_density})"
        
        return {
            "pass": passes,
            "score": score,
            "reason": reason,
            "details": {
                "citation_count": citation_count,
                "unique_citations": len(unique_citations),
                "min_required": self.min_citations,
                "require_citations": self.require_citations,
                "citations": unique_citations[:10],  # Limit to first 10
                "citation_types": citation_types,
                "format_valid": format_valid,
                "format_issues": format_issues,
                "density": density,
                "density_pass": density_pass if self.check_density else None,
                "word_count": word_count,
            },
        }
    
    def _get_pattern_name(self, pattern: re.Pattern) -> str:
        """Get a human-readable name for a citation pattern."""
        pattern_str = pattern.pattern
        if r"\[(\d+" in pattern_str:
            return "numbered"
        elif r"\([A-Z]" in pattern_str or r"[A-Z][A-Za-z]+\s*\(" in pattern_str:
            return "author_date"
        elif "http" in pattern_str:
            return "url"
        elif "doi" in pattern_str.lower():
            return "doi"
        elif "arxiv" in pattern_str.lower():
            return "arxiv"
        elif "isbn" in pattern_str.lower():
            return "isbn"
        else:
            return "other"
    
    def _validate_citation_formats(self, citations: List[str]) -> Tuple[bool, List[str]]:
        """
        Validate citation formats and return issues.
        
        Args:
            citations: List of citation strings
            
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues: List[str] = []
        
        for citation in citations:
            # Check for common format issues
            if citation.startswith("[") and not citation.endswith("]"):
                issues.append(f"Unclosed bracket: {citation[:20]}...")
            elif citation.startswith("(") and not citation.endswith(")"):
                issues.append(f"Unclosed parenthesis: {citation[:20]}...")
            elif "http" in citation.lower() and not citation.startswith(("http://", "https://")):
                issues.append(f"Malformed URL: {citation[:30]}...")
            # Check for empty or whitespace-only citations
            if not citation.strip():
                issues.append("Empty citation found")
        
        return len(issues) == 0, issues

