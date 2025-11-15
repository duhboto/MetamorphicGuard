"""
CLI commands for exporting performance profiling reports.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import click

from metamorphic_guard.types import JSONDict


@click.command("export-profile")
@click.argument("json_report", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--format",
    type=click.Choice(["json", "csv"], case_sensitive=False),
    default="json",
    help="Export format (json or csv)",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Output file path (defaults to <report_name>_profile.<format>)",
)
def export_profile(json_report: Path, format: str, output: Path | None) -> None:
    """Export performance profiling data from a JSON report."""
    
    # Load report
    with json_report.open("r", encoding="utf-8") as f:
        report_data: JSONDict = json.load(f)
    
    # Extract performance profiler data
    monitors = report_data.get("monitors", {})
    if isinstance(monitors, dict):
        monitor_entries = monitors.values()
    else:
        monitor_entries = monitors or []
    
    profiler_data = None
    for entry in monitor_entries:
        if isinstance(entry, dict) and entry.get("type") == "performance_profiler":
            profiler_data = entry
            break
    
    if not profiler_data:
        click.echo("No performance profiler data found in report.", err=True)
        return
    
    # Determine output path
    if output is None:
        output = json_report.parent / f"{json_report.stem}_profile.{format.lower()}"
    
    # Export based on format
    if format.lower() == "json":
        with output.open("w", encoding="utf-8") as f:
            json.dump(profiler_data, f, indent=2)
        click.echo(f"Performance profile exported to {output}")
    
    elif format.lower() == "csv":
        with output.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            
            # Write header
            writer.writerow([
                "Role", "Metric", "Value", "Unit"
            ])
            
            # Write latency data
            latency = profiler_data.get("latency", {})
            for role in ["baseline", "candidate"]:
                role_data = latency.get(role, {})
                if role_data:
                    writer.writerow([role, "Count", role_data.get("count", 0), "cases"])
                    writer.writerow([role, "Min Latency", role_data.get("min_ms"), "ms"])
                    writer.writerow([role, "Max Latency", role_data.get("max_ms"), "ms"])
                    writer.writerow([role, "Mean Latency", role_data.get("mean_ms"), "ms"])
                    writer.writerow([role, "Median Latency", role_data.get("median_ms"), "ms"])
                    writer.writerow([role, "StdDev Latency", role_data.get("stddev_ms"), "ms"])
                    
                    percentiles = role_data.get("percentiles", {})
                    for p_name, p_value in percentiles.items():
                        writer.writerow([role, f"Latency {p_name}", p_value, "ms"])
            
            # Write cost data
            cost = profiler_data.get("cost", {})
            for role in ["baseline", "candidate"]:
                role_data = cost.get(role, {})
                if role_data:
                    writer.writerow([role, "Cost Count", role_data.get("count", 0), "cases"])
                    writer.writerow([role, "Total Cost", role_data.get("total_usd", 0), "USD"])
                    writer.writerow([role, "Mean Cost", role_data.get("mean_usd"), "USD"])
                    writer.writerow([role, "Min Cost", role_data.get("min_usd"), "USD"])
                    writer.writerow([role, "Max Cost", role_data.get("max_usd"), "USD"])
                    if "stddev_usd" in role_data:
                        writer.writerow([role, "StdDev Cost", role_data.get("stddev_usd"), "USD"])
            
            # Write token data
            tokens = profiler_data.get("tokens", {})
            for role in ["baseline", "candidate"]:
                role_data = tokens.get(role, {})
                if role_data:
                    writer.writerow([role, "Token Count", role_data.get("count", 0), "cases"])
                    writer.writerow([role, "Total Tokens", role_data.get("total", 0), "tokens"])
                    writer.writerow([role, "Mean Tokens", role_data.get("mean"), "tokens"])
                    writer.writerow([role, "Min Tokens", role_data.get("min"), "tokens"])
                    writer.writerow([role, "Max Tokens", role_data.get("max"), "tokens"])
                    if "stddev" in role_data:
                        writer.writerow([role, "StdDev Tokens", role_data.get("stddev"), "tokens"])
            
            # Write success rate
            success_rate = profiler_data.get("success_rate", {})
            for role in ["baseline", "candidate"]:
                role_data = success_rate.get(role, {})
                if role_data:
                    writer.writerow([role, "Total Cases", role_data.get("total", 0), "cases"])
                    writer.writerow([role, "Successes", role_data.get("successes", 0), "cases"])
                    writer.writerow([role, "Failures", role_data.get("failures", 0), "cases"])
                    writer.writerow([role, "Success Rate", role_data.get("success_rate"), "ratio"])
            
            # Write comparison data
            comparison = profiler_data.get("comparison", {})
            latency_comp = comparison.get("latency", {})
            if latency_comp:
                writer.writerow(["comparison", "Baseline Mean Latency", latency_comp.get("baseline_mean_ms"), "ms"])
                writer.writerow(["comparison", "Candidate Mean Latency", latency_comp.get("candidate_mean_ms"), "ms"])
                writer.writerow(["comparison", "Latency Delta", latency_comp.get("delta_ms"), "ms"])
                writer.writerow(["comparison", "Latency Delta %", latency_comp.get("delta_percent"), "%"])
            
            cost_comp = comparison.get("cost", {})
            if cost_comp:
                writer.writerow(["comparison", "Baseline Mean Cost", cost_comp.get("baseline_mean_usd"), "USD"])
                writer.writerow(["comparison", "Candidate Mean Cost", cost_comp.get("candidate_mean_usd"), "USD"])
                writer.writerow(["comparison", "Cost Delta", cost_comp.get("delta_usd"), "USD"])
                writer.writerow(["comparison", "Cost Delta %", cost_comp.get("delta_percent"), "%"])
            
            success_comp = comparison.get("success_rate", {})
            if success_comp:
                writer.writerow(["comparison", "Baseline Success Rate", success_comp.get("baseline"), "ratio"])
                writer.writerow(["comparison", "Candidate Success Rate", success_comp.get("candidate"), "ratio"])
                writer.writerow(["comparison", "Success Rate Delta", success_comp.get("delta"), "ratio"])
                writer.writerow(["comparison", "Success Rate Delta %", success_comp.get("delta_percent"), "%"])
        
        click.echo(f"Performance profile exported to {output}")

