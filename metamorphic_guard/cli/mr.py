"""
CLI helpers for working with metamorphic relation tooling.
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from ..mr import (
    discover_relations,
    library_metadata,
    load_library,
    prioritize_relations,
    validate_relations,
)
from ..specs import get_task, register_spec


@click.group("mr")
def mr_group() -> None:
    """Metamorphic relation utilities."""


@mr_group.command("library")
def mr_library() -> None:
    """List built-in metamorphic relations."""
    entries = library_metadata()
    click.echo(f"Metamorphic relation library ({len(entries)} entries):")
    for entry in entries:
        click.echo(f"- {entry['name']} [{entry['category']}] {entry['description']}")


@mr_group.command("discover")
@click.argument("task")
def mr_discover(task: str) -> None:
    """Suggest relations for a registered task."""
    spec = get_task(task)
    suggestions = discover_relations(spec)
    click.echo(json.dumps(suggestions, indent=2))


@mr_group.command("validate")
@click.argument("task_or_file")
def mr_validate(task_or_file: str) -> None:
    """Validate relations for a task name or spec file."""
    if Path(task_or_file).exists():
        from importlib import import_module

        module_path = Path(task_or_file).resolve()
        spec_name = module_path.stem
        module_dir = str(module_path.parent)
        if module_dir not in ("", "."):
            import sys

            if module_dir not in sys.path:
                sys.path.insert(0, module_dir)
        module = import_module(spec_name)
        spec = module.build_spec() if hasattr(module, "build_spec") else module.spec  # type: ignore[attr-defined]
        if not hasattr(module, "build_spec") and not hasattr(module, "spec"):
            raise click.ClickException(
                f"{task_or_file} must expose build_spec() or spec (Spec instance)"
            )
        if isinstance(spec, str):
            spec = get_task(spec)
        register_spec(f"_tmp_{spec_name}", spec, overwrite=True)
    else:
        spec = get_task(task_or_file)

    issues = validate_relations(spec)
    if not issues:
        click.echo("✓ All relations look good.")
        return
    click.echo("Warnings:")
    for issue in issues:
        click.echo(f" - {issue}")


@mr_group.command("prioritize")
@click.argument("task")
@click.option("--limit", default=5, show_default=True, help="Limit number of MR suggestions.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
    help="Output format.",
)
def mr_prioritize(task: str, limit: int, output_format: str) -> None:
    """Report MR coverage and prioritized suggestions for a task."""
    spec = get_task(task)
    suggestions, coverage = prioritize_relations(spec, max_items=limit)

    payload = {"coverage": coverage, "suggestions": suggestions}
    if output_format == "json":
        click.echo(json.dumps(payload, indent=2))
        return

    click.echo(f"MR coverage density: {coverage['density']}")
    click.echo("Category coverage:")
    for category, stats in coverage["categories"].items():
        click.echo(
            f" - {category}: {stats['relations']} relations / {stats['properties']} props (ratio {stats['coverage_ratio']})"
        )
    if coverage["missing_categories"]:
        click.echo(f"Missing categories: {', '.join(coverage['missing_categories'])}")

    click.echo("")
    click.echo("Suggested additions:")
    if not suggestions:
        click.echo(" - No additional relations recommended.")
        return
    for entry in suggestions:
        click.echo(
            f" - {entry['name']} [{entry['category']}] score {entry['score']}: {entry['reason']} (effort {entry.get('effort')})"
        )

