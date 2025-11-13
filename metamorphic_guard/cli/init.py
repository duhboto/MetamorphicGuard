"""
Init command for creating starter configuration files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import click


@click.command("init")
@click.option(
    "--path",
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    default=Path("metamorphic_guard.toml"),
    show_default=True,
    help="Configuration file to create.",
)
@click.option("--task", default="top_k", show_default=True)
@click.option("--baseline", default="baseline.py", show_default=True)
@click.option("--candidate", default="candidate.py", show_default=True)
@click.option("--distributed/--no-distributed", default=False, show_default=True)
@click.option("--monitor", "monitor_names", multiple=True, help="Monitors to enable by default.")
@click.option("--interactive/--no-interactive", default=False, show_default=False, help="Launch an interactive wizard.")
def init_command(
    path: Path,
    task: str,
    baseline: str,
    candidate: str,
    distributed: bool,
    monitor_names: Sequence[str],
    interactive: bool,
) -> None:
    """Create a starter TOML configuration file."""

    monitors = list(monitor_names)

    if interactive:
        task = click.prompt("Task name", default=task)
        baseline = click.prompt("Baseline path", default=baseline)
        candidate = click.prompt("Candidate path", default=candidate)
        distributed = click.confirm("Enable distributed execution?", default=distributed)
        monitor_default = ",".join(monitors)
        monitor_input = click.prompt(
            "Monitors (comma separated, blank for none)",
            default=monitor_default,
            show_default=bool(monitor_default),
        )
        monitors = [m.strip() for m in monitor_input.split(",") if m.strip()] if monitor_input else []

    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["[metamorphic_guard]"]
    lines.append(f'task = "{task}"')
    lines.append(f'baseline = "{baseline}"')
    lines.append(f'candidate = "{candidate}"')
    if monitors:
        monitor_str = ", ".join(f'"{name}"' for name in monitors)
        lines.append(f"monitors = [{monitor_str}]")
    if distributed:
        lines.append("")
        lines.append("[metamorphic_guard.queue]")
        lines.append('dispatcher = "queue"')
        lines.append('queue_config = { backend = "redis", url = "redis://localhost:6379/0" }')

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    click.echo(f"Wrote configuration to {path}")

