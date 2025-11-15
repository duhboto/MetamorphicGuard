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
@click.option(
    "--theme",
    type=click.Choice(["default", "dark", "minimal"], case_sensitive=False),
    default="default",
    help="Report theme style",
)
@click.option(
    "--title",
    type=str,
    default=None,
    help="Custom report title (defaults to task name)",
)
@click.option(
    "--no-config",
    is_flag=True,
    default=False,
    help="Hide configuration section",
)
@click.option(
    "--no-metadata",
    is_flag=True,
    default=False,
    help="Hide job metadata section",
)
def report_command(
    json_report: Path,
    output: Path | None,
    theme: str,
    title: str | None,
    no_config: bool,
    no_metadata: bool,
) -> None:
    """Generate an HTML report from a JSON evaluation report."""
    result = load_report(json_report)
    output_path = output or json_report.with_suffix(".html")
    render_html_report(
        result,
        output_path,
        theme=theme,
        title=title,
        show_config=not no_config,
        show_metadata=not no_metadata,
    )
    click.echo(f"HTML report written to {output_path}")

