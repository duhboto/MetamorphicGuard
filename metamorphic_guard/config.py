from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class QueueSettings(BaseModel):
    backend: str = Field(default="redis")
    url: Optional[str] = None
    batch_size: Optional[int] = Field(default=None, ge=1)
    compress: Optional[bool] = None


class AlertSettings(BaseModel):
    webhooks: List[str] = Field(default_factory=list)


class EvaluatorConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)  # Allow both field name and alias

    task: str
    baseline: str
    candidate: str
    n: int = Field(default=400, ge=1)
    seed: int = 42
    timeout_s: float = Field(default=2.0, gt=0)
    mem_mb: int = Field(default=512, gt=0)
    alpha: float = Field(default=0.05, gt=0, lt=1)
    min_delta: float = Field(default=0.02, alias="improve_delta")  # improve_delta is deprecated
    min_pass_rate: float = Field(default=0.80, ge=0, le=1)
    violation_cap: int = Field(default=25, ge=1)
    parallel: int = Field(default=1, ge=1)
    bootstrap_samples: int = Field(default=1000, ge=1)
    ci_method: str = Field(default="bootstrap")
    relation_correction: Optional[str] = Field(default=None)
    rr_ci_method: str = Field(default="log")
    monitors: List[str] = Field(default_factory=list)
    dispatcher: str = Field(default="local")
    queue: Optional[QueueSettings] = None
    alerts: AlertSettings = Field(default_factory=AlertSettings)
    executor: Optional[str] = None
    executor_config: Optional[dict] = None
    policy_version: Optional[str] = None
    policy: Optional[str] = None
    power_target: float = Field(default=0.8, gt=0, lt=1)
    log_json: Optional[bool] = None
    log_file: Optional[str] = None
    metrics_enabled: Optional[bool] = None
    metrics_port: Optional[int] = Field(default=None, ge=0)
    metrics_host: str = "0.0.0.0"
    failed_artifact_limit: Optional[int] = Field(default=None, ge=0)
    failed_artifact_ttl_days: Optional[int] = Field(default=None, ge=0)
    sandbox_plugins: Optional[bool] = None
    stability: int = Field(default=1, ge=1)
    adaptive_testing: bool = Field(default=False)
    adaptive_min_sample_size: int = Field(default=50, ge=10)
    adaptive_check_interval: int = Field(default=50, ge=10)
    adaptive_power_threshold: float = Field(default=0.95, gt=0.0, le=1.0)
    adaptive_max_sample_size: Optional[int] = Field(default=None, ge=10)

    @field_validator("dispatcher")
    @classmethod
    def _validate_dispatcher(cls, value: str) -> str:
        allowed = {"local", "queue"}
        if value not in allowed:
            raise ValueError(f"dispatcher must be one of {sorted(allowed)}")
        return value

    @field_validator("monitors", mode="after")
    @classmethod
    def _strip_monitors(cls, value: List[str]) -> List[str]:
        if not value:
            return []
        return [item.strip() for item in value]

    @field_validator("relation_correction")
    @classmethod
    def _normalize_relation_correction(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not normalized or normalized in {"none", "null"}:
            return None
        if normalized in {"holm", "holm-bonferroni"}:
            return "holm"
        if normalized == "hochberg":
            return "hochberg"
        if normalized in {"fdr", "bh", "benjamini-hochberg"}:
            return "fdr"
        raise ValueError("relation_correction must be one of: holm, hochberg, fdr, none.")


class ConfigLoadError(Exception):
    """Raised when the configuration file fails validation."""


def load_config(path: Path) -> EvaluatorConfig:
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:  # pragma: no cover - filesystem errors
        raise ConfigLoadError(f"Failed to read config '{path}': {exc}") from exc

    import tomllib

    try:
        data = tomllib.loads(content)
    except Exception as exc:
        raise ConfigLoadError(f"Failed to parse TOML '{path}': {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigLoadError("Config must decode to a TOML table.")

    block = data.get("metamorphic_guard", data)
    try:
        return EvaluatorConfig.model_validate(block)
    except ValidationError as exc:
        raise ConfigLoadError(str(exc)) from exc
