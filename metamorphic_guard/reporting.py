from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Dict


def render_html_report(payload: Dict[str, Any], destination: Path) -> Path:
    """Render a simple HTML report summarizing the evaluation."""
    baseline = payload.get("baseline", {}) or {}
    candidate = payload.get("candidate", {}) or {}
    config = payload.get("config", {}) or {}
    job = payload.get("job_metadata", {}) or {}
    decision = payload.get("decision") or {}

    def _format_violations(section: Dict[str, Any]) -> str:
        entries = []
        for violation in section.get("prop_violations", []) + section.get("mr_violations", []):
            items = [
                f"<li><strong>Property</strong>: {html.escape(str(violation.get('property', violation.get('relation', ''))))}</li>",
                f"<li><strong>Input</strong>: {html.escape(str(violation.get('input', '')))}</li>",
            ]
            if "output" in violation:
                items.append(f"<li><strong>Output</strong>: {html.escape(str(violation['output']))}</li>")
            if "relation_output" in violation:
                items.append(f"<li><strong>Relation Output</strong>: {html.escape(str(violation['relation_output']))}</li>")
            if "error" in violation:
                items.append(f"<li><strong>Error</strong>: {html.escape(str(violation['error']))}</li>")
            entries.append("<ul>" + "".join(items) + "</ul>")
        return "".join(entries) or "<p>No violations recorded.</p>"

    monitors = payload.get("monitors", {})

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Metamorphic Guard Report - {html.escape(payload.get("task", ""))}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; }}
    h1, h2 {{ color: #333; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 1.5rem; }}
    th, td {{ border: 1px solid #ddd; padding: 0.75rem; text-align: left; }}
    th {{ background: #f5f5f5; }}
    code {{ background: #f0f0f0; padding: 0.2rem 0.4rem; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>Metamorphic Guard Report</h1>
  <p><strong>Task:</strong> {html.escape(str(payload.get("task", "")))}</p>
  <p><strong>Decision:</strong> {html.escape(str(decision.get("reason", "unknown")))}</p>
  <p><strong>Adopt:</strong> {html.escape(str(decision.get("adopt", False)))}</p>

  <h2>Summary Metrics</h2>
  <table>
    <tr><th>Metric</th><th>Value</th></tr>
    <tr><td>Baseline Pass Rate</td><td>{baseline.get("pass_rate", 0):.3f}</td></tr>
    <tr><td>Candidate Pass Rate</td><td>{candidate.get("pass_rate", 0):.3f}</td></tr>
    <tr><td>Δ Pass Rate</td><td>{payload.get("delta_pass_rate", 0):.3f}</td></tr>
    <tr><td>Δ 95% CI</td><td>{payload.get("delta_ci")}</td></tr>
    <tr><td>Relative Risk</td><td>{payload.get("relative_risk", 0):.3f}</td></tr>
    <tr><td>RR 95% CI</td><td>{payload.get("relative_risk_ci")}</td></tr>
  </table>

  <h2>Configuration</h2>
  <pre>{html.escape(str(config))}</pre>

  <h2>Job Metadata</h2>
  <pre>{html.escape(str(job))}</pre>

  <h2>Baseline Violations</h2>
  {_format_violations(baseline)}

  <h2>Candidate Violations</h2>
  {_format_violations(candidate)}

  <h2>Monitors</h2>
  {_format_monitors(monitors)}
</body>
</html>
"""
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(html_content, encoding="utf-8")
    return destination


def _format_monitors(monitors: Dict[str, Any] | Sequence[Any]) -> str:
    if not monitors:
        return "<p>No monitors configured.</p>"

    if isinstance(monitors, dict):
        items = monitors.items()
    else:
        items = ((entry.get("id", f"monitor_{idx}"), entry) for idx, entry in enumerate(monitors))

    blocks = []
    for name, data in items:
        blocks.append(
            f"<div><h3>{html.escape(str(name))}</h3><pre>{html.escape(json.dumps(data, indent=2))}</pre></div>"
        )
    return "".join(blocks)

