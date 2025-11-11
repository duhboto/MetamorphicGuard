"""
Utilities for loading gating policy files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import tomllib


class PolicyLoadError(Exception):
    """Raised when a policy file cannot be loaded or parsed."""


def load_policy_file(path: Path, *, schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Load a policy TOML file, optionally validating against a schema."""
    try:
        raw_text = path.read_text(encoding="utf-8")
    except Exception as exc:  # pragma: no cover - filesystem errors
        raise PolicyLoadError(f"Failed to read policy '{path}': {exc}") from exc

    try:
        data = tomllib.loads(raw_text)
    except Exception as exc:
        raise PolicyLoadError(f"Failed to parse policy TOML '{path}': {exc}") from exc

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


def _validate_policy(data: Dict[str, Any], schema: Dict[str, Any]) -> None:
    """Validates the policy data against a simple JSON-schema-like mapping."""
    try:
        from jsonschema import Draft202012Validator, validate  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise PolicyLoadError(
            "jsonschema is required for policy validation. Install with `pip install jsonschema`."
        ) from exc

    errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: e.path)
    if errors:
        message = "; ".join(f"{'/'.join(str(p) for p in error.path)}: {error.message}" for error in errors)
        raise PolicyLoadError(f"Policy schema validation failed: {message}")

