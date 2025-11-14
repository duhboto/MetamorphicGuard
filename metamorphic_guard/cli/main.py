"""
Main CLI entry point and command group.
"""

from __future__ import annotations

from typing import Any

import click

from .evaluate import evaluate_command
from .init import init_command
from .plugin import plugin_group
from .power import power_command
from .provenance import provenance_diff_command
from .regression import regression_guard_command
from .replay import replay_command
from .report import report_command
from .scaffold import scaffold_plugin
from .stability import stability_audit_command
from .trace import trace_group


class DefaultCommandGroup(click.Group):
    """Group that falls back to a default command when none is supplied."""

    def __init__(self, *args: Any, default_command: str | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.default_command = default_command

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        if self.default_command:
            if not args:
                args.insert(0, self.default_command)
            elif args[0].startswith("-"):
                args.insert(0, self.default_command)
        return super().parse_args(ctx, args)


@click.group(cls=DefaultCommandGroup, default_command="evaluate")
def main() -> None:
    """Metamorphic Guard command group."""
    pass


# Register all commands
main.add_command(evaluate_command, "evaluate")
main.add_command(init_command, "init")
main.add_command(plugin_group, "plugin")
main.add_command(power_command, "power")
main.add_command(provenance_diff_command, "provenance-diff")
main.add_command(regression_guard_command, "regression-guard")
main.add_command(replay_command, "replay")
main.add_command(report_command, "report")
main.add_command(scaffold_plugin, "scaffold-plugin")
main.add_command(stability_audit_command, "stability-audit")
main.add_command(trace_group, "trace")

