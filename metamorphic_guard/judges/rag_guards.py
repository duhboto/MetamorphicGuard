"""
RAG-specific guards for citation verification and attribution overlap.

These judges are specialized for Retrieval-Augmented Generation (RAG) applications,
where outputs should cite sources and attribute content to retrieved documents.
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from .__init__ import LLMJudge


class AttributionJudge(LLMJudge):
    """
    Judge that checks attribution overlap between output and source documents.
    
    For RAG applications, this judge verifies that:
    1. Content in the output can be traced to source documents
    2. Attribution statements match the source content
    3. Quoted content is properly attributed
    """

    PLUGIN_METADATA = {
        "name": "Attribution Judge",
        "description": "Verify attribution overlap and content matching for RAG outputs",
        "version": "1.0.0",
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config)
        cfg = config or {}
        self.require_attribution = bool(cfg.get("require_attribution", True))
        self.min_overlap_ratio = float(cfg.get("min_overlap_ratio", 0.3))
        self.check_quotes = bool(cfg.get("check_quotes", True))
        self.min_quote_attribution = float(cfg.get("min_quote_attribution", 0.8))
        
        # Patterns for attribution phrases
        self.attribution_patterns = [
            re.compile(r"according to\s+([^,\.]+)", re.IGNORECASE),
            re.compile(r"as stated (?:by|in)\s+([^,\.]+)", re.IGNORECASE),
            re.compile(r"as (?:mentioned|noted|reported)\s+(?:by|in)\s+([^,\.]+)", re.IGNORECASE),
            re.compile(r"per\s+([^,\.]+)", re.IGNORECASE),
            re.compile(r"cited in\s+([^,\.]+)", re.IGNORECASE),
            re.compile(r"source[:\s]+([^,\.]+)", re.IGNORECASE),
            re.compile(r"from\s+([^,\.]+)", re.IGNORECASE),
        ]
        
        # Patterns for quoted content
        self.quote_patterns = [
            re.compile(r'"([^"]+)"'),  # Double quotes
            re.compile(r"'([^']+)'"),  # Single quotes
            re.compile(r"``([^'']+)''"),  # LaTeX-style quotes
        ]

    def evaluate(
        self,
        output: str,
        input_data: Any,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Evaluate attribution in output.
        
        Args:
            output: The text output to check
            input_data: Optional input data (may contain source documents)
            **kwargs: Additional arguments (may include 'sources' key with source documents)
            
        Returns:
            Dictionary with pass, score, reason, and details
        """
        sources: List[str] = []
        if isinstance(input_data, dict):
            sources = input_data.get("sources", [])
        elif isinstance(input_data, list):
            sources = input_data
        elif kwargs.get("sources"):
            sources = kwargs["sources"]
        
        # Extract attribution phrases
        attributions_found = self._extract_attributions(output)
        
        # Extract quoted content
        quotes = self._extract_quotes(output)
        
        # Calculate attribution overlap if sources are provided
        overlap_ratio = 0.0
        overlap_details: Dict[str, Any] = {}
        if sources:
            overlap_ratio, overlap_details = self._calculate_overlap(output, sources)
        
        # Check quote attribution
        quote_attribution_ratio = 0.0
        quote_details: Dict[str, Any] = {}
        if self.check_quotes and quotes:
            quote_attribution_ratio, quote_details = self._check_quote_attribution(
                output, quotes, attributions_found
            )
        
        # Determine pass status
        passes = True
        issues: List[str] = []
        
        if self.require_attribution:
            if len(attributions_found) == 0:
                passes = False
                issues.append("No attribution phrases found")
            
            if sources and overlap_ratio < self.min_overlap_ratio:
                passes = False
                issues.append(
                    f"Low attribution overlap ({overlap_ratio:.2%}, required: {self.min_overlap_ratio:.2%})"
                )
            
            if self.check_quotes and quotes:
                if quote_attribution_ratio < self.min_quote_attribution:
                    passes = False
                    issues.append(
                        f"Low quote attribution ({quote_attribution_ratio:.2%}, "
                        f"required: {self.min_quote_attribution:.2%})"
                    )
        
        # Calculate score
        score = 0.0
        if len(attributions_found) > 0:
            score = 0.4  # Base score for having attributions
            if sources:
                score += 0.3 * min(1.0, overlap_ratio / self.min_overlap_ratio)
            if self.check_quotes and quotes:
                score += 0.3 * min(1.0, quote_attribution_ratio / self.min_quote_attribution)
        else:
            score = 0.1 if not self.require_attribution else 0.0
        
        reason = f"Found {len(attributions_found)} attribution(s)"
        if issues:
            reason = "; ".join(issues)
        elif sources:
            reason += f", {overlap_ratio:.1%} overlap with sources"
        
        return {
            "pass": passes,
            "score": min(1.0, score),
            "reason": reason,
            "details": {
                "attribution_count": len(attributions_found),
                "attributions": attributions_found[:10],
                "quote_count": len(quotes),
                "overlap_ratio": overlap_ratio,
                "overlap_details": overlap_details,
                "quote_attribution_ratio": quote_attribution_ratio,
                "quote_details": quote_details,
                "sources_provided": len(sources) > 0,
                "source_count": len(sources),
            },
        }
    
    def _extract_attributions(self, text: str) -> List[str]:
        """Extract attribution phrases from text."""
        attributions: List[str] = []
        for pattern in self.attribution_patterns:
            matches = pattern.finditer(text)
            for match in matches:
                if match.groups():
                    attribution = match.group(1).strip()
                    if attribution:
                        attributions.append(attribution)
        return attributions
    
    def _extract_quotes(self, text: str) -> List[str]:
        """Extract quoted content from text."""
        quotes: List[str] = []
        for pattern in self.quote_patterns:
            matches = pattern.finditer(text)
            for match in matches:
                if match.groups():
                    quote = match.group(1).strip()
                    if len(quote) > 10:  # Only consider substantial quotes
                        quotes.append(quote)
        return quotes
    
    def _calculate_overlap(
        self, output: str, sources: List[str]
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Calculate overlap ratio between output and source documents.
        
        Uses simple word overlap as a proxy for content matching.
        More sophisticated implementations could use semantic similarity.
        """
        # Tokenize output and sources
        output_words = set(self._tokenize(output.lower()))
        source_words: Set[str] = set()
        for source in sources:
            source_words.update(self._tokenize(str(source).lower()))
        
        # Calculate overlap
        if not output_words:
            return 0.0, {"overlapping_words": 0, "output_words": 0, "source_words": 0}
        
        overlapping_words = output_words.intersection(source_words)
        overlap_ratio = len(overlapping_words) / len(output_words) if output_words else 0.0
        
        return overlap_ratio, {
            "overlapping_words": len(overlapping_words),
            "output_words": len(output_words),
            "source_words": len(source_words),
            "overlap_ratio": overlap_ratio,
        }
    
    def _check_quote_attribution(
        self, output: str, quotes: List[str], attributions: List[str]
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Check if quotes are properly attributed.
        
        A quote is considered attributed if there's an attribution phrase
        near the quote (within 50 characters).
        """
        if not quotes:
            return 1.0, {"attributed_quotes": 0, "total_quotes": 0}
        
        attributed_count = 0
        quote_positions: List[Tuple[int, int]] = []
        
        # Find quote positions in output
        for quote in quotes:
            pos = output.find(quote)
            if pos >= 0:
                quote_positions.append((pos, pos + len(quote)))
        
        # Find attribution positions
        attribution_positions: List[int] = []
        for attribution in attributions:
            # Find all positions of this attribution phrase
            for match in re.finditer(re.escape(attribution), output, re.IGNORECASE):
                attribution_positions.append(match.start())
        
        # Check if quotes have nearby attributions
        for quote_start, quote_end in quote_positions:
            has_attribution = False
            for attr_pos in attribution_positions:
                # Check if attribution is within 50 characters of quote
                distance = min(
                    abs(attr_pos - quote_start),
                    abs(attr_pos - quote_end),
                    abs(attr_pos - (quote_start + quote_end) // 2),
                )
                if distance <= 50:
                    has_attribution = True
                    break
            
            if has_attribution:
                attributed_count += 1
        
        ratio = attributed_count / len(quotes) if quotes else 0.0
        
        return ratio, {
            "attributed_quotes": attributed_count,
            "total_quotes": len(quotes),
            "attribution_ratio": ratio,
        }
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization (split on whitespace and punctuation)."""
        # Remove punctuation and split
        text = re.sub(r"[^\w\s]", " ", text)
        return [word for word in text.split() if word]


class CitationVerificationJudge(LLMJudge):
    """
    Judge that verifies citations against source documents.
    
    For RAG applications, this checks that:
    1. Citations reference actual source documents
    2. Citation numbers/IDs match provided sources
    3. Cited content can be found in sources
    """

    PLUGIN_METADATA = {
        "name": "Citation Verification Judge",
        "description": "Verify citations match source documents",
        "version": "1.0.0",
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config)
        cfg = config or {}
        self.require_verification = bool(cfg.get("require_verification", True))
        self.strict_matching = bool(cfg.get("strict_matching", False))
        
        # Pattern for numbered citations
        self.citation_pattern = re.compile(r"\[(\d+)\]")

    def evaluate(
        self,
        output: str,
        input_data: Any,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Verify citations against source documents.
        
        Args:
            output: The text output with citations
            input_data: Optional input data (may contain sources with indices)
            **kwargs: Additional arguments (may include 'sources' key)
            
        Returns:
            Dictionary with pass, score, reason, and details
        """
        # Extract sources
        sources: List[str] = []
        source_indices: Set[int] = set()
        
        if isinstance(input_data, dict):
            sources = input_data.get("sources", [])
            provided_indices = input_data.get("source_indices")
            if provided_indices is not None:
                source_indices = set(provided_indices)
            else:
                # Default: allow all sources (1-indexed for citations)
                source_indices = set(range(1, len(sources) + 1))
        elif isinstance(input_data, list):
            sources = input_data
            # Default: allow all sources (1-indexed for citations)
            source_indices = set(range(1, len(sources) + 1))
        elif kwargs.get("sources"):
            sources = kwargs["sources"]
            provided_indices = kwargs.get("source_indices")
            if provided_indices is not None:
                source_indices = set(provided_indices)
            else:
                # Default: allow all sources (1-indexed for citations)
                source_indices = set(range(1, len(sources) + 1))
        else:
            # No sources provided - default to allowing all citations
            source_indices = set()
        
        # Extract citations from output (these are 1-indexed by convention)
        citations = self._extract_citations(output)
        
        # Verify citations
        verified_count = 0
        invalid_citations: List[int] = []
        unverified_citations: List[int] = []
        
        for citation_num in citations:
            # Citations are typically 1-indexed in text ([1], [2], etc.)
            # If no source_indices specified, assume all citations are valid if sources exist
            if not source_indices:
                # No restrictions - allow if citation is within source range
                if sources and 1 <= citation_num <= len(sources):
                    verified_count += 1
                else:
                    invalid_citations.append(citation_num)
            elif citation_num in source_indices:
                # Citation is in allowed indices
                verified_count += 1
            else:
                # Citation is not in allowed indices
                if sources and 1 <= citation_num <= len(sources):
                    # Citation exists but not in allowed set
                    if not self.strict_matching:
                        verified_count += 1
                    else:
                        unverified_citations.append(citation_num)
                else:
                    # Citation is out of range
                    invalid_citations.append(citation_num)
        
        # Calculate verification ratio
        verification_ratio = (
            verified_count / len(citations) if citations else 1.0
        )
        
        # Determine pass status
        passes = True
        if self.require_verification:
            if invalid_citations:
                passes = False
            elif self.strict_matching and unverified_citations:
                passes = False
        
        # Calculate score
        score = verification_ratio if citations else 0.0
        
        reason = f"Verified {verified_count}/{len(citations)} citations"
        if invalid_citations:
            reason = f"Invalid citations: {invalid_citations[:5]}"
        elif unverified_citations:
            reason = f"Unverified citations: {unverified_citations[:5]}"
        
        return {
            "pass": passes,
            "score": score,
            "reason": reason,
            "details": {
                "citation_count": len(citations),
                "verified_count": verified_count,
                "invalid_citations": invalid_citations,
                "unverified_citations": unverified_citations,
                "verification_ratio": verification_ratio,
                "sources_provided": len(sources) > 0,
                "source_count": len(sources),
                "source_indices": list(source_indices),
            },
        }
    
    def _extract_citations(self, text: str) -> List[int]:
        """Extract citation numbers from text."""
        citations: List[int] = []
        matches = self.citation_pattern.finditer(text)
        for match in matches:
            if match.groups():
                try:
                    citation_num = int(match.group(1))
                    citations.append(citation_num)
                except ValueError:
                    pass
        return citations

