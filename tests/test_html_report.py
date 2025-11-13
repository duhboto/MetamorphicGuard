"""Tests for HTML report generation."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from metamorphic_guard.harness import run_eval
from metamorphic_guard.reporting import render_html_report
from metamorphic_guard.util import write_report


def test_html_report_generation(tmp_path: Path) -> None:
    """Test that HTML report is generated and contains expected content."""
    baseline_path = Path("examples/top_k_baseline.py")
    candidate_path = Path("examples/top_k_improved.py")
    
    if not baseline_path.exists() or not candidate_path.exists():
        pytest.skip("Example files not found")
    
    html_output = tmp_path / "report.html"
    
    # Run evaluation
    result = run_eval(
        task_name="top_k",
        baseline_path=str(baseline_path),
        candidate_path=str(candidate_path),
        n=50,
        seed=42,
    )
    
    # Generate HTML report
    render_html_report(result, html_output)
    
    # Verify file exists
    assert html_output.exists(), "HTML report file should be created"
    assert html_output.stat().st_size > 0, "HTML report should not be empty"
    
    # Read and verify content
    html_content = html_output.read_text(encoding="utf-8")
    
    # Check for run_id in HTML (should be in JSON data or visible text)
    run_id = result.get("job_metadata", {}).get("run_id")
    if run_id:
        assert run_id in html_content or json.dumps(run_id) in html_content, \
            f"HTML report should contain run_id: {run_id}"
    
    # Check for task name
    assert result["task"] in html_content, \
        f"HTML report should contain task name: {result['task']}"
    
    # Check for decision
    decision = result.get("decision", {})
    if decision.get("adopt") is not None:
        # Decision should be visible in HTML
        assert "adopt" in html_content.lower() or "decision" in html_content.lower(), \
            "HTML report should contain decision information"
    
    # Check for basic HTML structure
    assert "<html" in html_content.lower() or "<!doctype" in html_content.lower(), \
        "HTML report should be valid HTML"
    
    # Check for baseline/candidate metrics and coverage section
    baseline_pass_rate = result.get("baseline", {}).get("pass_rate", 0.0)
    candidate_pass_rate = result.get("candidate", {}).get("pass_rate", 0.0)
    
    # Pass rates should be in the HTML (as numbers or in charts)
    assert str(baseline_pass_rate) in html_content or \
           f"{baseline_pass_rate:.2f}" in html_content or \
           f"{baseline_pass_rate:.3f}" in html_content, \
           f"HTML report should contain baseline pass rate: {baseline_pass_rate}"
    
    assert str(candidate_pass_rate) in html_content or \
           f"{candidate_pass_rate:.2f}" in html_content or \
           f"{candidate_pass_rate:.3f}" in html_content, \
           f"HTML report should contain candidate pass rate: {candidate_pass_rate}"

    assert "Metamorphic Relation Coverage" in html_content
    assert "Reproduction" in html_content


def test_html_report_from_json(tmp_path: Path) -> None:
    """Test generating HTML report from existing JSON report."""
    baseline_path = Path("examples/top_k_baseline.py")
    candidate_path = Path("examples/top_k_improved.py")
    
    if not baseline_path.exists() or not candidate_path.exists():
        pytest.skip("Example files not found")
    
    # Run evaluation and write JSON report
    result = run_eval(
        task_name="top_k",
        baseline_path=str(baseline_path),
        candidate_path=str(candidate_path),
        n=50,
        seed=42,
    )
    
    # Ensure decision is present (run_eval may not add it)
    from metamorphic_guard.gate import decide_adopt
    if "decision" not in result:
        result["decision"] = decide_adopt(result, min_delta=0.02)
    
    json_report = tmp_path / "report.json"
    write_report(result, directory=tmp_path)
    
    # Find the actual report file (write_report may generate timestamped name)
    json_files = list(tmp_path.glob("report_*.json"))
    if json_files:
        json_report = max(json_files, key=lambda p: p.stat().st_mtime)
    
    assert json_report.exists(), "JSON report should be created"
    
    # Load JSON and generate HTML
    with open(json_report, "r", encoding="utf-8") as f:
        json_data = json.load(f)
    
    html_output = tmp_path / "from_json.html"
    render_html_report(json_data, html_output)
    
    # Verify HTML was generated
    assert html_output.exists(), "HTML report should be generated from JSON"
    assert html_output.stat().st_size > 0, "HTML report should not be empty"
    
    # Verify content matches
    html_content = html_output.read_text(encoding="utf-8")
    assert json_data["task"] in html_content, \
        "HTML should contain task from JSON report"


def test_html_report_includes_llm_metrics(tmp_path: Path) -> None:
    html_output = tmp_path / "llm.html"
    payload = {
        "task": "llm_task",
        "baseline": {"pass_rate": 0.9, "prop_violations": [], "mr_violations": []},
        "candidate": {"pass_rate": 0.95, "prop_violations": [], "mr_violations": []},
        "delta_pass_rate": 0.05,
        "delta_ci": [0.01, 0.08],
        "relative_risk": 1.02,
        "relative_risk_ci": [0.99, 1.05],
        "decision": {"adopt": True, "reason": "meets_gate"},
        "llm_metrics": {
            "baseline": {
                "total_cost_usd": 0.5,
                "total_tokens": 1200,
                "avg_latency_ms": 120.5,
                "retry_total": 1,
                "success_rate": 0.95,
            },
            "candidate": {
                "total_cost_usd": 0.4,
                "total_tokens": 1100,
                "avg_latency_ms": 110.0,
                "retry_total": 0,
                "success_rate": 0.97,
            },
            "cost_delta_usd": -0.1,
            "cost_ratio": 0.8,
            "tokens_delta": -100,
            "token_ratio": 1100 / 1200,
            "retry_delta": -1,
            "retry_ratio": 0.0,
        },
    }
    render_html_report(payload, html_output)
    content = html_output.read_text(encoding="utf-8")
    assert "LLM Metrics" in content
    assert "Total Cost (USD)" in content

