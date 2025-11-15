"""
CLI command for risk monitoring and assessment.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import click

from ..risk_monitoring import (
    RiskCategory,
    RiskLevel,
    get_risk_monitor,
)


@click.group("risk")
def risk_group() -> None:
    """Risk monitoring and assessment commands."""
    pass


@risk_group.command("status")
@click.option(
    "--category",
    type=click.Choice([c.value for c in RiskCategory], case_sensitive=False),
    help="Filter by risk category",
)
@click.option(
    "--format",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    help="Output format",
)
def risk_status(category: Optional[str], format: str) -> None:
    """Show current risk status."""
    monitor = get_risk_monitor()

    if category:
        category_enum = RiskCategory(category.lower())
        indicators = monitor.get_indicators(category_enum)
    else:
        indicators = monitor.get_indicators()

    if format == "json":
        output = {
            "indicators": [
                {
                    "category": i.category.value,
                    "name": i.name,
                    "current_value": i.current_value,
                    "warning_threshold": i.warning_threshold,
                    "critical_threshold": i.critical_threshold,
                    "unit": i.unit,
                    "level": i.get_level().value,
                    "description": i.description,
                }
                for i in indicators
            ],
            "summary": monitor.get_summary(),
        }
        click.echo(json.dumps(output, indent=2))
    else:
        click.echo("=" * 80)
        click.echo("RISK STATUS")
        click.echo("=" * 80)

        if indicators:
            click.echo("\nIndicators:")
            for indicator in indicators:
                level = indicator.get_level()
                level_color = {
                    RiskLevel.LOW: "green",
                    RiskLevel.MEDIUM: "yellow",
                    RiskLevel.HIGH: "red",
                    RiskLevel.CRITICAL: "red",
                }.get(level, "white")

                click.echo(
                    f"  {indicator.category.value.upper()}: {indicator.name} = "
                    f"{indicator.current_value}{indicator.unit} "
                    f"(warning: {indicator.warning_threshold}{indicator.unit}, "
                    f"critical: {indicator.critical_threshold}{indicator.unit}) "
                    f"[{level.value.upper()}]"
                )
        else:
            click.echo("\nNo indicators registered.")

        summary = monitor.get_summary()
        click.echo(f"\nSummary:")
        click.echo(f"  Total indicators: {summary['total_indicators']}")
        click.echo(f"  Total alerts: {summary['total_alerts']}")
        click.echo(f"  Alerts by level: {summary['alerts_by_level']}")
        click.echo(f"  Indicators by level: {summary['indicators_by_level']}")


@risk_group.command("alerts")
@click.option(
    "--category",
    type=click.Choice([c.value for c in RiskCategory], case_sensitive=False),
    help="Filter by risk category",
)
@click.option(
    "--level",
    type=click.Choice([l.value for l in RiskLevel], case_sensitive=False),
    help="Filter by alert level",
)
@click.option(
    "--format",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    help="Output format",
)
def risk_alerts(category: Optional[str], level: Optional[str], format: str) -> None:
    """Show active risk alerts."""
    monitor = get_risk_monitor()

    category_enum = RiskCategory(category.lower()) if category else None
    level_enum = RiskLevel(level.lower()) if level else None

    alerts = monitor.get_alerts(category=category_enum, level=level_enum)

    if format == "json":
        output = {
            "alerts": [
                {
                    "category": a.indicator.category.value,
                    "indicator": a.indicator.name,
                    "level": a.level.value,
                    "message": a.message,
                    "timestamp": a.timestamp,
                    "recommendations": a.recommendations,
                }
                for a in alerts
            ],
        }
        click.echo(json.dumps(output, indent=2))
    else:
        click.echo("=" * 80)
        click.echo("RISK ALERTS")
        click.echo("=" * 80)

        if alerts:
            for alert in alerts:
                click.echo(f"\n[{alert.level.value.upper()}] {alert.message}")
                click.echo(f"  Category: {alert.indicator.category.value}")
                click.echo(f"  Time: {alert.timestamp}")
                if alert.recommendations:
                    click.echo("  Recommendations:")
                    for rec in alert.recommendations:
                        click.echo(f"    - {rec}")
        else:
            click.echo("\nNo active alerts.")


@risk_group.command("update")
@click.argument("indicator")
@click.argument("value", type=float)
def risk_update(indicator: str, value: float) -> None:
    """Update a risk indicator value."""
    monitor = get_risk_monitor()

    alert = monitor.update_indicator(indicator, value)

    if alert:
        click.echo(f"⚠️  Alert triggered: {alert.message}")
        if alert.recommendations:
            click.echo("Recommendations:")
            for rec in alert.recommendations:
                click.echo(f"  - {rec}")
    else:
        click.echo(f"✅ Indicator '{indicator}' updated to {value}")


@risk_group.command("register")
@click.argument("category")
@click.argument("name")
@click.argument("warning_threshold", type=float)
@click.argument("critical_threshold", type=float)
@click.option("--unit", default="", help="Unit of measurement")
@click.option("--description", default="", help="Description of the indicator")
def risk_register(
    category: str,
    name: str,
    warning_threshold: float,
    critical_threshold: float,
    unit: str,
    description: str,
) -> None:
    """Register a new risk indicator."""
    monitor = get_risk_monitor()

    try:
        category_enum = RiskCategory(category.lower())
    except ValueError:
        raise click.BadParameter(f"Invalid category: {category}")

    monitor.register_indicator(
        category_enum,
        name,
        warning_threshold,
        critical_threshold,
        unit,
        description,
    )

    click.echo(f"✅ Registered indicator '{name}' in category '{category}'")


@risk_group.command("export")
@click.argument("output", type=click.Path(path_type=Path))
@click.option(
    "--format",
    type=click.Choice(["json", "csv"], case_sensitive=False),
    default="json",
    help="Export format",
)
def risk_export(output: Path, format: str) -> None:
    """Export risk data to a file."""
    monitor = get_risk_monitor()

    if format == "json":
        data = {
            "indicators": [
                {
                    "category": i.category.value,
                    "name": i.name,
                    "current_value": i.current_value,
                    "warning_threshold": i.warning_threshold,
                    "critical_threshold": i.critical_threshold,
                    "unit": i.unit,
                    "level": i.get_level().value,
                    "description": i.description,
                }
                for i in monitor.get_indicators()
            ],
            "alerts": [
                {
                    "category": a.indicator.category.value,
                    "indicator": a.indicator.name,
                    "level": a.level.value,
                    "message": a.message,
                    "timestamp": a.timestamp,
                    "recommendations": a.recommendations,
                }
                for a in monitor.get_alerts()
            ],
            "summary": monitor.get_summary(),
        }

        with open(output, "w") as f:
            json.dump(data, f, indent=2)

        click.echo(f"✅ Exported risk data to {output}")
    else:
        # CSV format
        import csv

        with open(output, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Category", "Name", "Value", "Unit", "Level", "Description"])

            for indicator in monitor.get_indicators():
                writer.writerow([
                    indicator.category.value,
                    indicator.name,
                    indicator.current_value,
                    indicator.unit,
                    indicator.get_level().value,
                    indicator.description,
                ])

        click.echo(f"✅ Exported risk data to {output}")

