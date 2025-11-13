"""Pytest plugin implementation for Metamorphic Guard."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional
import warnings

import pytest

try:
    from metamorphic_guard.harness import run_eval
    from metamorphic_guard.specs import get_task
    from metamorphic_guard.util import write_report
    from metamorphic_guard.junit import write_junit_xml
    from metamorphic_guard.gate import decide_adopt
except ImportError:
    # Graceful degradation if MG not installed
    run_eval = None  # type: ignore
    get_task = None  # type: ignore
    write_report = None  # type: ignore
    write_junit_xml = None  # type: ignore
    decide_adopt = None  # type: ignore


def pytest_configure(config: pytest.Config) -> None:
    """Register the metamorphic marker."""
    config.addinivalue_line(
        "markers",
        "metamorphic(task, baseline, candidate, n=100, seed=42, expect_adopt=True): Run Metamorphic Guard evaluation as a test",
    )


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> None:
    """Set up metamorphic tests."""
    marker = item.get_closest_marker("metamorphic")
    if marker is None:
        return

    if run_eval is None:
        pytest.skip("Metamorphic Guard not installed")


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_call(item: pytest.Item) -> None:
    """Execute metamorphic tests."""
    marker = item.get_closest_marker("metamorphic")
    if marker is None:
        return

    if run_eval is None:
        return

    # Extract parameters from marker
    task_name = marker.kwargs.get("task")
    baseline_path = marker.kwargs.get("baseline")
    candidate_path = marker.kwargs.get("candidate")
    n = marker.kwargs.get("n", 100)
    seed = marker.kwargs.get("seed", 42)
    timeout_s = marker.kwargs.get("timeout_s", 2.0)
    mem_mb = marker.kwargs.get("mem_mb", 512)
    if "min_delta" in marker.kwargs:
        min_delta = marker.kwargs["min_delta"]
    else:
        min_delta = marker.kwargs.get("improve_delta", 0.02)
        if "improve_delta" in marker.kwargs:
            warnings.warn(
                "metamorphic marker parameter 'improve_delta' is deprecated; use 'min_delta' instead.",
                DeprecationWarning,
                stacklevel=2,
            )
    expect_adopt = marker.kwargs.get("expect_adopt", True)  # Default: expect adoption to succeed

    if not task_name or not baseline_path or not candidate_path:
        pytest.fail("metamorphic marker requires 'task', 'baseline', and 'candidate' parameters")

    # Run evaluation
    try:
        result = run_eval(
            task_name=task_name,
            baseline_path=baseline_path,
            candidate_path=candidate_path,
            n=n,
            seed=seed,
            timeout_s=timeout_s,
            mem_mb=mem_mb,
            min_delta=min_delta,
        )
    except Exception as e:
        pytest.fail(f"Metamorphic Guard evaluation failed: {e}")

    # Make adoption decision if not already present
    if "decision" not in result and decide_adopt is not None:
        result["decision"] = decide_adopt(result, min_delta=min_delta)

    # Store result in item for later use
    item._metamorphic_result = result  # type: ignore

    # Check adoption decision
    decision = result.get("decision", {})
    adopt = decision.get("adopt", False)

    if not adopt and expect_adopt:
        # Adoption failed but we expected it to succeed
        delta = result.get("delta_pass_rate", 0.0)
        reason = decision.get("reason", "unknown")
        pytest.fail(
            f"Metamorphic Guard adoption gate failed: {reason} (Δ pass rate: {delta:.4f})"
        )
    elif adopt and not expect_adopt:
        # Adoption succeeded but we expected it to fail
        delta = result.get("delta_pass_rate", 0.0)
        pytest.fail(
            f"Metamorphic Guard adoption gate unexpectedly passed (expected failure) (Δ pass rate: {delta:.4f})"
        )


@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item: pytest.Item, nextitem: Optional[pytest.Item]) -> None:
    """Clean up after metamorphic tests."""
    if not hasattr(item, "_metamorphic_result"):
        return

    result = item._metamorphic_result  # type: ignore

    # Write artifacts if configured
    config = item.config
    report_dir = config.getoption("--mg-report-dir", default=None)
    if report_dir:
        report_path = Path(report_dir)
        report_path.mkdir(parents=True, exist_ok=True)
        write_report(result, directory=str(report_path))

    junit_path = config.getoption("--mg-junit-xml", default=None)
    if junit_path and write_junit_xml:
        write_junit_xml(result, Path(junit_path))


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add command-line options for Metamorphic Guard."""
    group = parser.getgroup("metamorphic", "Metamorphic Guard integration")
    group.addoption(
        "--mg-report-dir",
        action="store",
        default=None,
        help="Directory to write Metamorphic Guard JSON reports",
    )
    group.addoption(
        "--mg-junit-xml",
        action="store",
        default=None,
        help="Path to write JUnit XML output for Metamorphic Guard tests",
    )

