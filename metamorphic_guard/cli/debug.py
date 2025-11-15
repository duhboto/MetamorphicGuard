"""
Debugging tools for Metamorphic Guard evaluations.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import click

from ..types import JSONDict


@click.command("inspect-violation")
@click.argument("report_file", type=click.Path(exists=True, path_type=Path))
@click.option("--violation-index", type=int, default=0, help="Index of violation to inspect")
@click.option("--role", type=click.Choice(["baseline", "candidate"]), default="candidate", help="Which role to inspect")
@click.option("--type", type=click.Choice(["property", "metamorphic"]), default="property", help="Violation type")
def inspect_violation(
    report_file: Path,
    violation_index: int,
    role: str,
    type: str,
) -> None:
    """Inspect a specific violation from a report."""
    
    with report_file.open("r", encoding="utf-8") as f:
        report: JSONDict = json.load(f)
    
    role_data = report.get(role, {})
    
    if type == "property":
        violations = role_data.get("prop_violations", [])
        violation_type = "Property"
    else:
        violations = role_data.get("mr_violations", [])
        violation_type = "Metamorphic Relation"
    
    if violation_index >= len(violations):
        click.echo(f"Error: Only {len(violations)} {type} violations found (index {violation_index} requested)", err=True)
        return
    
    violation = violations[violation_index]
    
    click.echo(f"\n{violation_type} Violation #{violation_index + 1} ({role}):")
    click.echo("=" * 60)
    
    for key, value in violation.items():
        if key == "input" or key == "output":
            click.echo(f"\n{key.capitalize()}:")
            click.echo(f"  {value}")
        elif key == "error":
            click.echo(f"\nError:")
            click.echo(f"  {value}")
        else:
            click.echo(f"{key.capitalize()}: {value}")
    
    click.echo()


@click.command("trace-case")
@click.argument("report_file", type=click.Path(exists=True, path_type=Path))
@click.option("--case-index", type=int, required=True, help="Test case index to trace")
@click.option("--role", type=click.Choice(["baseline", "candidate"]), default="candidate", help="Which role to trace")
def trace_case(
    report_file: Path,
    case_index: int,
    role: str,
) -> None:
    """Trace execution of a specific test case."""
    
    with report_file.open("r", encoding="utf-8") as f:
        report: JSONDict = json.load(f)
    
    # Get results (if available in report)
    # Note: Full results may not be in report, only violations
    role_data = report.get(role, {})
    
    click.echo(f"\nTracing case #{case_index} ({role}):")
    click.echo("=" * 60)
    
    # Check if case has violations
    prop_violations = [v for v in role_data.get("prop_violations", []) if v.get("test_case") == case_index]
    mr_violations = [v for v in role_data.get("mr_violations", []) if v.get("test_case") == case_index]
    
    if prop_violations:
        click.echo(f"\nProperty Violations ({len(prop_violations)}):")
        for v in prop_violations:
            click.echo(f"  - {v.get('input', 'N/A')}")
            if "error" in v:
                click.echo(f"    Error: {v['error']}")
    
    if mr_violations:
        click.echo(f"\nMetamorphic Relation Violations ({len(mr_violations)}):")
        for v in mr_violations:
            click.echo(f"  - Relation: {v.get('relation', 'N/A')}")
            click.echo(f"    Input: {v.get('input', 'N/A')}")
            click.echo(f"    Output: {v.get('output', 'N/A')}")
            if "error" in v:
                click.echo(f"    Error: {v['error']}")
    
    if not prop_violations and not mr_violations:
        click.echo(f"\n✅ Case #{case_index} passed all checks")
    
    click.echo()


@click.command("compare-reports")
@click.argument("report1", type=click.Path(exists=True, path_type=Path))
@click.argument("report2", type=click.Path(exists=True, path_type=Path))
@click.option("--format", type=click.Choice(["table", "json"]), default="table", help="Output format")
def compare_reports(
    report1: Path,
    report2: Path,
    format: str,
) -> None:
    """Compare two evaluation reports."""
    
    with report1.open("r", encoding="utf-8") as f:
        r1: JSONDict = json.load(f)
    
    with report2.open("r", encoding="utf-8") as f:
        r2: JSONDict = json.load(f)
    
    if format == "json":
        comparison = {
            "report1": {
                "delta_pass_rate": r1.get("delta_pass_rate"),
                "adopt": r1.get("decision", {}).get("adopt"),
            },
            "report2": {
                "delta_pass_rate": r2.get("delta_pass_rate"),
                "adopt": r2.get("decision", {}).get("adopt"),
            },
            "difference": {
                "delta_delta": (r2.get("delta_pass_rate", 0) - r1.get("delta_pass_rate", 0)),
                "decision_changed": (
                    r1.get("decision", {}).get("adopt") != r2.get("decision", {}).get("adopt")
                ),
            },
        }
        click.echo(json.dumps(comparison, indent=2))
    else:
        click.echo("\nReport Comparison:")
        click.echo("=" * 60)
        click.echo(f"\nReport 1: {report1.name}")
        click.echo(f"  Δ Pass Rate: {r1.get('delta_pass_rate', 0):.4f}")
        click.echo(f"  Adopt: {r1.get('decision', {}).get('adopt', False)}")
        click.echo(f"\nReport 2: {report2.name}")
        click.echo(f"  Δ Pass Rate: {r2.get('delta_pass_rate', 0):.4f}")
        click.echo(f"  Adopt: {r2.get('decision', {}).get('adopt', False)}")
        
        delta_diff = r2.get("delta_pass_rate", 0) - r1.get("delta_pass_rate", 0)
        decision_changed = r1.get("decision", {}).get("adopt") != r2.get("decision", {}).get("adopt")
        
        click.echo(f"\nDifference:")
        click.echo(f"  ΔΔ Pass Rate: {delta_diff:+.4f}")
        click.echo(f"  Decision Changed: {'Yes' if decision_changed else 'No'}")
        click.echo()


@click.group("debug")
def debug_group() -> None:
    """Debugging tools for Metamorphic Guard."""
    pass


debug_group.add_command(inspect_violation, "inspect-violation")
debug_group.add_command(trace_case, "trace-case")
debug_group.add_command(compare_reports, "compare-reports")

