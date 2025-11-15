from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Dict, Sequence
import xml.etree.ElementTree as ET


def render_html_report(
    payload: Dict[str, Any],
    destination: Path,
    *,
    theme: str = "default",
    title: str | None = None,
    show_config: bool = True,
    show_metadata: bool = True,
) -> Path:
    """
    Render an HTML report summarizing the evaluation.
    
    Args:
        payload: Evaluation result payload
        destination: Output file path
        theme: Report theme ('default', 'dark', 'minimal')
        title: Custom report title (defaults to task name)
        show_config: Whether to show configuration section
        show_metadata: Whether to show job metadata section
    
    Returns:
        Path to generated HTML file
    """
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
    performance_chart = _extract_performance_chart(monitors)
    relation_block = _render_relation_coverage(payload.get("relation_coverage"))
    replay_block = _render_replay_block(payload.get("replay"))
    policy_block = _render_policy_block(payload.get("policy"), decision)
    coverage_chart = _build_coverage_chart(payload.get("relation_coverage"))
    llm_metrics_block = _render_llm_metrics(payload.get("llm_metrics"))

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

    performance_block = (
        """
  <div class="chart-container">
    <h2>Performance Profiling</h2>
    <canvas id="performance-chart"></canvas>
  </div>
"""
        if performance_chart
        else ""
    )

    chart_script = _build_chart_script(pass_chart_config, fairness_chart, resource_chart, coverage_chart, performance_chart)
    
    # Theme-specific CSS
    theme_css = _get_theme_css(theme)
    
    # Report title
    report_title = title or f"Metamorphic Guard Report - {html.escape(str(payload.get('task', '')))}"
    page_title = title or f"Metamorphic Guard Report - {html.escape(str(payload.get('task', '')))}"
    
    # Configuration and metadata blocks (conditional)
    config_block = f"""
  <h2>Configuration</h2>
  <pre>{html.escape(str(config))}</pre>
""" if show_config else ""
    
    metadata_block = f"""
  <h2>Job Metadata</h2>
  <pre>{html.escape(str(job))}</pre>
""" if show_metadata else ""

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{html.escape(page_title)}</title>
  <style>
    {theme_css}
  </style>
</head>
<body>
  <header class="report-header">
    <h1>{html.escape(report_title)}</h1>
    <div class="report-meta">
      <span class="meta-item"><strong>Task:</strong> {html.escape(str(payload.get("task", "")))}</span>
      <span class="meta-item"><strong>Decision:</strong> {html.escape(str(decision.get("reason", "unknown")))}</span>
      <span class="meta-item decision-badge {'adopt' if decision.get('adopt', False) else 'reject'}">
        {html.escape(str(decision.get("adopt", False)))}
      </span>
    </div>
  </header>
  
  {policy_block}
  
  <section class="summary-section">
    <h2>Summary Metrics</h2>
    <table class="metrics-table">
      <thead>
        <tr><th>Metric</th><th>Value</th></tr>
      </thead>
      <tbody>
        <tr><td>Baseline Pass Rate</td><td class="metric-value">{baseline.get("pass_rate", 0):.3f}</td></tr>
        <tr><td>Candidate Pass Rate</td><td class="metric-value">{candidate.get("pass_rate", 0):.3f}</td></tr>
        <tr><td>Δ Pass Rate</td><td class="metric-value">{payload.get("delta_pass_rate", 0):.3f}</td></tr>
        <tr><td>Δ 95% CI</td><td class="metric-value">{payload.get("delta_ci")}</td></tr>
        <tr><td>Relative Risk</td><td class="metric-value">{payload.get("relative_risk", 0):.3f}</td></tr>
        <tr><td>RR 95% CI</td><td class="metric-value">{payload.get("relative_risk_ci")}</td></tr>
      </tbody>
    </table>
  </section>
  
  {llm_metrics_block}

  <section class="charts-section">
    <div class="chart-container">
      <h2>Pass Rate Comparison</h2>
      <canvas id="pass-rate-chart"></canvas>
    </div>
    {fairness_block}
    {resource_block}
    {performance_block}
    {('<div class="chart-container"><h2>MR Coverage by Category</h2><canvas id="coverage-chart"></canvas></div>' if coverage_chart else '')}
  </section>

  {config_block}
  {metadata_block}
  {replay_block}
  {relation_block}

  <section class="violations-section">
    <h2>Baseline Violations</h2>
    <div class="violations-content">
      {_format_violations(baseline)}
    </div>
  </section>

  <section class="violations-section">
    <h2>Candidate Violations</h2>
    <div class="violations-content">
      {_format_violations(candidate)}
    </div>
  </section>

  <section class="monitors-section">
    <h2>Monitors</h2>
    <div class="monitor-grid">
      {_format_monitors(monitors)}
    </div>
  </section>
  
  {chart_script}
</body>
</html>
"""
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(html_content, encoding="utf-8")
    return destination


def render_junit_report(
    payload: Dict[str, Any],
    destination: Path,
    suite_name: str | None = None,
) -> Path:
    """
    Render a JUnit XML report for CI consumption.

    Each test case corresponds to an evaluation input. Failures capture the first
    related violation for quick debugging while embedding the full violation
    payload in the failure body.
    """

    cases = payload.get("cases") or []
    candidate = payload.get("candidate") or {}
    decision = payload.get("decision") or {}
    statistics = payload.get("statistics") or {}

    pass_indicators = list(candidate.get("pass_indicators") or [])
    candidate_total = int(candidate.get("total") or len(cases))
    candidate_passes = int(candidate.get("passes") or sum(x for x in pass_indicators if x))
    failures_expected = max(candidate_total - candidate_passes, 0)

    suite_attrs = {
        "name": suite_name or payload.get("task") or "MetamorphicGuard",
        "tests": str(candidate_total),
        "failures": str(failures_expected),
        "errors": "0",
        "skipped": "0",
    }
    suite = ET.Element("testsuite", suite_attrs)

    properties = ET.SubElement(suite, "properties")

    def _append_property(name: str, value: Any) -> None:
        if value is None:
            return
        if isinstance(value, (dict, list)):
            serialized = json.dumps(value, sort_keys=True)
        else:
            serialized = str(value)
        ET.SubElement(properties, "property", {"name": name, "value": serialized})

    _append_property("decision.adopt", decision.get("adopt"))
    _append_property("decision.reason", decision.get("reason"))
    _append_property("delta.pass_rate", payload.get("delta_pass_rate"))
    _append_property("delta.ci", payload.get("delta_ci"))
    _append_property("relative_risk", payload.get("relative_risk"))
    _append_property("relative_risk_ci", payload.get("relative_risk_ci"))
    for key, value in statistics.items():
        _append_property(f"statistics.{key}", value)

    violations = (candidate.get("prop_violations") or []) + (
        candidate.get("mr_violations") or []
    )

    violations_by_case: Dict[int, list[Dict[str, Any]]] = {}
    for violation in violations:
        if not isinstance(violation, dict):
            continue
        idx = violation.get("test_case")
        if idx is None:
            continue
        violations_by_case.setdefault(int(idx), []).append(violation)

    def _case_passed(case_index: int) -> bool:
        if case_index < len(pass_indicators):
            return bool(pass_indicators[case_index])
        if violations_by_case.get(case_index):
            return False
        return True

    task_name = payload.get("task") or "MetamorphicGuard"

    for position, case in enumerate(cases):
        idx = int(case.get("index", position))
        name = str(case.get("formatted") or f"case_{idx}")
        testcase = ET.SubElement(
            suite,
            "testcase",
            {
                "classname": str(task_name),
                "name": name,
                "time": "0",
            },
        )

        if _case_passed(idx):
            continue

        case_violations = violations_by_case.get(idx) or []
        messages: list[str] = []
        details: list[str] = []
        for violation in case_violations:
            if "relation" in violation:
                messages.append(f"MR {violation['relation']} failed")
            elif "property" in violation:
                messages.append(f"Property {violation['property']} failed")
            else:
                messages.append("Evaluation failed")
            details.append(json.dumps(violation, sort_keys=True, indent=2))

        message = "; ".join(messages) if messages else "Evaluation failed"
        failure = ET.SubElement(
            testcase,
            "failure",
            {
                "message": message,
                "type": "failure",
            },
        )
        failure.text = "\n".join(details) if details else ""

    # Attach summary output to assist with quick triage.
    summary = {
        "decision": decision,
        "statistics": statistics,
        "delta_pass_rate": payload.get("delta_pass_rate"),
        "delta_ci": payload.get("delta_ci"),
        "relative_risk": payload.get("relative_risk"),
        "relative_risk_ci": payload.get("relative_risk_ci"),
    }
    system_out = ET.SubElement(suite, "system-out")
    system_out.text = json.dumps(summary, sort_keys=True, indent=2)

    destination.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(suite)
    tree.write(destination, encoding="utf-8", xml_declaration=True)
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


def _render_llm_metrics(metrics: Dict[str, Any] | None) -> str:
    if not metrics:
        return ""
    baseline = metrics.get("baseline", {}) or {}
    candidate = metrics.get("candidate", {}) or {}
    rows = [
        ("Total Cost (USD)", baseline.get("total_cost_usd", 0.0), candidate.get("total_cost_usd", 0.0), metrics.get("cost_delta_usd"), metrics.get("cost_ratio")),
        ("Total Tokens", baseline.get("total_tokens", 0), candidate.get("total_tokens", 0), metrics.get("tokens_delta"), metrics.get("token_ratio")),
        ("Average Latency (ms)", baseline.get("avg_latency_ms"), candidate.get("avg_latency_ms"), None, None),
        ("Retry Attempts", baseline.get("retry_total", 0), candidate.get("retry_total", 0), metrics.get("retry_delta"), metrics.get("retry_ratio")),
        ("Success Rate", baseline.get("success_rate"), candidate.get("success_rate"), None, None),
    ]
    body = []
    for label, base_val, cand_val, delta, ratio in rows:
        body.append(
            "<tr>"
            f"<td>{html.escape(label)}</td>"
            f"<td>{_format_optional_float(base_val)}</td>"
            f"<td>{_format_optional_float(cand_val)}</td>"
            f"<td>{_format_optional_float(delta)}</td>"
            f"<td>{_format_optional_float(ratio)}</td>"
            "</tr>"
        )
    return (
        "<h2>LLM Metrics</h2>"
        "<table>"
        "<tr><th>Metric</th><th>Baseline</th><th>Candidate</th><th>Δ</th><th>Ratio</th></tr>"
        + "".join(body)
        + "</table>"
    )


def _render_relation_coverage(coverage: Dict[str, Any] | None) -> str:
    if not coverage:
        return ""

    relations = coverage.get("relations") or []
    categories = coverage.get("categories") or {}

    relation_rows = []
    for relation in relations:
        relation_rows.append(
            "<tr>"
            f"<td>{html.escape(str(relation.get('name', '')))}</td>"
            f"<td>{html.escape(str(relation.get('category', '')))}</td>"
            f"<td>{html.escape(str(relation.get('description', '') or ''))}</td>"
            f"<td>{relation.get('baseline', {}).get('total', 0)}</td>"
            f"<td>{relation.get('baseline', {}).get('failures', 0)}</td>"
            f"<td>{_format_optional_float(relation.get('baseline', {}).get('pass_rate'))}</td>"
            f"<td>{relation.get('candidate', {}).get('total', 0)}</td>"
            f"<td>{relation.get('candidate', {}).get('failures', 0)}</td>"
            f"<td>{_format_optional_float(relation.get('candidate', {}).get('pass_rate'))}</td>"
            "</tr>"
        )

    category_rows = []
    for category, stats in categories.items():
        category_rows.append(
            "<tr>"
            f"<td>{html.escape(str(category))}</td>"
            f"<td>{stats.get('relations', 0)}</td>"
            f"<td>{stats.get('baseline_total', 0)}</td>"
            f"<td>{stats.get('baseline_failures', 0)}</td>"
            f"<td>{_format_optional_float(stats.get('baseline_pass_rate'))}</td>"
            f"<td>{stats.get('candidate_total', 0)}</td>"
            f"<td>{stats.get('candidate_failures', 0)}</td>"
            f"<td>{_format_optional_float(stats.get('candidate_pass_rate'))}</td>"
            "</tr>"
        )

    relations_table = ""
    if relation_rows:
        relations_table = (
            "<h2>Metamorphic Relation Coverage</h2>"
            "<table>"
            "<tr>"
            "<th>Relation</th><th>Category</th><th>Description</th>"
            "<th>Baseline Total</th><th>Baseline Failures</th><th>Baseline Pass Rate</th>"
            "<th>Candidate Total</th><th>Candidate Failures</th><th>Candidate Pass Rate</th>"
            "</tr>"
            + "".join(relation_rows)
            + "</table>"
        )

    categories_table = ""
    if category_rows:
        categories_table = (
            "<h3>Coverage by Category</h3>"
            "<table>"
            "<tr>"
            "<th>Category</th><th>Relations</th>"
            "<th>Baseline Total</th><th>Baseline Failures</th><th>Baseline Pass Rate</th>"
            "<th>Candidate Total</th><th>Candidate Failures</th><th>Candidate Pass Rate</th>"
            "</tr>"
            + "".join(category_rows)
            + "</table>"
        )

    if not relations_table and not categories_table:
        return ""

    return relations_table + categories_table


def _format_optional_float(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.3f}"
    except (TypeError, ValueError):
        return html.escape(str(value))


def _render_replay_block(replay: Dict[str, Any] | None) -> str:
    if not replay:
        return ""

    seed = replay.get("seed")
    cases = replay.get("cases")
    explicit = replay.get("explicit_inputs")
    baseline_path = replay.get("baseline_path")
    candidate_path = replay.get("candidate_path")
    task = replay.get("task")

    items = []
    if seed is not None:
        items.append(f"<li><strong>Seed:</strong> {html.escape(str(seed))}</li>")
    if cases is not None:
        items.append(f"<li><strong>Cases:</strong> {html.escape(str(cases))}</li>")
    items.append(f"<li><strong>Explicit inputs provided:</strong> {explicit}</li>")
    if baseline_path:
        items.append(f"<li><strong>Baseline:</strong> {html.escape(str(baseline_path))}</li>")
    if candidate_path:
        items.append(f"<li><strong>Candidate:</strong> {html.escape(str(candidate_path))}</li>")

    command = " ".join(
        [
            "metamorphic-guard",
            "--task",
            html.escape(str(task or "")),
            "--baseline",
            html.escape(str(baseline_path or "<baseline.py>")),
            "--candidate",
            html.escape(str(candidate_path or "<candidate.py>")),
            "--replay-input",
            "<cases.json>",
        ]
    ).strip()

    return (
        "<h2>Reproduction</h2>"
        "<ul>"
        f"{''.join(items)}"
        "</ul>"
        "<p>Replay command (update paths as needed):</p>"
        f"<pre><code>{command}</code></pre>"
    )


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


def _extract_performance_chart(monitors: Dict[str, Any] | Sequence[Any]) -> Dict[str, Any] | None:
    """Extract performance profiling chart data from monitors."""
    entries: Sequence[Any]
    if isinstance(monitors, dict):
        entries = monitors.values()
    else:
        entries = monitors or []

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if entry.get("type") != "performance_profiler":
            continue
        
        profile = entry
        latency_data = profile.get("latency", {})
        cost_data = profile.get("cost", {})
        
        # Build latency comparison chart
        baseline_latency = latency_data.get("baseline", {})
        candidate_latency = latency_data.get("candidate", {})
        
        if not baseline_latency or not candidate_latency:
            continue
        
        baseline_mean = baseline_latency.get("mean_ms")
        candidate_mean = candidate_latency.get("mean_ms")
        baseline_p95 = baseline_latency.get("percentiles", {}).get("p95_ms")
        candidate_p95 = candidate_latency.get("percentiles", {}).get("p95_ms")
        
        if baseline_mean is None or candidate_mean is None:
            continue
        
        # Create multi-dataset chart for latency metrics
        datasets = [
            {
                "label": "Mean Latency (ms)",
                "backgroundColor": ["#4caf50", "#2196f3"],
                "data": [
                    round(float(baseline_mean), 2),
                    round(float(candidate_mean), 2),
                ],
            }
        ]
        
        if baseline_p95 is not None and candidate_p95 is not None:
            datasets.append({
                "label": "P95 Latency (ms)",
                "backgroundColor": ["#81c784", "#64b5f6"],
                "data": [
                    round(float(baseline_p95), 2),
                    round(float(candidate_p95), 2),
                ],
            })
        
        # Add cost data if available
        if cost_data:
            baseline_cost = cost_data.get("baseline", {}).get("mean_usd")
            candidate_cost = cost_data.get("candidate", {}).get("mean_usd")
            if baseline_cost is not None and candidate_cost is not None:
                datasets.append({
                    "label": "Mean Cost (USD)",
                    "backgroundColor": ["#ff9800", "#f44336"],
                    "data": [
                        round(float(baseline_cost), 4),
                        round(float(candidate_cost), 4),
                    ],
                    "yAxisID": "y1",
                })
        
        return {
            "type": "bar",
            "data": {
                "labels": ["Baseline", "Candidate"],
                "datasets": datasets,
            },
            "options": {
                "responsive": True,
                "plugins": {
                    "title": {
                        "display": True,
                        "text": "Performance Comparison (Latency & Cost)",
                    },
                    "legend": {"display": True},
                },
                "scales": {
                    "y": {
                        "beginAtZero": True,
                        "title": {"display": True, "text": "Latency (ms)"},
                    },
                    "y1": {
                        "type": "linear",
                        "display": True,
                        "position": "right",
                        "title": {"display": True, "text": "Cost (USD)"},
                        "grid": {"drawOnChartArea": False},
                    },
                },
            },
        }
    return None


def _build_chart_script(
    pass_chart: Dict[str, Any],
    fairness_chart: Dict[str, Any] | None,
    resource_chart: Dict[str, Any] | None,
    coverage_chart: Dict[str, Any] | None,
    performance_chart: Dict[str, Any] | None = None,
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

    coverage_def = ""
    coverage_init = ""
    if coverage_chart:
        coverage_def = f"const coverageChartConfig = {json.dumps(coverage_chart)};"
        coverage_init = "const coverageCtx = document.getElementById('coverage-chart');\n    if (coverageCtx) { new Chart(coverageCtx, coverageChartConfig); }"

    performance_def = ""
    performance_init = ""
    if performance_chart:
        performance_def = f"const performanceChartConfig = {json.dumps(performance_chart)};"
        performance_init = "const performanceCtx = document.getElementById('performance-chart');\n    if (performanceCtx) { new Chart(performanceCtx, performanceChartConfig); }"

    return (
        "\n  <script src=\"https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js\"></script>\n  <script>\n    const passRateChartConfig = "
        + json.dumps(pass_chart)
        + ";\n    "
        + fairness_def
        + ("\n    " if fairness_def else "")
        + resource_def
        + ("\n    " if resource_def else "")
        + coverage_def
        + ("\n    " if coverage_def else "")
        + performance_def
        + ("\n    " if performance_def else "")
        + "document.addEventListener('DOMContentLoaded', () => {\n      if (typeof Chart === 'undefined') { return; }\n      const passCtx = document.getElementById('pass-rate-chart');\n      if (passCtx) { new Chart(passCtx, passRateChartConfig); }\n      "
        + fairness_init
        + ("\n      " if fairness_init else "")
        + resource_init
        + ("\n      " if resource_init else "")
        + coverage_init
        + ("\n      " if coverage_init else "")
        + performance_init
        + "\n    });\n  </script>\n"
    )


def _render_policy_block(policy: Dict[str, Any] | None, decision: Dict[str, Any]) -> str:
    """Render policy decision banner."""
    adopt = decision.get("adopt", False)
    reason = decision.get("reason", "unknown")
    banner_class = "adopt" if adopt else "reject"
    status_icon = "✅" if adopt else "❌"
    status_text = "ADOPTED" if adopt else "REJECTED"
    
    policy_info = ""
    if policy:
        gating = policy.get("gating", {})
        if gating:
            policy_info = "<ul>"
            if "min_delta" in gating:
                policy_info += f"<li><strong>Min Δ:</strong> {gating['min_delta']}</li>"
            if "min_pass_rate" in gating:
                policy_info += f"<li><strong>Min Pass Rate:</strong> {gating['min_pass_rate']}</li>"
            if "alpha" in gating:
                policy_info += f"<li><strong>α:</strong> {gating['alpha']}</li>"
            policy_info += "</ul>"
    
    return f"""
  <div class="policy-banner {banner_class}">
    <h2>{status_icon} Decision: {status_text}</h2>
    <p><strong>Reason:</strong> {html.escape(str(reason))}</p>
    {policy_info}
  </div>
"""


def _get_theme_css(theme: str) -> str:
    """Get CSS for the specified theme."""
    base_css = """
    * { box-sizing: border-box; }
    body { 
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
      line-height: 1.6;
      margin: 0;
      padding: 0;
      color: #333;
      background: #ffffff;
    }
    .report-header {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
      padding: 2rem;
      margin-bottom: 2rem;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    .report-header h1 {
      margin: 0 0 1rem 0;
      font-size: 2rem;
      font-weight: 600;
    }
    .report-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 1.5rem;
      font-size: 0.95rem;
    }
    .meta-item {
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .decision-badge {
      padding: 0.25rem 0.75rem;
      border-radius: 12px;
      font-weight: 600;
      font-size: 0.85rem;
      text-transform: uppercase;
    }
    .decision-badge.adopt {
      background: rgba(76, 175, 80, 0.2);
      border: 1px solid rgba(76, 175, 80, 0.5);
    }
    .decision-badge.reject {
      background: rgba(244, 67, 54, 0.2);
      border: 1px solid rgba(244, 67, 54, 0.5);
    }
    section {
      margin: 2rem 0;
      padding: 0 2rem;
    }
    h2 {
      color: #333;
      font-size: 1.5rem;
      font-weight: 600;
      margin: 1.5rem 0 1rem 0;
      border-bottom: 2px solid #e0e0e0;
      padding-bottom: 0.5rem;
    }
    h3 {
      color: #555;
      font-size: 1.2rem;
      font-weight: 600;
      margin: 1rem 0 0.5rem 0;
    }
    table {
      border-collapse: collapse;
      width: 100%;
      margin: 1rem 0;
      background: white;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
      border-radius: 8px;
      overflow: hidden;
    }
    thead {
      background: #f5f5f5;
    }
    th, td {
      padding: 0.875rem 1rem;
      text-align: left;
      border-bottom: 1px solid #e0e0e0;
    }
    th {
      font-weight: 600;
      color: #555;
      text-transform: uppercase;
      font-size: 0.85rem;
      letter-spacing: 0.5px;
    }
    tbody tr:hover {
      background: #f9f9f9;
    }
    tbody tr:last-child td {
      border-bottom: none;
    }
    .metric-value {
      font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
      font-weight: 600;
      color: #667eea;
    }
    code, pre {
      background: #f5f5f5;
      padding: 0.25rem 0.5rem;
      border-radius: 4px;
      font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
      font-size: 0.9rem;
      overflow-x: auto;
    }
    pre {
      padding: 1rem;
      border: 1px solid #e0e0e0;
      border-radius: 6px;
      background: #fafafa;
    }
    .monitor-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 1.5rem;
      margin: 1.5rem 0;
    }
    .monitor-card {
      border: 1px solid #e0e0e0;
      border-radius: 8px;
      padding: 1.25rem;
      background: white;
      box-shadow: 0 2px 4px rgba(0,0,0,0.08);
      transition: transform 0.2s, box-shadow 0.2s;
    }
    .monitor-card:hover {
      transform: translateY(-2px);
      box-shadow: 0 4px 8px rgba(0,0,0,0.12);
    }
    .monitor-card h3 {
      margin: 0 0 0.75rem 0;
      font-size: 1.1rem;
      color: #333;
    }
    .monitor-card small {
      color: #888;
      font-weight: normal;
      font-size: 0.85rem;
    }
    .monitor-summary {
      width: 100%;
      font-size: 0.9rem;
      border-collapse: collapse;
      margin-top: 0.75rem;
    }
    .monitor-summary td {
      border: none;
      padding: 0.25rem 0.5rem;
    }
    .monitor-summary td:first-child {
      font-weight: 600;
      color: #666;
    }
    .monitor-alerts {
      margin-top: 0.75rem;
      padding-left: 1.5rem;
      color: #d32f2f;
    }
    .monitor-alerts li {
      margin-bottom: 0.5rem;
    }
    .chart-container {
      margin: 2rem 0;
      padding: 1.5rem;
      background: white;
      border-radius: 8px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .chart-container h2 {
      margin-top: 0;
      border-bottom: none;
    }
    .chart-container canvas {
      max-width: 100%;
      height: 320px;
    }
    .policy-banner {
      padding: 1.5rem;
      margin: 2rem;
      border-radius: 8px;
      border-left: 5px solid;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .policy-banner.adopt {
      border-color: #4caf50;
      background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
    }
    .policy-banner.reject {
      border-color: #f44336;
      background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%);
    }
    .policy-banner h2 {
      margin: 0 0 0.75rem 0;
      border-bottom: none;
      font-size: 1.5rem;
    }
    .policy-banner ul {
      margin: 0.75rem 0 0 0;
      padding-left: 1.5rem;
    }
    .policy-banner li {
      margin-bottom: 0.5rem;
    }
    .violations-content {
      background: white;
      padding: 1.5rem;
      border-radius: 8px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .violations-content ul {
      margin: 1rem 0;
      padding-left: 1.5rem;
    }
    .violations-content ul ul {
      margin: 0.5rem 0;
      background: #f9f9f9;
      padding: 0.75rem;
      border-radius: 4px;
      border-left: 3px solid #e0e0e0;
    }
    @media (max-width: 768px) {
      body { padding: 0; }
      section { padding: 0 1rem; }
      .report-header { padding: 1.5rem; }
      .report-header h1 { font-size: 1.5rem; }
      .report-meta { flex-direction: column; gap: 0.75rem; }
      .monitor-grid { grid-template-columns: 1fr; }
      .chart-container canvas { height: 240px; }
    }
"""
    
    if theme == "dark":
        return base_css + """
    body { background: #1e1e1e; color: #e0e0e0; }
    .report-header { background: linear-gradient(135deg, #4a5568 0%, #2d3748 100%); }
    section { background: #2d2d2d; }
    table { background: #2d2d2d; }
    thead { background: #3a3a3a; }
    th, td { border-bottom: 1px solid #404040; }
    tbody tr:hover { background: #353535; }
    .monitor-card { background: #2d2d2d; border-color: #404040; }
    .chart-container { background: #2d2d2d; }
    .violations-content { background: #2d2d2d; }
    code, pre { background: #1a1a1a; color: #e0e0e0; }
    h2 { color: #e0e0e0; border-bottom-color: #404040; }
    h3 { color: #d0d0d0; }
"""
    elif theme == "minimal":
        return """
    * { box-sizing: border-box; }
    body { 
      font-family: system-ui, sans-serif;
      line-height: 1.6;
      margin: 2rem;
      color: #333;
      background: #ffffff;
    }
    h1, h2, h3 { color: #333; margin: 1.5rem 0 1rem 0; }
    table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
    th, td { border: 1px solid #ddd; padding: 0.75rem; text-align: left; }
    th { background: #f5f5f5; }
    .monitor-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1rem; }
    .monitor-card { border: 1px solid #ddd; padding: 1rem; }
    .chart-container { margin: 2rem 0; }
    .chart-container canvas { max-width: 100%; height: 320px; }
    .policy-banner { padding: 1rem; margin: 1.5rem 0; border-left: 4px solid; }
    .policy-banner.adopt { border-color: #4caf50; background: #e8f5e9; }
    .policy-banner.reject { border-color: #f44336; background: #ffebee; }
"""
    else:  # default
        return base_css


def _build_coverage_chart(coverage: Dict[str, Any] | None) -> Dict[str, Any] | None:
    """Build chart configuration for MR coverage by category."""
    if not coverage:
        return None
    
    categories = coverage.get("categories") or {}
    if not categories:
        return None
    
    labels = []
    baseline_rates = []
    candidate_rates = []
    
    for category, stats in categories.items():
        labels.append(category)
        baseline_pr = stats.get("baseline_pass_rate")
        candidate_pr = stats.get("candidate_pass_rate")
        baseline_rates.append(round(float(baseline_pr * 100), 1) if baseline_pr is not None else 0)
        candidate_rates.append(round(float(candidate_pr * 100), 1) if candidate_pr is not None else 0)
    
    return {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "label": "Baseline Pass Rate (%)",
                    "backgroundColor": "#4caf50",
                    "data": baseline_rates,
                },
                {
                    "label": "Candidate Pass Rate (%)",
                    "backgroundColor": "#2196f3",
                    "data": candidate_rates,
                },
            ],
        },
        "options": {
            "responsive": True,
            "plugins": {
                "title": {
                    "display": True,
                    "text": "MR Coverage by Category",
                },
                "legend": {"display": True},
            },
            "scales": {
                "y": {
                    "beginAtZero": True,
                    "suggestedMax": 100,
                },
            },
        },
    }

