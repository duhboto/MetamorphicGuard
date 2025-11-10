from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Dict, Sequence


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

    pass_chart_config = {
        "type": "bar",
        "data": {
            "labels": ["Baseline", "Candidate"],
            "datasets": [
                {
                    "label": "Pass Rate (%)",
                    "backgroundColor": ["#4caf50", "#2196f3"],
                    "data": [
                        round(float(baseline.get("pass_rate", 0.0)) * 100, 3),
                        round(float(candidate.get("pass_rate", 0.0)) * 100, 3),
                    ],
                }
            ],
        },
        "options": {
            "responsive": True,
            "plugins": {
                "legend": {"display": False},
                "title": {
                    "display": True,
                    "text": "Pass Rate Comparison",
                },
            },
            "scales": {
                "y": {
                    "beginAtZero": True,
                    "suggestedMax": 100,
                }
            },
        },
    }

    fairness_chart = _extract_fairness_chart(monitors)
    resource_chart = _extract_resource_chart(monitors)

    fairness_block = (
        """
  <div class="chart-container">
    <h2>Fairness Gap</h2>
    <canvas id="fairness-chart"></canvas>
  </div>
"""
        if fairness_chart
        else ""
    )

    resource_block = (
        """
  <div class="chart-container">
    <h2>Resource Usage</h2>
    <canvas id="resource-chart"></canvas>
  </div>
"""
        if resource_chart
        else ""
    )

    chart_script = _build_chart_script(pass_chart_config, fairness_chart, resource_chart)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Metamorphic Guard Report - {html.escape(payload.get("task", ""))}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; }}
    h1, h2, h3, h4 {{ color: #333; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 1.5rem; }}
    th, td {{ border: 1px solid #ddd; padding: 0.75rem; text-align: left; }}
    th {{ background: #f5f5f5; }}
    code, pre {{ background: #f0f0f0; padding: 0.2rem 0.4rem; border-radius: 4px; overflow-x: auto; }}
    .monitor-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1rem; }}
    .monitor-card {{ border: 1px solid #ddd; border-radius: 6px; padding: 1rem; background: #fafafa; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }}
    .monitor-card h3 {{ margin-top: 0; font-size: 1.1rem; }}
    .monitor-summary {{ width: 100%; font-size: 0.9rem; border-collapse: collapse; margin-top: 0.5rem; }}
    .monitor-summary td {{ border: none; padding: 0.2rem 0.1rem; }}
    .monitor-alerts {{ margin-top: 0.5rem; padding-left: 1.2rem; color: #8b0000; }}
    .monitor-alerts li {{ margin-bottom: 0.25rem; }}
    .chart-container {{ margin: 2rem 0; }}
    .chart-container canvas {{ max-width: 720px; width: 100%; height: 320px; }}
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

  <div class="chart-container">
    <canvas id="pass-rate-chart"></canvas>
  </div>
  {fairness_block}
  {resource_block}

  <h2>Configuration</h2>
  <pre>{html.escape(str(config))}</pre>

  <h2>Job Metadata</h2>
  <pre>{html.escape(str(job))}</pre>

  <h2>Baseline Violations</h2>
  {_format_violations(baseline)}

  <h2>Candidate Violations</h2>
  {_format_violations(candidate)}

  <h2>Monitors</h2>
  <div class="monitor-grid">
  {_format_monitors(monitors)}
  </div>
  {chart_script}
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
        monitor_type = html.escape(str(data.get("type", "")))
        summary_html = _render_monitor_summary(data.get("summary", {}))
        alerts = data.get("alerts", []) or []
        if alerts:
            alert_items = "".join(
                f"<li>{html.escape(json.dumps(alert))}</li>" for alert in alerts
            )
            alerts_html = f"<ul class=\"monitor-alerts\">{alert_items}</ul>"
        else:
            alerts_html = ""

        blocks.append(
            "<div class=\"monitor-card\">"
            f"<h3>{html.escape(str(name))} <small>({monitor_type})</small></h3>"
            f"{summary_html}{alerts_html}"
            "</div>"
        )
    return "".join(blocks)


def _render_monitor_summary(summary: Any) -> str:
    if not isinstance(summary, dict):
        return ""

    rows = []

    def _append(prefix: str, value: Any) -> None:
        if isinstance(value, dict):
            for key, sub in value.items():
                _append(f"{prefix}.{key}" if prefix else str(key), sub)
        else:
            rows.append(
                f"<tr><td>{html.escape(prefix)}</td><td>{html.escape(str(value))}</td></tr>"
            )

    for key, value in summary.items():
        _append(str(key), value)

    if not rows:
        return ""

    return f"<table class=\"monitor-summary\">{''.join(rows)}</table>"


def _extract_fairness_chart(monitors: Dict[str, Any] | Sequence[Any]) -> Dict[str, Any] | None:
    entries: Sequence[Any]
    if isinstance(monitors, dict):
        entries = monitors.values()
    else:
        entries = monitors or []

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if entry.get("type") != "fairness_gap":
            continue
        summary = entry.get("summary") or {}
        baseline_rates = summary.get("baseline", {}) or {}
        candidate_rates = summary.get("candidate", {}) or {}
        labels = sorted(set(baseline_rates) | set(candidate_rates))
        if not labels:
            return None
        baseline_values = [round(float(baseline_rates.get(label, 0.0)) * 100, 3) for label in labels]
        candidate_values = [round(float(candidate_rates.get(label, 0.0)) * 100, 3) for label in labels]
        return {
            "type": "bar",
            "data": {
                "labels": labels,
                "datasets": [
                    {
                        "label": "Baseline",
                        "backgroundColor": "#607d8b",
                        "data": baseline_values,
                    },
                    {
                        "label": "Candidate",
                        "backgroundColor": "#ff9800",
                        "data": candidate_values,
                    },
                ],
            },
            "options": {
                "responsive": True,
                "plugins": {
                    "title": {
                        "display": True,
                        "text": f"Fairness Gap (max Δ={summary.get('max_gap', 0):.3f})",
                    },
                },
                "scales": {
                    "y": {
                        "beginAtZero": True,
                        "suggestedMax": 100,
                    }
                },
            },
        }
    return None


def _extract_resource_chart(monitors: Dict[str, Any] | Sequence[Any]) -> Dict[str, Any] | None:
    entries: Sequence[Any]
    if isinstance(monitors, dict):
        entries = monitors.values()
    else:
        entries = monitors or []

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if entry.get("type") != "resource_usage":
            continue
        summary = entry.get("summary") or {}
        metric = entry.get("metric", "usage")
        labels = ["Baseline", "Candidate"]
        baseline_mean = summary.get("baseline", {}).get("mean")
        candidate_mean = summary.get("candidate", {}).get("mean")
        if baseline_mean is None and candidate_mean is None:
            return None
        values = [
            round(float(baseline_mean or 0.0), 3),
            round(float(candidate_mean or 0.0), 3),
        ]
        return {
            "type": "bar",
            "data": {
                "labels": labels,
                "datasets": [
                    {
                        "label": f"{metric} (mean)",
                        "backgroundColor": ["#9c27b0", "#e040fb"],
                        "data": values,
                    }
                ],
            },
            "options": {
                "responsive": True,
                "plugins": {
                    "title": {
                        "display": True,
                        "text": f"Resource Usage - {metric}",
                    },
                },
            },
        }
    return None


def _build_chart_script(
    pass_chart: Dict[str, Any],
    fairness_chart: Dict[str, Any] | None,
    resource_chart: Dict[str, Any] | None,
) -> str:
    fairness_def = ""
    fairness_init = ""
    if fairness_chart:
        fairness_def = f"const fairnessChartConfig = {json.dumps(fairness_chart)};"
        fairness_init = "const fairnessCtx = document.getElementById('fairness-chart');\n    if (fairnessCtx) { new Chart(fairnessCtx, fairnessChartConfig); }"

    resource_def = ""
    resource_init = ""
    if resource_chart:
        resource_def = f"const resourceChartConfig = {json.dumps(resource_chart)};"
        resource_init = "const resourceCtx = document.getElementById('resource-chart');\n    if (resourceCtx) { new Chart(resourceCtx, resourceChartConfig); }"

    return (
        "\n  <script src=\"https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js\"></script>\n  <script>\n    const passRateChartConfig = "
        + json.dumps(pass_chart)
        + ";\n    "
        + fairness_def
        + ("\n    " if fairness_def else "")
        + resource_def
        + ("\n    " if resource_def else "")
        + "document.addEventListener('DOMContentLoaded', () => {\n      if (typeof Chart === 'undefined') { return; }\n      const passCtx = document.getElementById('pass-rate-chart');\n      if (passCtx) { new Chart(passCtx, passRateChartConfig); }\n      "
        + fairness_init
        + ("\n      " if fairness_init else "")
        + resource_init
        + "\n    });\n  </script>\n"
    )

