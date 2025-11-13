"""
Plugin management commands.
"""

from __future__ import annotations

import json

import click

from ..plugins import plugin_registry


@click.group("plugin")
def plugin_group() -> None:
    """Inspect installed Metamorphic Guard plugins."""
    pass


@plugin_group.command("list")
@click.option(
    "--kind",
    type=click.Choice(["monitor", "dispatcher", "executor", "mutant", "judge", "task", "relation", "all"], case_sensitive=False),
    default="all",
    show_default=True,
    help="Filter by plugin kind.",
)
@click.option("--json", "json_flag", is_flag=True, help="Emit plugin list as JSON.")
def plugin_list(kind: str, json_flag: bool) -> None:
    """List available plugins."""
    registry = plugin_registry(kind)
    if not registry:
        click.echo("No plugins discovered.")
        return

    rows = []
    for key, definition in sorted(registry.items()):
        plugin_kind = "monitor" if definition.group == "metamorphic_guard.monitors" else "dispatcher"
        metadata = definition.metadata
        rows.append(
            {
                "name": metadata.name or definition.name,
                "entry": key,
                "kind": plugin_kind,
                "version": metadata.version,
                "sandbox": metadata.sandbox,
                "description": metadata.description,
            }
        )

    if json_flag:
        click.echo(json.dumps(rows, indent=2))
        return

    name_width = max(len(r["name"]) for r in rows)
    kind_width = max(len(r["kind"]) for r in rows)
    version_width = max(len(r["version"] or "-") for r in rows)

    header = f"{'NAME'.ljust(name_width)}  {'KIND'.ljust(kind_width)}  {'VERSION'.ljust(version_width)}  SANDBOX  DESCRIPTION"
    click.echo(header)
    click.echo("-" * len(header))
    for row in rows:
        name = row["name"].ljust(name_width)
        kind_str = row["kind"].ljust(kind_width)
        version = (row["version"] or "-").ljust(version_width)
        sandbox = "yes" if row["sandbox"] else "no"
        description = row["description"] or ""
        click.echo(f"{name}  {kind_str}  {version}  {sandbox:>3}   {description}")


@plugin_group.command("info")
@click.argument("plugin_name", type=str)
@click.option(
    "--kind",
    type=click.Choice(["monitor", "dispatcher", "executor", "mutant", "judge", "task", "relation"], case_sensitive=False),
    required=True,
    help="Plugin kind.",
)
@click.option("--json", "json_flag", is_flag=True, help="Emit plugin info as JSON.")
def plugin_info(plugin_name: str, kind: str, json_flag: bool) -> None:
    """Show detailed information about a specific plugin."""
    registry = plugin_registry(kind)
    if plugin_name not in registry:
        click.echo(f"Plugin '{plugin_name}' not found for kind '{kind}'", err=True)
        click.echo(f"Available plugins: {sorted(registry.keys())}", err=True)
        import sys
        sys.exit(1)

    definition = registry[plugin_name]
    metadata = definition.metadata

    info = {
        "name": metadata.name or definition.name,
        "entry": plugin_name,
        "kind": kind,
        "version": metadata.version,
        "sandbox": metadata.sandbox,
        "description": metadata.description,
        "group": definition.group,
        "module": definition.module,
    }

    if json_flag:
        click.echo(json.dumps(info, indent=2))
        return

    click.echo(f"Plugin: {info['name']}")
    click.echo(f"Entry: {info['entry']}")
    click.echo(f"Kind: {info['kind']}")
    click.echo(f"Version: {info['version'] or 'N/A'}")
    click.echo(f"Sandboxed: {info['sandbox']}")
    click.echo(f"Description: {info['description'] or 'N/A'}")
    click.echo(f"Module: {info['module']}")

