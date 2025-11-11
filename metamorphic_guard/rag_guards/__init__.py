"""RAG trust scoring for groundedness checks."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

__version__ = "1.0.0"

__all__ = ["assess", "TrustScore", "TrustFlags"]


class TrustFlags:
    """Flags indicating specific trust issues."""

    def __init__(
        self,
        citation_correct: bool = True,
        citation_complete: bool = True,
        coverage_sufficient: bool = True,
        answerable: bool = True,
        novel_content: bool = False,
    ) -> None:
        self.citation_correct = citation_correct
        self.citation_complete = citation_complete
        self.coverage_sufficient = coverage_sufficient
        self.answerable = answerable
        self.novel_content = novel_content

    def to_dict(self) -> Dict[str, bool]:
        """Convert to dictionary."""
        return {
            "citation_correct": self.citation_correct,
            "citation_complete": self.citation_complete,
            "coverage_sufficient": self.coverage_sufficient,
            "answerable": self.answerable,
            "novel_content": self.novel_content,
        }


class TrustScore:
    """Trust score for RAG answer."""

    def __init__(
        self,
        score: float,
        flags: TrustFlags,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Initialize trust score.

        Args:
            score: Overall trust score (0.0-1.0, higher is better)
            flags: Trust flags indicating specific issues
            details: Additional scoring details
        """
        self.score = max(0.0, min(1.0, score))
        self.flags = flags
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "score": self.score,
            "flags": self.flags.to_dict(),
            "details": self.details,
        }


def assess(
    question: str,
    answer: str,
    sources: Sequence[str],
    checks: Optional[Sequence[str]] = None,
) -> tuple[TrustScore, TrustFlags]:
    """
    Assess trust score for a RAG answer.

    Args:
        question: The question asked
        answer: The answer generated
        sources: Source documents/chunks used
        checks: Optional list of checks to perform (default: all)

    Returns:
        Tuple of (TrustScore, TrustFlags)
    """
    if checks is None:
        checks = ["citation", "faithfulness", "coverage", "answerability", "novelty"]

    flags = TrustFlags()
    details: Dict[str, Any] = {}
    score_components: List[float] = []

    # Citation correctness check
    if "citation" in checks:
        citation_score, citation_correct, citation_complete = _check_citations(
            answer, sources
        )
        flags.citation_correct = citation_correct
        flags.citation_complete = citation_complete
        details["citation"] = {
            "score": citation_score,
            "correct": citation_correct,
            "complete": citation_complete,
        }
        score_components.append(citation_score)

    # Faithfulness check (answer is grounded in sources)
    if "faithfulness" in checks:
        faithfulness_score = _check_faithfulness(answer, sources)
        details["faithfulness"] = {"score": faithfulness_score}
        score_components.append(faithfulness_score)

    # Coverage check (sources cover the question)
    if "coverage" in checks:
        coverage_score, coverage_sufficient = _check_coverage(question, sources)
        flags.coverage_sufficient = coverage_sufficient
        details["coverage"] = {
            "score": coverage_score,
            "sufficient": coverage_sufficient,
        }
        score_components.append(coverage_score)

    # Answerability check (question can be answered from sources)
    if "answerability" in checks:
        answerability_score, answerable = _check_answerability(question, sources)
        flags.answerable = answerable
        details["answerability"] = {"score": answerability_score, "answerable": answerable}
        score_components.append(answerability_score)

    # Novelty check (detect hallucinated content)
    if "novelty" in checks:
        novelty_score, novel_content = _check_novelty(answer, sources)
        flags.novel_content = novel_content
        details["novelty"] = {"score": novelty_score, "novel": novel_content}
        score_components.append(novelty_score)

    # Compute overall score (weighted average)
    overall_score = sum(score_components) / len(score_components) if score_components else 0.0

    return TrustScore(overall_score, flags, details), flags


def _check_citations(answer: str, sources: Sequence[str]) -> tuple[float, bool, bool]:
    """Check citation correctness and completeness."""
    import re

    # Find citations in answer (e.g., [1], [2], or (source1))
    citation_pattern = r"\[(\d+)\]|\(([^)]+)\)"
    citations = re.findall(citation_pattern, answer)

    if not citations:
        return 0.0, False, False

    # Check if citations reference valid sources
    valid_citations = 0
    for citation in citations:
        if citation[0]:  # Numbered citation
            idx = int(citation[0]) - 1
            if 0 <= idx < len(sources):
                valid_citations += 1
        else:  # Text citation
            if citation[1] in sources:
                valid_citations += 1

    correctness = valid_citations / len(citations) if citations else 0.0
    completeness = len(citations) >= min(len(sources), 3)  # At least 3 citations or all sources

    return correctness, correctness > 0.8, completeness


def _check_faithfulness(answer: str, sources: Sequence[str]) -> float:
    """Check if answer is faithful to sources (simple overlap-based)."""
    if not sources:
        return 0.0

    # Simple word overlap metric
    answer_words = set(answer.lower().split())
    source_words = set()
    for source in sources:
        source_words.update(source.lower().split())

    if not source_words:
        return 0.0

    overlap = len(answer_words & source_words) / len(answer_words) if answer_words else 0.0
    return min(1.0, overlap * 1.5)  # Scale up slightly


def _check_coverage(question: str, sources: Sequence[str]) -> tuple[float, bool]:
    """Check if sources cover the question."""
    if not sources:
        return 0.0, False

    question_words = set(question.lower().split())
    source_text = " ".join(sources).lower()
    source_words = set(source_text.split())

    # Check if key question terms appear in sources
    key_terms = [w for w in question_words if len(w) > 3]  # Filter short words
    if not key_terms:
        return 1.0, True  # No key terms to check

    covered = sum(1 for term in key_terms if term in source_words)
    coverage = covered / len(key_terms)
    sufficient = coverage >= 0.7

    return coverage, sufficient


def _check_answerability(question: str, sources: Sequence[str]) -> tuple[float, bool]:
    """Check if question can be answered from sources."""
    if not sources:
        return 0.0, False

    # Simple heuristic: if sources have substantial content and question is clear
    total_length = sum(len(s) for s in sources)
    question_length = len(question)

    # Sources should be at least 3x question length
    answerable = total_length >= question_length * 3
    score = min(1.0, total_length / (question_length * 3)) if question_length > 0 else 0.0

    return score, answerable


def _check_novelty(answer: str, sources: Sequence[str]) -> tuple[float, bool]:
    """Detect novel (potentially hallucinated) content in answer."""
    if not sources:
        return 0.0, True  # No sources = all novel

    # Check for novel sentences/phrases
    answer_sentences = answer.split(".")
    source_text = " ".join(sources).lower()

    novel_count = 0
    for sentence in answer_sentences:
        sentence_lower = sentence.lower().strip()
        if len(sentence_lower) > 10:  # Ignore very short sentences
            # Check if sentence appears in sources (fuzzy)
            words = sentence_lower.split()
            if len(words) >= 3:
                # Check if at least 50% of words appear in sources
                matching_words = sum(1 for w in words if w in source_text)
                if matching_words / len(words) < 0.5:
                    novel_count += 1

    novelty_ratio = novel_count / len(answer_sentences) if answer_sentences else 0.0
    has_novel = novelty_ratio > 0.2

    # Trust score: lower novelty is better
    trust_score = 1.0 - min(1.0, novelty_ratio * 2)

    return trust_score, has_novel

