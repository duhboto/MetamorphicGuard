"""
Catalog generation command to index evaluation reports.
"""

from __future__ import annotations

import datetime
import html
import json
from pathlib import Path
from typing import Any, Dict, List

import click

from .utils import load_report


@click.command("catalog")
@click.option(
    "--reports-dir",
    "-d",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("reports"),
    help="Directory containing JSON reports",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=Path("reports/index.html"),
    help="Output path for catalog index",
)
@click.option(
    "--title",
    type=str,
    default="Metamorphic Guard Report Catalog",
    help="Catalog page title",
)
def catalog_command(reports_dir: Path, output: Path, title: str) -> None:
    """Generate an HTML catalog of evaluation reports."""
    reports: List[Dict[str, Any]] = []
    
    for report_file in reports_dir.glob("**/*.json"):
        if report_file.name.startswith("catalog"):
            continue
        try:
            data = load_report(report_file)
            # Check if it looks like a Metamorphic Guard report
            if "task" not in data or "baseline" not in data:
                continue
                
            timestamp = datetime.datetime.fromtimestamp(report_file.stat().st_mtime)
            
            reports.append({
                "path": str(report_file.relative_to(output.parent)),
                "filename": report_file.name,
                "task": data.get("task", "Unknown"),
                "timestamp": timestamp,
                "timestamp_str": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "decision": data.get("decision", {}),
                "baseline_pass_rate": data.get("baseline", {}).get("pass_rate", 0.0),
                "candidate_pass_rate": data.get("candidate", {}).get("pass_rate", 0.0),
                "delta": data.get("delta_pass_rate", 0.0),
                "ci": data.get("delta_ci", []),
            })
        except Exception:
            # Skip unreadable files
            continue
    
    # Sort by timestamp descending
    reports.sort(key=lambda x: x["timestamp"], reverse=True)
    
    html_content = _render_catalog_html(reports, title)
    
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html_content, encoding="utf-8")
    click.echo(f"Catalog written to {output}")


def _render_catalog_html(reports: List[Dict[str, Any]], title: str) -> str:
    rows = []
    for report in reports:
        decision = report["decision"]
        adopt = decision.get("adopt", False)
        status_class = "adopt" if adopt else "reject"
        status_icon = "✅" if adopt else "❌"
        
        # Try to find HTML report variant
        json_path = Path(report["path"])
        html_link = report["path"]
        # Heuristic: link to .html if it exists next to .json, otherwise .json
        # Since we don't check file existence relative to output here easily without context,
        # we assume the standard naming convention <name>.html matches <name>.json
        html_candidate = json_path.with_suffix(".html")
        # Ideally we'd check if it exists, but for the catalog we can just link to the HTML version 
        # assuming 'mg report' was run or we want to link to it.
        # Let's link to the HTML version by default as it's nicer.
        link_target = str(html_candidate)
        
        rows.append(
            f"""
            <tr class="{status_class}">
                <td>{html.escape(report["timestamp_str"])}</td>
                <td><a href="{html.escape(link_target)}">{html.escape(report["task"])}</a></td>
                <td><span class="badge {status_class}">{status_icon} {html.escape(str(adopt))}</span></td>
                <td class="metric">{report["baseline_pass_rate"]:.3f}</td>
                <td class="metric">{report["candidate_pass_rate"]:.3f}</td>
                <td class="metric">{report["delta"]:+.3f}</td>
                <td class="metric small">{html.escape(str(report["ci"]))}</td>
                <td class="small">{html.escape(str(decision.get("reason", "")))}</td>
            </tr>
            """
        )
    
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; color: #333; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ margin-top: 0; border-bottom: 2px solid #eee; padding-bottom: 10px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #fafafa; font-weight: 600; color: #555; }}
        tr:hover {{ background: #f9f9f9; }}
        a {{ color: #2196f3; text-decoration: none; font-weight: 500; }}
        a:hover {{ text-decoration: underline; }}
        .metric {{ font-family: monospace; }}
        .badge {{ padding: 4px 8px; border-radius: 4px; font-size: 0.85rem; font-weight: 600; }}
        .badge.adopt {{ background: #e8f5e9; color: #2e7d32; }}
        .badge.reject {{ background: #ffebee; color: #c62828; }}
        .small {{ font-size: 0.85rem; color: #777; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{html.escape(title)}</h1>
        <p>Found {len(reports)} evaluation reports.</p>
        <table>
            <thead>
                <tr>
                    <th>Timestamp</th>
                    <th>Task</th>
                    <th>Decision</th>
                    <th>Baseline</th>
                    <th>Candidate</th>
                    <th>Δ Pass Rate</th>
                    <th>95% CI</th>
                    <th>Reason</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>
    </div>
</body>
</html>
"""

