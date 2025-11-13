"""
Regression guard command.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

import click

from .utils import flatten_dict, get_nested, load_report


def _parse_metric_threshold(ctx: click.Context, param: click.Option, value: Tuple[str, ...]) -> Dict[Tuple[str, Tuple[str, ...]], float]:
    thresholds: Dict[Tuple[str, Tuple[str, ...]], float] = {}
    for entry in value:
        if "=" not in entry:
            raise click.BadParameter("Expected format metric:path=value", ctx=ctx, param=param)
        left, right = entry.split("=", 1)
        try:
            threshold = float(right)
        except ValueError as exc:
            raise click.BadParameter(f"Threshold must be numeric: {entry}") from exc
        if ":" not in left:
            raise click.BadParameter("Expected format metric:path=value", ctx=ctx, param=param)
        metric_name, raw_path = left.split(":", 1)
        path = tuple(part for part in raw_path.split(".") if part)
        if not path:
            raise click.BadParameter(f"Path portion empty in {entry}", ctx=ctx, param=param)
        thresholds[(metric_name, path)] = threshold
    return thresholds


@click.command("regression-guard")
@click.argument("baseline_report", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("candidate_report", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--metric-threshold",
    "metric_thresholds",
    multiple=True,
    callback=_parse_metric_threshold,
    help="Guard metric deltas: metric:path=value enforces |candidate metric[path]| <= value.",
)
@click.option(
    "--require-provenance-match",
    is_flag=True,
    default=False,
    help="Fail if sandbox provenance fingerprints differ between reports.",
)
def regression_guard_command(
    baseline_report: Path,
    candidate_report: Path,
    metric_thresholds: Dict[Tuple[str, Tuple[str, ...]], float],
    require_provenance_match: bool,
) -> None:
    """Fail the build when metrics regress or provenance changes unexpectedly."""

    baseline = load_report(baseline_report)
    candidate = load_report(candidate_report)

    violations: list[str] = []

    if require_provenance_match:
        base_sandbox = flatten_dict(
            (baseline.get("provenance") or {}).get("sandbox") or {},
            prefix="sandbox",
        )
        cand_sandbox = flatten_dict(
            (candidate.get("provenance") or {}).get("sandbox") or {},
            prefix="sandbox",
        )
        if base_sandbox != cand_sandbox:
            diff_keys = sorted(set(base_sandbox.keys()) ^ set(cand_sandbox.keys()))
            changed_keys = [
                key
                for key in sorted(set(base_sandbox.keys()) & set(cand_sandbox.keys()))
                if base_sandbox[key] != cand_sandbox[key]
            ]
            message_lines = ["Sandbox provenance mismatch detected."]
            if diff_keys:
                message_lines.append(f"Missing keys: {', '.join(diff_keys)}")
            if changed_keys:
                sample = ", ".join(changed_keys[:5])
                message_lines.append(f"Changed keys: {sample}")
            violations.append("\n".join(message_lines))

    candidate_metrics = candidate.get("metrics") or {}
    for (metric_name, path), max_value in metric_thresholds.items():
        metric_entry = candidate_metrics.get(metric_name)
        if metric_entry is None:
            violations.append(f"Metric '{metric_name}' missing in candidate report.")
            continue
        try:
            metric_value = get_nested(metric_entry, path)
        except KeyError:
            violations.append(
                f"Metric '{metric_name}' missing path '{'.'.join(path)}' in candidate report."
            )
            continue
        if not isinstance(metric_value, (int, float)):
            violations.append(
                f"Metric '{metric_name}' path '{'.'.join(path)}' is not numeric (value={metric_value!r})."
            )
            continue
        if abs(float(metric_value)) > max_value:
            violations.append(
                f"Metric '{metric_name}' path '{'.'.join(path)}' exceeded {max_value} (observed {metric_value})."
            )

    if violations:
        for line in violations:
            click.echo(f"FAIL: {line}", err=True)
        import sys
        sys.exit(1)

    click.echo("Regression guard passed.")

