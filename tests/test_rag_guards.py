"""
Tests for RAG-specific guards (attribution and citation verification).
"""

import pytest

from metamorphic_guard.judges.rag_guards import (
    AttributionJudge,
    CitationVerificationJudge,
)
from metamorphic_guard.judges.structured import CitationJudge


class TestCitationJudge:
    """Test enhanced CitationJudge."""
    
    def test_citation_judge_basic(self):
        """Test basic citation detection."""
        judge = CitationJudge({"require_citations": False})
        output = "This is a test [1] with citations [2]."
        result = judge.evaluate(output, None)
        assert result["pass"] is True
        assert result["details"]["citation_count"] >= 2
        assert result["score"] > 0
    
    def test_citation_judge_author_date(self):
        """Test author-date citation format."""
        judge = CitationJudge({"require_citations": False})
        output = "According to Smith (2024), this is correct. See also (Jones et al. 2023)."
        result = judge.evaluate(output, None)
        assert result["pass"] is True
        assert result["details"]["citation_count"] >= 2
    
    def test_citation_judge_urls(self):
        """Test URL citation format."""
        judge = CitationJudge({"require_citations": False})
        output = "See https://example.com/article for more information."
        result = judge.evaluate(output, None)
        assert result["pass"] is True
        assert "url" in str(result["details"].get("citation_types", {}))
    
    def test_citation_judge_format_validation(self):
        """Test citation format validation."""
        judge = CitationJudge({"validate_format": True, "require_citations": False})
        output = "This has [1 and [2] citations."  # One unclosed bracket
        result = judge.evaluate(output, None)
        # Should detect format issues
        assert "format_valid" in result["details"]
    
    def test_citation_judge_density_check(self):
        """Test citation density checking."""
        judge = CitationJudge({
            "check_density": True,
            "min_density": 0.5,  # 0.5 citations per 100 words
            "require_citations": False,
        })
        output = " ".join(["word"] * 200) + " [1] [2]"
        result = judge.evaluate(output, None)
        assert "density" in result["details"]
        assert result["details"]["density"] is not None


class TestAttributionJudge:
    """Test AttributionJudge."""
    
    def test_attribution_judge_basic(self):
        """Test basic attribution detection."""
        judge = AttributionJudge({"require_attribution": False})
        output = "According to Smith, this is correct."
        result = judge.evaluate(output, None)
        assert result["pass"] is True
        assert result["details"]["attribution_count"] >= 1
    
    def test_attribution_judge_with_sources(self):
        """Test attribution with source documents."""
        judge = AttributionJudge({
            "require_attribution": True,
            "min_overlap_ratio": 0.1,
        })
        output = "According to the source, this is important information."
        sources = ["This is important information from the source document."]
        result = judge.evaluate(output, {"sources": sources})
        assert result["details"]["overlap_ratio"] > 0
        assert "overlap_details" in result["details"]
    
    def test_attribution_judge_quotes(self):
        """Test quote attribution checking."""
        judge = AttributionJudge({
            "check_quotes": True,
            "require_attribution": False,
        })
        output = 'According to Smith, "This is a quoted statement."'
        result = judge.evaluate(output, None)
        assert result["details"]["quote_count"] >= 1
        assert "quote_attribution_ratio" in result["details"]
    
    def test_attribution_judge_no_attribution(self):
        """Test output without attribution."""
        judge = AttributionJudge({"require_attribution": True})
        output = "This is output without any attribution phrases."
        result = judge.evaluate(output, None)
        assert result["pass"] is False
        assert result["details"]["attribution_count"] == 0


class TestCitationVerificationJudge:
    """Test CitationVerificationJudge."""
    
    def test_citation_verification_basic(self):
        """Test basic citation verification."""
        judge = CitationVerificationJudge({"require_verification": False})
        output = "This has [1] and [2] citations."
        sources = ["Source 1", "Source 2"]
        result = judge.evaluate(output, {"sources": sources})
        assert result["pass"] is True
        assert result["details"]["verified_count"] == 2
    
    def test_citation_verification_invalid(self):
        """Test citation verification with invalid citations."""
        judge = CitationVerificationJudge({"require_verification": True})
        output = "This has [1] and [5] citations."  # [5] is invalid (only 2 sources)
        sources = ["Source 1", "Source 2"]
        result = judge.evaluate(output, {"sources": sources})
        assert result["pass"] is False
        assert len(result["details"]["invalid_citations"]) > 0
    
    def test_citation_verification_strict(self):
        """Test strict citation verification."""
        judge = CitationVerificationJudge({
            "require_verification": True,
            "strict_matching": True,
        })
        output = "This has [1] citation."
        sources = ["Source 1", "Source 2"]
        # Only allow citation [2] (1-indexed, so index 2)
        result = judge.evaluate(output, {
            "sources": sources,
            "source_indices": [2],  # Only citation [2] is allowed
        })
        # [1] should be unverified in strict mode since only [2] is allowed
        assert len(result["details"]["unverified_citations"]) > 0 or result["pass"] is False
    
    def test_citation_verification_no_sources(self):
        """Test citation verification without sources."""
        judge = CitationVerificationJudge({"require_verification": False})
        output = "This has [1] citation."
        result = judge.evaluate(output, None)
        # Should still work but can't verify
        assert result["details"]["citation_count"] >= 1

