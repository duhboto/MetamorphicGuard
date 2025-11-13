"""
Provenance diff command.
"""

from __future__ import annotations

from pathlib import Path

import click

from .utils import flatten_dict, load_report


@click.command("provenance-diff")
@click.argument("report_a", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("report_b", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def provenance_diff_command(report_a: Path, report_b: Path) -> None:
    """Compare sandbox provenance between two reports."""

    try:
        data_a = load_report(report_a)
        data_b = load_report(report_b)
    except Exception as exc:
        click.echo(f"Error: Failed to parse report JSON ({exc})", err=True)
        import sys
        sys.exit(1)

    sandbox_a = (data_a.get("provenance") or {}).get("sandbox")
    sandbox_b = (data_b.get("provenance") or {}).get("sandbox")

    if sandbox_a is None and sandbox_b is None:
        click.echo("Neither report contains sandbox provenance.")
        return

    flat_a = flatten_dict(sandbox_a or {}, prefix="sandbox")
    flat_b = flatten_dict(sandbox_b or {}, prefix="sandbox")

    all_keys = sorted(set(flat_a.keys()) | set(flat_b.keys()))
    differences: list[str] = []

    for key in all_keys:
        value_a = flat_a.get(key)
        value_b = flat_b.get(key)
        if value_a == value_b:
            continue
        differences.append(
            f"- {key}: {value_a!r} != {value_b!r}"
        )

    if not differences:
        click.echo("Sandbox provenance matches.")
        return

    click.echo("Sandbox provenance differences:")
    for diff in differences:
        click.echo(diff)

