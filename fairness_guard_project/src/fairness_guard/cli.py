"""Command-line interface for the Fairness Guard project."""

from __future__ import annotations

import json
from pathlib import Path

import click
from rich import box
from rich.console import Console
from rich.table import Table

from . import FairnessMetrics, evaluate_candidate

console = Console()


@click.group()
def main() -> None:
    """Gate credit approval models with fairness-aware metamorphic testing."""


@main.command("evaluate")
@click.option(
    "--candidate",
    "candidate_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to the candidate credit policy implementation.",
)
@click.option(
    "--baseline",
    "baseline_path",
    required=False,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Optional baseline override (defaults to bundled baseline_model.py).",
)
@click.option("--n", "test_cases", default=400, show_default=True, help="Number of test datasets.")
@click.option("--seed", default=42, show_default=True, help="Random seed.")
@click.option("--timeout-s", default=2.0, show_default=True, help="Sandbox timeout per evaluation.")
@click.option("--mem-mb", default=512, show_default=True, help="Sandbox memory limit.")
@click.option(
    "--improve-delta",
    default=0.0,
    show_default=True,
    help="Minimum improvement required for the confidence interval lower bound.",
)
@click.option(
    "--min-pass-rate",
    default=0.85,
    show_default=True,
    help="Minimum candidate pass rate.",
)
@click.option(
    "--report-dir",
    default=None,
    type=click.Path(file_okay=False, writable=True, path_type=Path),
    help="Directory for generated JSON reports.",
)
@click.option(
    "--executor",
    default=None,
    type=str,
    help="Sandbox executor backend (e.g. 'docker').",
)
@click.option(
    "--executor-config",
    default=None,
    type=str,
    help="JSON config passed to the sandbox executor.",
)
def evaluate_command(
    candidate_path: Path,
    baseline_path: Path | None,
    test_cases: int,
    seed: int,
    timeout_s: float,
    mem_mb: int,
    improve_delta: float,
    min_pass_rate: float,
    report_dir: Path | None,
    executor: str | None,
    executor_config: str | None,
) -> None:
    """Evaluate a candidate credit approval policy and print the adoption decision."""
    parsed_executor_config = None
    if executor_config:
        try:
            parsed_executor_config = json.loads(executor_config)
            if not isinstance(parsed_executor_config, dict):
                raise ValueError("Executor config must be a JSON object.")
        except Exception as exc:
            raise click.ClickException(f"Invalid executor config: {exc}") from exc

    outcome = evaluate_candidate(
        candidate_path,
        baseline_path=baseline_path,
        test_cases=test_cases,
        seed=seed,
        timeout_s=timeout_s,
        mem_mb=mem_mb,
        improve_delta=improve_delta,
        min_pass_rate=min_pass_rate,
        report_dir=report_dir,
        executor=executor,
        executor_config=parsed_executor_config,
    )

    table = Table(title="Fairness Guard Result", box=box.SIMPLE_HEAVY)
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Candidate", str(outcome.candidate_path))
    table.add_row("Adopt?", "✅ Yes" if outcome.adopted else "❌ No")
    table.add_row("Reason", outcome.reason)
    table.add_row("Δ Pass Rate", f"{outcome.delta_pass_rate:.4f}")
    table.add_row("Δ 95% CI", f"[{outcome.ci_lower:.4f}, {outcome.ci_upper:.4f}]")
    table.add_row("Report", str(outcome.report_path))
    table.add_row(
        "Candidate Fairness Gap", f"{outcome.candidate_metrics.fairness_gap:.4f}"
    )
    table.add_row(
        "Baseline Fairness Gap", f"{outcome.baseline_metrics.fairness_gap:.4f}"
    )
    table.add_row(
        "Candidate Group Rates",
        _format_group_rates(outcome.candidate_metrics),
    )
    table.add_row(
        "Baseline Group Rates",
        _format_group_rates(outcome.baseline_metrics),
    )

    console.print(table)


def _format_group_rates(metrics: FairnessMetrics) -> str:
    if not metrics.group_approval_rates:
        return "n/a"
    return ", ".join(
        f"{group}:{rate:.2%}"
        for group, rate in sorted(metrics.group_approval_rates.items())
    )


if __name__ == "__main__":
    main()
