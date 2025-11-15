"""
Utility functions for sandbox result processing.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence

from ..redaction import get_redactor


def _result(
    *,
    success: bool,
    duration_ms: float,
    stdout: str,
    stderr: str,
    error: Optional[str] = None,
    result: Optional[Any] = None,
    error_type: Optional[str] = None,
    error_code: Optional[str] = None,
    diagnostics: Optional[Dict[str, Any]] = None,
    sandbox_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Helper for constructing run_in_sandbox response payloads."""
    payload: Dict[str, Any] = {
        "success": success,
        "result": result,
        "stdout": stdout,
        "stderr": stderr,
        "duration_ms": duration_ms,
        "error": error,
    }
    if error_type:
        payload["error_type"] = error_type
    if error_code:
        payload["error_code"] = error_code
    if diagnostics:
        payload["diagnostics"] = diagnostics
    if sandbox_metadata is not None:
        payload["sandbox_metadata"] = sandbox_metadata
    return payload


def _sanitize_config_payload(payload: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Sanitize config payload for serialization."""
    if payload is None:
        return None
    try:
        return json.loads(json.dumps(payload, default=str))
    except Exception:  # pragma: no cover - fallback for non-serializable values
        sanitized: Dict[str, Any] = {}
        for key, value in payload.items():
            sanitized[str(key)] = str(value)
        return sanitized


def _finalize_result(result: Any, config: Optional[Dict[str, Any]]) -> Any:
    """Finalize result by applying redaction to sensitive data."""
    if not isinstance(result, dict):
        return result
    redactor = get_redactor(config if isinstance(config, dict) else None)
    return redactor.redact(result)



