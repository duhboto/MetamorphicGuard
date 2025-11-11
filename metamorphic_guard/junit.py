"""JUnit XML output for CI integration."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from .reporting import render_junit_report


def write_junit_xml(result: Dict[str, Any], output_path: Path) -> None:
    """
    Backwards-compatible wrapper for legacy integrations.

    Delegates to :func:`render_junit_report` which now powers all JUnit output.
    """
    render_junit_report(result, output_path)

