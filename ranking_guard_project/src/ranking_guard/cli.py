"""Command-line interface for the ranking guard project."""

from __future__ import annotations

from pathlib import Path

import click
from rich import box
from rich.console import Console
from rich.table import Table

from .runner import evaluate_candidate


console = Console()


@click.group()
def main() -> None:
    """Gate ranking algorithm releases using Metamorphic Guard."""


@main.command("evaluate")
@click.option(
    "--candidate",
    "candidate_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to the candidate ranking implementation.",
)
@click.option(
    "--baseline",
    "baseline_path",
    required=False,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Optional baseline override (defaults to bundled baseline_ranker.py).",
)
@click.option("--n", "test_cases", default=400, show_default=True, help="Number of tests.")
@click.option("--seed", default=42, show_default=True, help="Random seed.")
@click.option("--timeout-s", default=2.0, show_default=True, help="Sandbox timeout per call.")
@click.option("--mem-mb", default=512, show_default=True, help="Sandbox memory limit.")
@click.option(
    "--improve-delta",
    default=0.0,
    show_default=True,
    help="Minimum improvement required for the CI lower bound.",
)
@click.option(
    "--min-pass-rate",
    default=0.8,
    show_default=True,
    help="Minimum candidate pass rate.",
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
) -> None:
    """Evaluate a candidate ranking algorithm and print the adoption decision."""
    outcome = evaluate_candidate(
        candidate_path,
        baseline_path=baseline_path,
        test_cases=test_cases,
        seed=seed,
        timeout_s=timeout_s,
        mem_mb=mem_mb,
        improve_delta=improve_delta,
        min_pass_rate=min_pass_rate,
    )

    table = Table(title="Ranking Guard Result", box=box.SIMPLE_HEAVY)
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Candidate", str(outcome.candidate_path))
    table.add_row("Adopt?", "✅ Yes" if outcome.adopted else "❌ No")
    table.add_row("Reason", outcome.reason)
    table.add_row("Δ Pass Rate", f"{outcome.delta_pass_rate:.4f}")
    table.add_row("Δ 95% CI", f"[{outcome.ci_lower:.4f}, {outcome.ci_upper:.4f}]")
    table.add_row("Report", str(outcome.report_path))

    console.print(table)


if __name__ == "__main__":
    main()
