from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PolicyVersion(str, Enum):
    V1 = "v1"
    V2 = "v2"


class GatingMethod(str, Enum):
    BOOTSTRAP = "bootstrap"
    BOOTSTRAP_BCA = "bootstrap_bca"
    BAYESIAN = "bayesian"
    WILSON = "wilson"
    NEWCOMBE = "newcombe"


class GatingConfigV1(BaseModel):
    """V1 Gating Configuration Schema."""
    model_config = ConfigDict(extra="forbid")

    min_delta: float = Field(default=0.02)
    min_pass_rate: float = Field(default=0.80, ge=0.0, le=1.0)
    alpha: float = Field(default=0.05, gt=0.0, lt=1.0)
    power_target: float = Field(default=0.8, gt=0.0, lt=1.0)
    violation_cap: Optional[int] = Field(default=None, ge=0)


class EvaluationConfigV2(BaseModel):
    """V2 Evaluation Settings."""
    model_config = ConfigDict(extra="forbid")

    n: int = Field(default=400, ge=1)
    alpha: float = Field(default=0.05, gt=0.0, lt=1.0)
    bootstrap_samples: int = Field(default=5000, ge=100)
    hierarchical: bool = Field(default=False)


class GateConfigV2(BaseModel):
    """V2 Gate Settings."""
    model_config = ConfigDict(extra="forbid")

    method: GatingMethod = Field(default=GatingMethod.BOOTSTRAP)
    threshold: float = Field(default=0.0)
    allow_flaky: bool = Field(default=False)
    min_pass_rate: float = Field(default=0.80, ge=0.0, le=1.0)


class MonitorConfigV2(BaseModel):
    """V2 Monitor Settings."""
    model_config = ConfigDict(extra="forbid")

    list: List[str] = Field(default_factory=list)


class PolicyV1(BaseModel):
    """Schema for V1 policies."""
    model_config = ConfigDict(extra="ignore")  # V1 allowed top-level extras

    name: Optional[str] = None
    description: Optional[str] = None
    version: Literal["v1"] = "v1"
    gating: GatingConfigV1


class PolicyV2(BaseModel):
    """Schema for V2 policies (Structured)."""
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    description: Optional[str] = None
    version: Literal["v2"] = "v2"
    
    evaluation: Optional[EvaluationConfigV2] = None
    gate: Optional[GateConfigV2] = None
    monitors: Optional[MonitorConfigV2] = None
    
    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        if v != "v2":
            raise ValueError("Version must be 'v2'")
        return v


PolicySchema = Union[PolicyV1, PolicyV2]


