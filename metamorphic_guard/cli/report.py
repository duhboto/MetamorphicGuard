"""
Report generation commands.
"""

from __future__ import annotations

from pathlib import Path

import click

from ..reporting import render_html_report, render_junit_report
from .utils import load_report


@click.command("report")
@click.argument("json_report", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Output path (defaults to <json_report>.html)",
)
def report_command(json_report: Path, output: Path | None) -> None:
    """Generate an HTML report from a JSON evaluation report."""
    result = load_report(json_report)
    output_path = output or json_report.with_suffix(".html")
    render_html_report(result, output_path)
    click.echo(f"HTML report written to {output_path}")

