"""
Policy snapshotting and rollback helpers.
"""

from __future__ import annotations

import shutil
import time
import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from typing import Optional

import click

SNAPSHOT_DIR = Path("policies/history")


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sign_bytes(data: bytes, key: str) -> str:
    return hmac.new(key.encode("utf-8"), data, hashlib.sha256).hexdigest()


def _default_signature_path(policy_path: Path) -> Path:
    return policy_path.with_suffix(f"{policy_path.suffix}.sig")


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


@policy_group.command("sign")
@click.argument("policy_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--signature-path",
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    default=None,
    help="Optional output file for the signature metadata.",
)
@click.option("--key", type=str, default=None, help="Override signing key (defaults to env).")
def sign_policy(policy_path: Path, signature_path: Optional[Path], key: Optional[str]) -> None:
    """Generate a hash (and optional HMAC) for a policy file."""
    data = policy_path.read_bytes()
    sha256 = _hash_file(policy_path)
    key = key or os.getenv("METAMORPHIC_GUARD_AUDIT_KEY")
    record = {
        "path": str(policy_path),
        "sha256": sha256,
        "timestamp": time.time(),
    }
    if key:
        record["hmac_sha256"] = _sign_bytes(data, key)
    target = signature_path or _default_signature_path(policy_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record, indent=2), encoding="utf-8")
    click.echo(f"Signature written to {target}")


@policy_group.command("verify")
@click.argument("policy_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--signature-path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Signature metadata file (defaults to <policy>.sig).",
)
@click.option("--key", type=str, default=None, help="Override verification key (defaults to env).")
@click.option(
    "--require-hmac/--no-require-hmac",
    default=False,
    show_default=True,
    help="Fail if signature file lacks HMAC.",
)
def verify_policy(
    policy_path: Path,
    signature_path: Optional[Path],
    key: Optional[str],
    require_hmac: bool,
) -> None:
    """Verify a policy file against a previously generated signature."""
    target = signature_path or _default_signature_path(policy_path)
    if not target.exists():
        raise click.ClickException(f"Signature file not found: {target}")
    metadata = json.loads(target.read_text(encoding="utf-8"))
    stored_hash = metadata.get("sha256")
    if stored_hash != _hash_file(policy_path):
        raise click.ClickException("Policy hash mismatch.")
    hmac_value = metadata.get("hmac_sha256")
    if hmac_value:
        key = key or os.getenv("METAMORPHIC_GUARD_AUDIT_KEY")
        if not key:
            raise click.ClickException(
                "Signature includes HMAC but no key provided. "
                "Set METAMORPHIC_GUARD_AUDIT_KEY or pass --key."
            )
        computed = _sign_bytes(policy_path.read_bytes(), key)
        if not hmac.compare_digest(hmac_value, computed):
            raise click.ClickException("Policy HMAC verification failed.")
    elif require_hmac:
        raise click.ClickException("Signature missing HMAC.")
    click.echo(f"✓ Policy signature verified ({target})")

