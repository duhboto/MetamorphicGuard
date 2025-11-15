"""
CLI command for comparing multiple LLM models.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click

from ..model_comparison import compare_models, compare_with_baseline
from ..types import JSONValue


@click.command("compare")
@click.option(
    "--models",
    required=True,
    help="JSON array of model configs, e.g., '[{\"model\":\"gpt-3.5-turbo\",\"provider\":\"openai\"}]'",
)
@click.option(
    "--case",
    required=True,
    help="Test case input (JSON string or path to JSON file)",
)
@click.option(
    "--n",
    default=100,
    type=int,
    help="Number of test cases",
)
@click.option(
    "--seed",
    default=42,
    type=int,
    help="Random seed",
)
@click.option(
    "--rank-by",
    type=click.Choice(["pass_rate", "cost_usd", "latency_ms", "combined"], case_sensitive=False),
    default="pass_rate",
    help="Metric to rank models by",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    help="Output file for comparison report (JSON)",
)
@click.option(
    "--bootstrap/--no-bootstrap",
    default=True,
    help="Compute bootstrap confidence intervals",
)
def compare_command(
    models: str,
    case: str,
    n: int,
    seed: int,
    rank_by: str,
    output: Path | None,
    bootstrap: bool,
) -> None:
    """
    Compare multiple LLM models on the same test cases.

    Example:
        mg compare \\
            --models '[{"model":"gpt-3.5-turbo","provider":"openai"},{"model":"gpt-4","provider":"openai"}]' \\
            --case '{"user":"Explain quantum computing"}' \\
            --n 50
    """
    # Parse models
    try:
        if Path(models).exists():
            with open(models) as f:
                models_data = json.load(f)
        else:
            models_data = json.loads(models)
    except json.JSONDecodeError as e:
        raise click.BadParameter(f"Invalid JSON for --models: {e}")

    if not isinstance(models_data, list):
        raise click.BadParameter("--models must be a JSON array")

    # Parse case
    try:
        if Path(case).exists():
            with open(case) as f:
                case_data = json.load(f)
        else:
            case_data = json.loads(case)
    except json.JSONDecodeError as e:
        raise click.BadParameter(f"Invalid JSON for --case: {e}")

    # Run comparison
    click.echo(f"Comparing {len(models_data)} models...")
    result = compare_models(
        models=models_data,
        case=case_data,
        n=n,
        seed=seed,
        bootstrap=bootstrap,
        rank_by=rank_by,
    )

    # Display results
    click.echo("\n" + "=" * 60)
    click.echo("MODEL COMPARISON RESULTS")
    click.echo("=" * 60)
    click.echo(f"\nBest Model: {result['best_model']}")
    click.echo(f"\nRanking (by {rank_by}):")
    for i, model_name in enumerate(result["ranking"], start=1):
        model_result = next(m for m in result["models"] if m["model"] == model_name)
        click.echo(
            f"  {i}. {model_name}: "
            f"pass_rate={model_result['pass_rate']:.3f}, "
            f"cost=${model_result['cost_usd']:.4f}, "
            f"latency={model_result['avg_latency_ms']:.1f}ms"
        )

    click.echo(f"\nSummary:")
    summary = result["summary"]
    click.echo(f"  Total models: {summary['total_models']}")
    click.echo(f"  Best pass rate: {summary['best_pass_rate']:.3f}")
    click.echo(f"  Worst pass rate: {summary['worst_pass_rate']:.3f}")
    click.echo(f"  Average pass rate: {summary['avg_pass_rate']:.3f}")
    click.echo(f"  Total cost: ${summary['total_cost']:.4f}")
    click.echo(f"  Average cost: ${summary['avg_cost']:.4f}")
    click.echo(f"  Average latency: {summary['avg_latency']:.1f}ms")

    # Save output if requested
    if output:
        with open(output, "w") as f:
            json.dump(result, f, indent=2)
        click.echo(f"\nReport saved to: {output}")


@click.command("compare-baseline")
@click.option(
    "--baseline",
    required=True,
    help="Baseline model identifier",
)
@click.option(
    "--candidates",
    required=True,
    help="Comma-separated list of candidate model identifiers",
)
@click.option(
    "--case",
    required=True,
    help="Test case input (JSON string or path to JSON file)",
)
@click.option(
    "--baseline-provider",
    default="openai",
    help="Provider for baseline model",
)
@click.option(
    "--candidate-provider",
    help="Provider for candidate models (defaults to baseline-provider)",
)
@click.option(
    "--n",
    default=100,
    type=int,
    help="Number of test cases",
)
@click.option(
    "--seed",
    default=42,
    type=int,
    help="Random seed",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    help="Output file for comparison report (JSON)",
)
@click.option(
    "--bootstrap/--no-bootstrap",
    default=True,
    help="Compute bootstrap confidence intervals",
)
def compare_baseline_command(
    baseline: str,
    candidates: str,
    case: str,
    baseline_provider: str,
    candidate_provider: str | None,
    n: int,
    seed: int,
    output: Path | None,
    bootstrap: bool,
) -> None:
    """
    Compare multiple candidate models against a baseline.

    Example:
        mg compare-baseline \\
            --baseline gpt-3.5-turbo \\
            --candidates gpt-4,claude-3-haiku \\
            --case '{"user":"Explain quantum computing"}' \\
            --n 50
    """
    # Parse candidates
    candidate_list = [c.strip() for c in candidates.split(",") if c.strip()]

    # Parse case
    try:
        if Path(case).exists():
            with open(case) as f:
                case_data = json.load(f)
        else:
            case_data = json.loads(case)
    except json.JSONDecodeError as e:
        raise click.BadParameter(f"Invalid JSON for --case: {e}")

    # Run comparison
    click.echo(f"Comparing {len(candidate_list)} candidates against baseline {baseline}...")
    result = compare_with_baseline(
        baseline_model=baseline,
        candidate_models=candidate_list,
        case=case_data,
        baseline_provider=baseline_provider,
        candidate_provider=candidate_provider,
        n=n,
        seed=seed,
        bootstrap=bootstrap,
    )

    # Display results
    click.echo("\n" + "=" * 60)
    click.echo("BASELINE COMPARISON RESULTS")
    click.echo("=" * 60)
    click.echo(f"\nBest Model: {result['best_model']}")
    click.echo(f"\nRanking:")
    for i, model_name in enumerate(result["ranking"], start=1):
        model_result = next(m for m in result["models"] if m["model"] == model_name)
        is_baseline = model_name == baseline
        marker = " [BASELINE]" if is_baseline else ""
        click.echo(
            f"  {i}. {model_name}{marker}: "
            f"pass_rate={model_result['pass_rate']:.3f}, "
            f"cost=${model_result['cost_usd']:.4f}, "
            f"latency={model_result['avg_latency_ms']:.1f}ms"
        )

    # Save output if requested
    if output:
        with open(output, "w") as f:
            json.dump(result, f, indent=2)
        click.echo(f"\nReport saved to: {output}")

