"""
Power analysis command.
"""

from __future__ import annotations

import sys

import click

from ..power import calculate_power, calculate_sample_size, estimate_mde


@click.command("power")
@click.option("--baseline-rate", required=True, type=float, help="Expected baseline pass rate (0-1)")
@click.option("--lift", type=float, default=None, help="Expected improvement (pass-rate delta). If not provided, calculates MDE.")
@click.option("--n", type=int, default=None, help="Sample size (number of test cases). If not provided, calculates required n.")
@click.option("--alpha", default=0.05, show_default=True, help="Significance level")
@click.option("--power-target", default=0.8, show_default=True, help="Desired statistical power")
@click.option("--min-delta", default=0.02, show_default=True, help="Minimum detectable effect threshold")
def power_command(
    baseline_rate: float,
    lift: float | None,
    n: int | None,
    alpha: float,
    power_target: float,
    min_delta: float,
) -> None:
    """
    Calculate statistical power or required sample size for pass-rate comparisons.
    
    Examples:
    
    \b
    # Calculate required sample size for 2% lift detection
    metamorphic-guard power --baseline-rate 0.92 --lift 0.02
    
    \b
    # Calculate power for given sample size
    metamorphic-guard power --baseline-rate 0.92 --lift 0.02 --n 400
    
    \b
    # Calculate minimum detectable effect for given sample size
    metamorphic-guard power --baseline-rate 0.92 --n 400
    """
    
    if not (0 <= baseline_rate <= 1):
        click.echo("Error: baseline-rate must be between 0 and 1", err=True)
        sys.exit(1)
    
    if lift is not None and not (0 <= lift <= 1):
        click.echo("Error: lift must be between 0 and 1", err=True)
        sys.exit(1)
    
    if n is not None and n <= 0:
        click.echo("Error: n must be positive", err=True)
        sys.exit(1)
    
    click.echo("=" * 60)
    click.echo("Power Analysis")
    click.echo("=" * 60)
    click.echo(f"Baseline pass rate: {baseline_rate:.3f}")
    click.echo(f"Alpha (significance level): {alpha}")
    click.echo(f"Power target: {power_target}")
    click.echo(f"Minimum detectable effect: {min_delta}")
    click.echo("")
    
    if lift is not None:
        candidate_rate = min(1.0, baseline_rate + lift)
        click.echo(f"Expected improvement: {lift:.3f} (candidate rate: {candidate_rate:.3f})")
        
        if n is None:
            # Calculate required sample size
            try:
                required_n = calculate_sample_size(
                    baseline_rate=baseline_rate,
                    min_delta=lift,
                    alpha=alpha,
                    power_target=power_target,
                )
                click.echo(f"\nRequired sample size (n): {required_n}")
                click.echo(f"  To detect Δ ≥ {lift:.3f} with {power_target:.0%} power at α={alpha}")
            except ValueError as e:
                click.echo(f"Error: {e}", err=True)
                sys.exit(1)
        else:
            # Calculate power for given sample size
            power = calculate_power(
                baseline_rate=baseline_rate,
                candidate_rate=candidate_rate,
                sample_size=n,
                alpha=alpha,
                min_delta=min_delta,
            )
            click.echo(f"\nSample size (n): {n}")
            click.echo(f"Statistical power: {power:.3f} ({power:.1%})")
            if power < power_target:
                click.echo(f"⚠️  Power below target ({power_target:.1%})", err=True)
            else:
                click.echo(f"✓ Power meets target ({power_target:.1%})")
    else:
        # Calculate MDE for given sample size
        if n is None:
            click.echo("Error: Either --lift or --n must be provided", err=True)
            sys.exit(1)
        
        try:
            mde = estimate_mde(
                baseline_rate=baseline_rate,
                sample_size=n,
                alpha=alpha,
                power_target=power_target,
            )
            click.echo(f"\nSample size (n): {n}")
            click.echo(f"Minimum detectable effect (MDE): {mde:.3f} ({mde:.1%})")
            click.echo(f"  With {n} cases, you can detect improvements ≥ {mde:.3f} with {power_target:.0%} power")
            
            if mde > min_delta:
                click.echo(f"⚠️  MDE ({mde:.3f}) exceeds threshold ({min_delta:.3f})", err=True)
                click.echo(f"   Consider increasing n or lowering --min-delta")
        except ValueError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
    
    click.echo("")

