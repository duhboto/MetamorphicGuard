"""
Utilities for loading gating policy files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import tomllib

from .errors import PolicyError


class PolicyLoadError(PolicyError):
    """Raised when a policy file cannot be loaded or parsed."""

    def __init__(self, message: str, *, original: Exception | None = None) -> None:
        super().__init__(
            message,
            error_code="POLICY_LOAD_ERROR",
            original=original,
        )


class PolicyParseError(PolicyError):
    """Raised when a policy string cannot be parsed."""

    def __init__(self, message: str, *, original: Exception | None = None) -> None:
        super().__init__(
            message,
            error_code="POLICY_PARSE_ERROR",
            original=original,
        )


def load_policy_file(path: Path, *, schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Load a policy TOML file, optionally validating against a schema."""
    try:
        raw_text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, PermissionError, OSError) as exc:  # pragma: no cover - filesystem errors
        raise PolicyLoadError(f"Failed to read policy '{path}': {exc}", original=exc) from exc

    try:
        data = tomllib.loads(raw_text)
    except (tomllib.TOMLDecodeError, ValueError, TypeError) as exc:
        raise PolicyLoadError(f"Failed to parse policy TOML '{path}': {exc}", original=exc) from exc

    if not isinstance(data, dict):
        raise PolicyLoadError("Policy file must decode to a TOML table.")

    gating = data.get("gating")
    if gating is None:
        # Allow top-level keys when no [gating] section is provided
        gating = {k: v for k, v in data.items() if not isinstance(v, dict)}
    elif not isinstance(gating, dict):
        raise PolicyLoadError("Policy 'gating' section must be a table.")

    if schema is not None:
        _validate_policy(data, schema)

    recognized: Dict[str, Any] = {}
    for key in ("min_delta", "min_pass_rate", "alpha", "power_target", "violation_cap"):
        if key in gating:
            recognized[key] = gating[key]

    return {
        "path": str(path),
        "raw": data,
        "gating": recognized,
    }


def parse_policy_preset(value: str) -> Dict[str, Any]:
    raw = value.strip()
    if not raw:
        raise PolicyParseError("Policy preset cannot be empty.")

    name, _, param_str = raw.partition(":")
    name = name.strip().lower()
    if name not in {"noninferiority", "superiority"}:
        raise PolicyParseError(
            f"Unknown policy preset '{name}'. Supported presets: noninferiority, superiority."
        )

    params_raw: Dict[str, str] = {}
    if param_str:
        for token in param_str.split(","):
            token = token.strip()
            if not token:
                continue
            key, sep, val = token.partition("=")
            if not sep:
                raise PolicyParseError(
                    f"Invalid policy preset parameter '{token}'. Expected key=value."
                )
            params_raw[key.strip().lower()] = val.strip()

    def _get_float(key: str, default: Optional[float] = None) -> Optional[float]:
        if key not in params_raw:
            return default
        try:
            return float(params_raw[key])
        except ValueError:
            raise PolicyParseError(f"Policy preset parameter '{key}' must be numeric.")

    margin = _get_float("margin", 0.0) or 0.0
    pass_rate = _get_float("pass_rate")
    alpha_override = _get_float("alpha")
    power_override = _get_float("power")

    violation_cap: Optional[int] = None
    if "violation_cap" in params_raw:
        try:
            violation_cap = int(params_raw["violation_cap"])
        except ValueError:
            raise PolicyParseError("Policy preset parameter 'violation_cap' must be an integer.")

    min_delta = margin if name == "superiority" else -margin
    gating: Dict[str, Any] = {"min_delta": min_delta}
    if pass_rate is not None:
        gating["min_pass_rate"] = pass_rate
    if alpha_override is not None:
        gating["alpha"] = alpha_override
    if power_override is not None:
        gating["power_target"] = power_override
    if violation_cap is not None:
        gating["violation_cap"] = violation_cap

    quality_policy: Dict[str, Any] = {"min_delta": min_delta}
    if pass_rate is not None:
        quality_policy["min_pass_rate"] = pass_rate

    label_parts = []
    if margin:
        label_parts.append(f"margin={margin}")
    if pass_rate is not None:
        label_parts.append(f"pass_rate={pass_rate}")
    if violation_cap is not None:
        label_parts.append(f"violation_cap={violation_cap}")
    parameters: Dict[str, Any] = {}
    if "margin" in params_raw:
        parameters["margin"] = margin
    if pass_rate is not None and "pass_rate" in params_raw:
        parameters["pass_rate"] = pass_rate
    if alpha_override is not None and "alpha" in params_raw:
        parameters["alpha"] = alpha_override
    if power_override is not None and "power" in params_raw:
        parameters["power"] = power_override
    if violation_cap is not None and "violation_cap" in params_raw:
        parameters["violation_cap"] = violation_cap

    # Preserve any additional, unrecognized parameters as raw strings
    for key, value in params_raw.items():
        if key not in parameters:
            parameters[key] = value

    descriptor = {
        "type": "preset",
        "name": name,
        "parameters": parameters,
        "label": f"{name}({', '.join(label_parts)})" if label_parts else name,
    }

    return {
        "source": "preset",
        "name": name,
        "parameters": parameters,
        "gating": gating,
        "policy": {"quality": quality_policy},
        "descriptor": descriptor,
    }


def resolve_policy_option(value: str) -> Dict[str, Any]:
    candidate = value.strip()
    if not candidate:
        raise PolicyParseError("Policy value cannot be empty.")

    path = Path(candidate)
    if path.exists():
        if not path.is_file():
            raise PolicyParseError(f"Policy path must be a file: {path}")
        payload = load_policy_file(path)
        payload["source"] = "file"

        descriptor: Dict[str, Any] = {"type": "file", "path": str(path)}
        raw_section = payload.get("raw", {})
        if isinstance(raw_section, dict):
            policy_name = raw_section.get("name")
            if isinstance(policy_name, str):
                descriptor["name"] = policy_name
                descriptor["label"] = policy_name
        payload["descriptor"] = descriptor

        gating_cfg = payload.get("gating", {})
        normalized_gating: Dict[str, Any] = {}
        for key, val in gating_cfg.items():
            if key == "violation_cap":
                try:
                    normalized_gating[key] = int(val)
                except (TypeError, ValueError):
                    raise PolicyParseError("Policy value 'violation_cap' must be an integer.")
            else:
                try:
                    normalized_gating[key] = float(val)
                except (TypeError, ValueError):
                    raise PolicyParseError(f"Policy value '{key}' must be numeric.")
        payload["gating"] = normalized_gating

        if isinstance(raw_section, dict) and isinstance(raw_section.get("policy"), dict):
            policy_dict = raw_section["policy"]  # type: ignore[assignment]
        else:
            quality_policy: Dict[str, Any] = {}
            if "min_delta" in normalized_gating:
                quality_policy["min_delta"] = normalized_gating["min_delta"]
            if "min_pass_rate" in normalized_gating:
                quality_policy["min_pass_rate"] = normalized_gating["min_pass_rate"]
            policy_dict = {"quality": quality_policy} if quality_policy else {}

        payload["policy"] = policy_dict
        return payload

    return parse_policy_preset(candidate)


def _validate_policy(data: Dict[str, Any], schema: Dict[str, Any]) -> None:
    """Validates the policy data against a simple JSON-schema-like mapping."""
    try:
        from jsonschema import Draft202012Validator, validate  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise PolicyLoadError(
            "jsonschema is required for policy validation. Install with `pip install jsonschema`.",
            original=exc,
        ) from exc

    errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: e.path)
    if errors:
        message = "; ".join(f"{'/'.join(str(p) for p in error.path)}: {error.message}" for error in errors)
        raise PolicyLoadError(f"Policy schema validation failed: {message}")

