"""
Stability audit command.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from ..harness import run_eval
from ..stability_audit import audit_to_report, run_stability_audit


@click.command("stability-audit")
@click.option("--task", required=True, help="Task name to evaluate")
@click.option("--baseline", required=True, help="Path to baseline implementation")
@click.option("--candidate", required=True, help="Path to candidate implementation")
@click.option("--n", default=400, show_default=True, help="Number of test cases per run")
@click.option("--seed-start", default=42, show_default=True, help="Starting seed value")
@click.option("--num-seeds", default=10, show_default=True, help="Number of different seeds to test")
@click.option("--min-delta", default=0.02, show_default=True, help="Minimum improvement threshold")
@click.option("--min-pass-rate", default=0.80, show_default=True, help="Minimum candidate pass rate")
@click.option("--ci-method", default="newcombe", show_default=True, help="CI method to use")
@click.option("--output", type=click.Path(path_type=Path), default=None, help="Output JSON file for audit results")
def stability_audit_command(
    task: str,
    baseline: str,
    candidate: str,
    n: int,
    seed_start: int,
    num_seeds: int,
    min_delta: float,
    min_pass_rate: float,
    ci_method: str,
    output: Path | None,
) -> None:
    """Run stability audit across multiple seeds to detect flakiness."""
    
    click.echo(f"Running stability audit: {num_seeds} runs with seeds {seed_start}..{seed_start + num_seeds - 1}")
    click.echo(f"Task: {task}, Baseline: {baseline}, Candidate: {candidate}")
    
    try:
        audit_result = run_stability_audit(
            task_name=task,
            baseline_path=baseline,
            candidate_path=candidate,
            n=n,
            seed_start=seed_start,
            num_seeds=num_seeds,
            min_delta=min_delta,
            min_pass_rate=min_pass_rate,
            ci_method=ci_method,
        )
        
        # Print report
        report = audit_to_report(audit_result)
        click.echo(report)
        
        # Save to file if requested
        if output:
            output.write_text(json.dumps(audit_result, indent=2), encoding="utf-8")
            click.echo(f"\nAudit results saved to: {output}")
        
        # Exit with error if flaky
        if audit_result["flaky"]:
            click.echo("\n⚠️  Flakiness detected! Exiting with error code.", err=True)
            sys.exit(1)
        
    except Exception as e:
        click.echo(f"Error running stability audit: {e}", err=True)
        sys.exit(1)

