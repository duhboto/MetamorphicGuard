"""
CLI commands for model registry operations.
"""

from __future__ import annotations

from typing import Optional

import click

from ..model_registry import get_model, get_model_info, list_models


@click.group("model")
def model_group() -> None:
    """Model registry commands."""
    pass


@model_group.command("list")
@click.option(
    "--provider",
    type=str,
    default=None,
    help="Filter models by provider (e.g., 'openai', 'anthropic')",
)
@click.option(
    "--format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format",
)
def list_models_command(provider: Optional[str], format: str) -> None:
    """List all registered models."""
    models = list_models(provider=provider)
    
    if format == "json":
        import json
        output = [get_model_info(m.name) for m in models if get_model_info(m.name)]
        click.echo(json.dumps(output, indent=2))
    else:
        if not models:
            click.echo("No models found.")
            return
        
        click.echo(f"\n{'Name':<40} {'Provider':<15} {'Max Tokens':<12} {'Description'}")
        click.echo("=" * 100)
        
        for model in models:
            max_tokens_str = str(model.max_tokens) if model.max_tokens else "N/A"
            desc = model.description or ""
            if len(desc) > 40:
                desc = desc[:37] + "..."
            click.echo(f"{model.name:<40} {model.provider:<15} {max_tokens_str:<12} {desc}")
        
        click.echo(f"\nTotal: {len(models)} model(s)")


@model_group.command("info")
@click.argument("model_name")
@click.option(
    "--format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format",
)
def model_info_command(model_name: str, format: str) -> None:
    """Show detailed information about a model."""
    model = get_model(model_name)
    if not model:
        click.echo(f"Model '{model_name}' not found in registry.", err=True)
        click.echo("Use 'mg model list' to see available models.")
        return
    
    info = get_model_info(model_name)
    if not info:
        click.echo(f"Could not retrieve info for model '{model_name}'", err=True)
        return
    
    if format == "json":
        import json
        click.echo(json.dumps(info, indent=2))
    else:
        click.echo(f"\nModel: {info['name']}")
        click.echo(f"Provider: {info['provider']}")
        click.echo(f"Description: {info.get('description', 'N/A')}")
        click.echo(f"\nPricing (per {info['pricing_unit']} tokens):")
        click.echo(f"  Prompt: ${info['pricing']['prompt']:.6f}")
        click.echo(f"  Completion: ${info['pricing']['completion']:.6f}")
        click.echo(f"\nLimits:")
        if info['max_tokens']:
            click.echo(f"  Max tokens per request: {info['max_tokens']:,}")
        if info['max_context_length']:
            click.echo(f"  Max context length: {info['max_context_length']:,}")
        click.echo(f"\nFeatures:")
        click.echo(f"  System prompt: {'Yes' if info['supports_system_prompt'] else 'No'}")
        click.echo(f"  Streaming: {'Yes' if info['supports_streaming'] else 'No'}")
        click.echo(f"  Temperature range: {info['temperature_range'][0]:.1f} - {info['temperature_range'][1]:.1f}")
        if info.get('constraints'):
            click.echo(f"\nConstraints:")
            for key, value in info['constraints'].items():
                click.echo(f"  {key}: {value}")


@model_group.command("pricing")
@click.argument("model_name")
@click.option(
    "--unit",
    type=click.Choice(["1k", "1m"]),
    default="1k",
    help="Pricing unit (1k = per 1K tokens, 1m = per 1M tokens)",
)
def model_pricing_command(model_name: str, unit: str) -> None:
    """Show pricing information for a model."""
    from ..model_registry import get_pricing
    
    pricing = get_pricing(model_name, unit=unit)
    if not pricing:
        click.echo(f"Model '{model_name}' not found or has no pricing information.", err=True)
        return
    
    click.echo(f"\nPricing for {model_name} (per {unit} tokens):")
    click.echo(f"  Prompt: ${pricing['prompt']:.6f}")
    click.echo(f"  Completion: ${pricing['completion']:.6f}")
    click.echo(f"  Total (1 prompt + 1 completion): ${pricing['prompt'] + pricing['completion']:.6f}")

