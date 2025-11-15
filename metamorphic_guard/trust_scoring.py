"""
Enhanced trust scoring system for RAG attribution and citation verification.

This module extends the existing trust scoring with citation verification,
attribution quality assessment, and source reliability scoring.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from .types import JSONDict


@dataclass
class Citation:
    """A citation or reference in a response."""
    
    text: str
    source: Optional[str] = None
    position: Optional[int] = None  # Character position in response
    confidence: float = 1.0  # Confidence in citation accuracy


@dataclass
class TrustScore:
    """Comprehensive trust score for a response."""
    
    overall_score: float  # 0.0 to 1.0
    attribution_score: float  # Quality of source attribution
    citation_score: float  # Quality of citations
    consistency_score: float  # Consistency with sources
    source_reliability: float  # Reliability of sources
    details: Dict[str, Any]


def extract_citations(response: str) -> List[Citation]:
    """
    Extract citations from a response.
    
    Looks for common citation patterns like [1], (source), etc.
    
    Args:
        response: Response text
    
    Returns:
        List of extracted citations
    """
    import re
    
    citations = []
    
    # Pattern 1: [1], [2], etc.
    pattern1 = r'\[(\d+)\]'
    for match in re.finditer(pattern1, response):
        citations.append(
            Citation(
                text=match.group(0),
                position=match.start(),
                confidence=0.8,
            )
        )
    
    # Pattern 2: (Source: ...)
    pattern2 = r'\(Source:\s*([^)]+)\)'
    for match in re.finditer(pattern2, response, re.IGNORECASE):
        citations.append(
            Citation(
                text=match.group(0),
                source=match.group(1),
                position=match.start(),
                confidence=0.9,
            )
        )
    
    # Pattern 3: URLs
    pattern3 = r'https?://[^\s]+'
    for match in re.finditer(pattern3, response):
        citations.append(
            Citation(
                text=match.group(0),
                source=match.group(0),
                position=match.start(),
                confidence=0.7,
            )
        )
    
    return citations


def verify_citations(
    citations: List[Citation],
    sources: Optional[List[str]] = None,
) -> float:
    """
    Verify that citations reference valid sources.
    
    Args:
        citations: List of citations
        sources: Available source list (if known)
    
    Returns:
        Verification score (0.0 to 1.0)
    """
    if not citations:
        return 0.0  # No citations = no verification
    
    if sources is None:
        # Can't verify without source list
        return 0.5
    
    verified = 0
    for citation in citations:
        if citation.source:
            # Check if source is in available sources
            if any(citation.source in source for source in sources):
                verified += 1
    
    return verified / len(citations) if citations else 0.0


def compute_attribution_score(
    response: str,
    sources: Optional[List[str]] = None,
    citations: Optional[List[Citation]] = None,
) -> float:
    """
    Compute attribution quality score.
    
    Measures how well the response attributes information to sources.
    
    Args:
        response: Response text
        sources: Available sources
        citations: Extracted citations (if already computed)
    
    Returns:
        Attribution score (0.0 to 1.0)
    """
    if citations is None:
        citations = extract_citations(response)
    
    if not citations:
        return 0.0  # No citations = poor attribution
    
    # Score based on citation count and quality
    citation_count_score = min(1.0, len(citations) / 3.0)  # Normalize to 3 citations
    
    # Verify citations if sources available
    verification_score = verify_citations(citations, sources) if sources else 0.5
    
    # Average citation confidence
    avg_confidence = sum(c.confidence for c in citations) / len(citations) if citations else 0.0
    
    # Combined score
    return (citation_count_score * 0.4 + verification_score * 0.4 + avg_confidence * 0.2)


def compute_source_reliability(
    sources: Optional[List[str]] = None,
) -> float:
    """
    Compute source reliability score.
    
    Args:
        sources: List of source identifiers/URLs
    
    Returns:
        Reliability score (0.0 to 1.0)
    """
    if not sources:
        return 0.5  # Unknown reliability
    
    # Simple heuristic: check for known reliable domains
    reliable_domains = [
        ".edu", ".gov", ".org", "wikipedia.org", "arxiv.org",
        "pubmed", "scholar.google", "ieee.org", "acm.org",
    ]
    
    reliable_count = 0
    for source in sources:
        source_lower = source.lower()
        if any(domain in source_lower for domain in reliable_domains):
            reliable_count += 1
    
    return reliable_count / len(sources) if sources else 0.5


def compute_consistency_score(
    response: str,
    sources: Optional[List[str]] = None,
) -> float:
    """
    Compute consistency score between response and sources.
    
    This is a simplified version - in practice, would compare
    response content with source content.
    
    Args:
        response: Response text
        sources: Source texts (if available)
    
    Returns:
        Consistency score (0.0 to 1.0)
    """
    # Simplified: if sources provided, check for overlap
    if not sources:
        return 0.5  # Can't verify without sources
    
    # Simple keyword overlap check
    response_words = set(response.lower().split())
    source_words = set()
    for source in sources:
        source_words.update(source.lower().split())
    
    if not source_words:
        return 0.5
    
    overlap = len(response_words & source_words)
    total_unique = len(response_words | source_words)
    
    return overlap / total_unique if total_unique > 0 else 0.0


def compute_trust_score(
    response: str,
    sources: Optional[List[str]] = None,
    citations: Optional[List[Citation]] = None,
) -> TrustScore:
    """
    Compute comprehensive trust score for a response.
    
    Args:
        response: Response text
        sources: Available sources
        citations: Extracted citations (if already computed)
    
    Returns:
        TrustScore with overall and component scores
    """
    if citations is None:
        citations = extract_citations(response)
    
    attribution_score = compute_attribution_score(response, sources, citations)
    citation_score = verify_citations(citations, sources)
    consistency_score = compute_consistency_score(response, sources)
    source_reliability = compute_source_reliability(sources)
    
    # Weighted overall score
    overall_score = (
        attribution_score * 0.3 +
        citation_score * 0.3 +
        consistency_score * 0.2 +
        source_reliability * 0.2
    )
    
    return TrustScore(
        overall_score=overall_score,
        attribution_score=attribution_score,
        citation_score=citation_score,
        consistency_score=consistency_score,
        source_reliability=source_reliability,
        details={
            "citation_count": len(citations),
            "sources_count": len(sources) if sources else 0,
            "citations": [
                {
                    "text": c.text,
                    "source": c.source,
                    "confidence": c.confidence,
                }
                for c in citations
            ],
        },
    )

