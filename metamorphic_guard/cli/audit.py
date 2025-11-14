"""
CLI helpers for audit log inspection and verification.
"""

from __future__ import annotations

import json
import os
from typing import List

import click

from ..audit import audit_log_path, read_audit_entries, verify_entry_signature


@click.group("audit")
def audit_group() -> None:
    """Audit log utilities."""


@audit_group.command("tail")
@click.option("--count", default=20, show_default=True, help="Number of entries to display.")
def audit_tail(count: int) -> None:
    """Display the most recent audit entries."""
    entries = read_audit_entries()
    if not entries:
        click.echo("No audit entries found.")
        return
    for entry in entries[-count:]:
        click.echo(json.dumps(entry))


@audit_group.command("verify")
@click.option("--key", type=str, default=None, help="Override audit signing key (defaults to env).")
def audit_verify(key: str | None) -> None:
    """
    Verify audit log signatures using the configured HMAC key.
    """
    entries = read_audit_entries()
    if not entries:
        click.echo("No audit entries found.")
        return

    key = key or os.getenv("METAMORPHIC_GUARD_AUDIT_KEY")
    signed_entries: List[dict] = [entry for entry in entries if entry.get("signature")]
    if signed_entries and not key:
        raise click.ClickException(
            "Audit log contains signed entries but no key was provided. "
            "Set METAMORPHIC_GUARD_AUDIT_KEY or pass --key."
        )

    invalid_indices = []
    for idx, entry in enumerate(entries):
        if entry.get("signature"):
            if not verify_entry_signature(entry, key=key):  # type: ignore[arg-type]
                invalid_indices.append(idx)

    if invalid_indices:
        raise click.ClickException(f"Audit verification failed for entries: {invalid_indices}")

    click.echo(f"✓ Verified {len(signed_entries)} signed audit entries at {audit_log_path()}")

