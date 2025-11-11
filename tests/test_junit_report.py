from __future__ import annotations

import textwrap
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from metamorphic_guard.harness import run_eval
from metamorphic_guard.reporting import render_junit_report


def _ensure_examples() -> None:
    base = Path("examples/top_k_baseline.py")
    cand = Path("examples/top_k_improved.py")
    if not base.exists() or not cand.exists():
        pytest.skip("Example files not present")


def test_junit_report_success(tmp_path: Path) -> None:
    _ensure_examples()
    destination = tmp_path / "report.xml"
    result = run_eval(
        task_name="top_k",
        baseline_path="examples/top_k_baseline.py",
        candidate_path="examples/top_k_improved.py",
        n=8,
        seed=123,
    )

    render_junit_report(result, destination)

    assert destination.exists()
    tree = ET.parse(destination)
    suite = tree.getroot()

    candidate = result["candidate"]
    assert suite.tag == "testsuite"
    assert suite.attrib["tests"] == str(candidate["total"])
    assert suite.attrib["failures"] == "0"

    testcases = suite.findall("testcase")
    assert len(testcases) == len(result["cases"])
    assert all(tc.find("failure") is None for tc in testcases)

    properties = suite.find("properties")
    assert properties is not None
    prop_map = {prop.attrib["name"]: prop.attrib["value"] for prop in properties}
    assert prop_map["decision.adopt"] == str(result["decision"].get("adopt"))
    assert "statistics.power_estimate" in prop_map


def test_junit_report_failure(tmp_path: Path) -> None:
    _ensure_examples()

    bad_candidate = tmp_path / "bad_candidate.py"
    bad_candidate.write_text(
        textwrap.dedent(
            """
            def solve(L, k):
                return []
            """
        ),
        encoding="utf-8",
    )

    destination = tmp_path / "failure_report.xml"
    result = run_eval(
        task_name="top_k",
        baseline_path="examples/top_k_baseline.py",
        candidate_path=str(bad_candidate),
        n=4,
        seed=999,
    )

    render_junit_report(result, destination)

    tree = ET.parse(destination)
    suite = tree.getroot()

    candidate = result["candidate"]
    expected_failures = candidate["total"] - candidate["passes"]
    assert int(suite.attrib["failures"]) == expected_failures

    fail_cases = [tc for tc in suite.findall("testcase") if tc.find("failure") is not None]
    assert fail_cases, "Expected at least one failing testcase in JUnit report"
    failure_node = fail_cases[0].find("failure")
    assert failure_node is not None
    assert "failed" in failure_node.attrib["message"].lower()
    assert "relation" in (failure_node.text or "").lower() or "property" in (failure_node.text or "").lower()

