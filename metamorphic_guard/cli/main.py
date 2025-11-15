"""
Main CLI entry point and command group.
"""

from __future__ import annotations

from typing import Any

import click

from .compare import compare_command, compare_baseline_command
from .evaluate import evaluate_command
from .init import init_command
from .model import model_group
from .plugin import plugin_group
from .power import power_command
from .profile import export_profile
from .provenance import provenance_diff_command
from .regression import regression_guard_command
from .replay import replay_command
from .report import report_command
from .risk import risk_group
from .scaffold import scaffold_plugin
from .stability import stability_audit_command
from .trace import trace_group
from .policy import policy_group
from .audit import audit_group
from .mr import mr_group
from .debug import debug_group


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
main.add_command(compare_command, "compare")
main.add_command(compare_baseline_command, "compare-baseline")
main.add_command(model_group, "model")
main.add_command(init_command, "init")
main.add_command(plugin_group, "plugin")
main.add_command(power_command, "power")
main.add_command(provenance_diff_command, "provenance-diff")
main.add_command(regression_guard_command, "regression-guard")
main.add_command(replay_command, "replay")
main.add_command(report_command, "report")
main.add_command(export_profile, "export-profile")
main.add_command(scaffold_plugin, "scaffold-plugin")
main.add_command(stability_audit_command, "stability-audit")
main.add_command(trace_group, "trace")
main.add_command(policy_group, "policy")
main.add_command(mr_group, "mr")
main.add_command(audit_group, "audit")
main.add_command(debug_group, "debug")
main.add_command(risk_group, "risk")

