"""
Command-line interface for Metamorphic Guard.
"""

import click
import json
import sys
from .harness import run_eval
from .gate import decide_adopt
from .util import write_report
from .specs import list_tasks


@click.command()
@click.option('--task', required=True, help='Task name to evaluate')
@click.option('--baseline', required=True, help='Path to baseline implementation')
@click.option('--candidate', required=True, help='Path to candidate implementation')
@click.option('--n', default=400, help='Number of test cases (default: 400)')
@click.option('--seed', default=42, help='Random seed (default: 42)')
@click.option('--timeout-s', default=2.0, help='Timeout per test in seconds (default: 2.0)')
@click.option('--mem-mb', default=512, help='Memory limit in MB (default: 512)')
@click.option('--alpha', default=0.05, help='Significance level for CI (default: 0.05)')
@click.option('--improve-delta', default=0.02, help='Minimum improvement threshold (default: 0.02)')
@click.option('--violation-cap', default=25, help='Max violations to report (default: 25)')
@click.option('--parallel', type=int, help='Number of parallel processes (not implemented yet)')
def main(task, baseline, candidate, n, seed, timeout_s, mem_mb, alpha, improve_delta, violation_cap, parallel):
    """Compare baseline and candidate implementations using metamorphic testing."""
    
    # Validate task exists
    available_tasks = list_tasks()
    if task not in available_tasks:
        click.echo(f"Error: Task '{task}' not found. Available tasks: {available_tasks}", err=True)
        sys.exit(1)
    
    try:
        # Run evaluation
        click.echo(f"Running evaluation: {task}")
        click.echo(f"Baseline: {baseline}")
        click.echo(f"Candidate: {candidate}")
        click.echo(f"Test cases: {n}, Seed: {seed}")
        
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
            parallel=parallel
        )
        
        # Make adoption decision
        decision = decide_adopt(result, improve_delta)
        result["decision"] = decision
        
        # Write report
        report_path = write_report(result)
        
        # Print summary
        click.echo("\n" + "="*60)
        click.echo("EVALUATION SUMMARY")
        click.echo("="*60)
        click.echo(f"Task: {result['task']}")
        click.echo(f"Test cases: {result['n']}")
        click.echo(f"Seed: {result['seed']}")
        click.echo()
        click.echo("BASELINE:")
        click.echo(f"  Pass rate: {result['baseline']['pass_rate']:.3f} ({result['baseline']['passes']}/{result['baseline']['total']})")
        click.echo()
        click.echo("CANDIDATE:")
        click.echo(f"  Pass rate: {result['candidate']['pass_rate']:.3f} ({result['candidate']['passes']}/{result['candidate']['total']})")
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
        
        # Exit with appropriate code
        if decision['adopt']:
            click.echo("✅ Candidate accepted!")
            sys.exit(0)
        else:
            click.echo("❌ Candidate rejected!")
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error during evaluation: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
