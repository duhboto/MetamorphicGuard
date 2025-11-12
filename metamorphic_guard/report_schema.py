"""Pydantic models for Metamorphic Guard reports."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from pydantic import BaseModel, Field
except ImportError:
    # Fallback if pydantic not available
    BaseModel = object  # type: ignore
    Field = lambda *args, **kwargs: None  # type: ignore


class Violation(BaseModel):
    """A property or metamorphic relation violation."""

    test_case: int
    property: Optional[str] = None
    relation: Optional[str] = None
    input: Optional[str] = None
    output: Optional[str] = None
    relation_output: Optional[str] = None
    error: Optional[str] = None


class BaselineMetrics(BaseModel):
    """Baseline evaluation metrics."""

    total: int
    passes: int
    pass_rate: float
    prop_violations: List[Violation] = Field(default_factory=list)
    mr_violations: List[Violation] = Field(default_factory=list)


class CandidateMetrics(BaseModel):
    """Candidate evaluation metrics."""

    total: int
    passes: int
    pass_rate: float
    prop_violations: List[Violation] = Field(default_factory=list)
    mr_violations: List[Violation] = Field(default_factory=list)


class Decision(BaseModel):
    """Adoption decision."""

    adopt: bool
    reason: Optional[str] = None


class JobMetadata(BaseModel):
    """Job execution metadata."""

    duration_seconds: Optional[float] = None
    seed: Optional[int] = None
    n: Optional[int] = None
    run_id: Optional[str] = None


class TrustScores(BaseModel):
    """Trust scores for RAG evaluations."""

    score: float
    flags: Dict[str, bool] = Field(default_factory=dict)
    count: Optional[int] = None
    individual_scores: Optional[List[Dict[str, Any]]] = None
    details: Optional[Dict[str, Any]] = None


class Provenance(BaseModel):
    """Provenance metadata for auditability and reproducibility."""

    library_version: Optional[str] = Field(
        None, description="Metamorphic Guard library version"
    )
    git_sha: Optional[str] = Field(None, description="Git commit SHA")
    git_dirty: Optional[bool] = Field(None, description="Whether working tree has uncommitted changes")
    python_version: Optional[str] = Field(None, description="Python version")
    platform: Optional[str] = Field(None, description="Platform identifier")
    hostname: Optional[str] = Field(None, description="Hostname where evaluation ran")
    executable: Optional[str] = Field(None, description="Python executable path")
    mr_ids: Optional[List[str]] = Field(
        None, description="List of metamorphic relation identifiers"
    )
    spec_fingerprint: Optional[Dict[str, Any]] = Field(
        None, description="Hash-based fingerprint of task specification"
    )
    environment: Optional[Dict[str, str]] = Field(
        None, description="Runtime environment metadata"
    )
    sandbox: Optional[Dict[str, Any]] = Field(
        None, description="Sandbox configuration and provenance details"
    )


class Report(BaseModel):
    """Complete Metamorphic Guard evaluation report."""

    task: str
    baseline: BaselineMetrics
    candidate: CandidateMetrics
    decision: Decision
    delta_pass_rate: Optional[float] = None
    delta_ci: Optional[List[float]] = None
    relative_risk: Optional[float] = None
    relative_risk_ci: Optional[List[float]] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    job_metadata: Optional[JobMetadata] = None
    monitors: Dict[str, Any] = Field(default_factory=dict)
    policy_version: Optional[str] = None
    trust_scores: Optional[Dict[str, TrustScores]] = None
    llm_metrics: Optional[Dict[str, Any]] = None
    provenance: Optional[Provenance] = None

    class Config:
        """Pydantic config."""

        extra = "allow"  # Allow additional fields for extensibility


def validate_report(data: Dict[str, Any]) -> Report:
    """
    Validate a report dictionary against the Report schema.

    Args:
        data: Report dictionary to validate

    Returns:
        Validated Report model

    Raises:
        ValidationError: If the data doesn't match the schema
    """
    return Report(**data)


def report_to_dict(report: Report) -> Dict[str, Any]:
    """
    Convert a Report model to a dictionary.

    Args:
        report: Report model instance

    Returns:
        Dictionary representation
    """
    return report.model_dump(exclude_none=False)

