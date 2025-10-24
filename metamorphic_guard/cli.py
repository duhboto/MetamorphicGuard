"""
Command-line interface for Metamorphic Guard.
"""

import sys

import click

from .gate import decide_adopt
from .harness import run_eval
from .specs import list_tasks
from .util import write_report


@click.command()
@click.option("--task", required=True, help="Task name to evaluate")
@click.option("--baseline", required=True, help="Path to baseline implementation")
@click.option("--candidate", required=True, help="Path to candidate implementation")
@click.option("--n", default=400, show_default=True, help="Number of test cases to generate")
@click.option("--seed", default=42, show_default=True, help="Random seed for generators")
@click.option("--timeout-s", default=2.0, show_default=True, help="Timeout per test (seconds)")
@click.option("--mem-mb", default=512, show_default=True, help="Memory limit per test (MB)")
@click.option("--alpha", default=0.05, show_default=True, help="Significance level for bootstrap CI")
@click.option(
    "--improve-delta",
    default=0.02,
    show_default=True,
    help="Minimum improvement threshold for adoption",
)
@click.option("--violation-cap", default=25, show_default=True, help="Maximum violations to record")
@click.option(
    "--parallel",
    type=int,
    default=1,
    show_default=True,
    help="Number of concurrent workers for sandbox execution",
)
@click.option(
    "--bootstrap-samples",
    type=int,
    default=1000,
    show_default=True,
    help="Bootstrap resamples for confidence interval estimation",
)
def main(
    task: str,
    baseline: str,
    candidate: str,
    n: int,
    seed: int,
    timeout_s: float,
    mem_mb: int,
    alpha: float,
    improve_delta: float,
    violation_cap: int,
    parallel: int,
    bootstrap_samples: int,
) -> None:
    """Compare baseline and candidate implementations using metamorphic testing."""

    available_tasks = list_tasks()
    if task not in available_tasks:
        click.echo(
            f"Error: Task '{task}' not found. Available tasks: {available_tasks}",
            err=True,
        )
        sys.exit(1)

    try:
        click.echo(f"Running evaluation: {task}")
        click.echo(f"Baseline: {baseline}")
        click.echo(f"Candidate: {candidate}")
        click.echo(f"Test cases: {n}, Seed: {seed}")
        click.echo(f"Parallel workers: {parallel}")

        result = run_eval(
            task_name=task,
            baseline_path=baseline,
            candidate_path=candidate,
            n=n,
            seed=seed,
            timeout_s=timeout_s,
            mem_mb=mem_mb,
            alpha=alpha,
            violation_cap=violation_cap,
            parallel=parallel,
            improve_delta=improve_delta,
            bootstrap_samples=bootstrap_samples,
        )

        decision = decide_adopt(result, improve_delta)
        result["decision"] = decision

        report_path = write_report(result)

        click.echo("\n" + "=" * 60)
        click.echo("EVALUATION SUMMARY")
        click.echo("=" * 60)
        click.echo(f"Task: {result['task']}")
        click.echo(f"Test cases: {result['n']}")
        click.echo(f"Seed: {result['seed']}")
        click.echo()
        click.echo("BASELINE:")
        click.echo(
            f"  Pass rate: {result['baseline']['pass_rate']:.3f} "
            f"({result['baseline']['passes']}/{result['baseline']['total']})"
        )
        click.echo()
        click.echo("CANDIDATE:")
        click.echo(
            f"  Pass rate: {result['candidate']['pass_rate']:.3f} "
            f"({result['candidate']['passes']}/{result['candidate']['total']})"
        )
        click.echo(f"  Property violations: {len(result['candidate']['prop_violations'])}")
        click.echo(f"  MR violations: {len(result['candidate']['mr_violations'])}")
        click.echo()
        click.echo("IMPROVEMENT:")
        click.echo(f"  Delta: {result['delta_pass_rate']:.3f}")
        click.echo(f"  95% CI: [{result['delta_ci'][0]:.3f}, {result['delta_ci'][1]:.3f}]")
        click.echo()
        click.echo("DECISION:")
        click.echo(f"  Adopt: {decision['adopt']}")
        click.echo(f"  Reason: {decision['reason']}")
        click.echo()
        click.echo(f"Report saved to: {report_path}")

        if decision["adopt"]:
            click.echo("✅ Candidate accepted!")
            sys.exit(0)

        click.echo("❌ Candidate rejected!")
        sys.exit(1)

    except Exception as exc:  # pragma: no cover - defensive surface
        click.echo(f"Error during evaluation: {exc}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
