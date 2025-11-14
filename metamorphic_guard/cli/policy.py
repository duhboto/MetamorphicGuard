"""
Policy snapshotting and rollback helpers.
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import click

SNAPSHOT_DIR = Path("policies/history")


@click.group("policy")
def policy_group() -> None:
    """Manage policy versions."""


@policy_group.command("snapshot")
@click.argument("policy_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--label", type=str, default=None, help="Optional label for the snapshot.")
def snapshot_policy(policy_path: Path, label: str | None) -> None:
    """Create a timestamped snapshot of a policy file."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    stem = policy_path.stem.replace(" ", "_")
    label_part = f"-{label}" if label else ""
    target = SNAPSHOT_DIR / f"{stem}{label_part}-{timestamp}{policy_path.suffix}"
    shutil.copy2(policy_path, target)
    click.echo(f"Snapshot created: {target}")


@policy_group.command("list")
def list_snapshots() -> None:
    """List stored policy snapshots."""
    if not SNAPSHOT_DIR.exists():
        click.echo("No snapshots found.")
        return
    for file in sorted(SNAPSHOT_DIR.glob("*.toml")):
        click.echo(file)


@policy_group.command("rollback")
@click.argument("snapshot", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("destination", type=click.Path(dir_okay=False, path_type=Path))
def rollback_snapshot(snapshot: Path, destination: Path) -> None:
    """Rollback to a snapshot by copying it back to a destination policy file."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(snapshot, destination)
    click.echo(f"Rolled back {destination} to {snapshot}")

