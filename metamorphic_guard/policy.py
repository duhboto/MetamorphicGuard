"""
Utilities for loading gating policy files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import tomllib


class PolicyLoadError(Exception):
    """Raised when a policy file cannot be loaded or parsed."""


def load_policy_file(path: Path) -> Dict[str, Any]:
    """Load a policy TOML file and return structured data."""
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

    recognized: Dict[str, Any] = {}
    for key in ("min_delta", "min_pass_rate", "alpha", "power_target", "violation_cap"):
        if key in gating:
            recognized[key] = gating[key]

    return {
        "path": str(path),
        "raw": data,
        "gating": recognized,
    }

