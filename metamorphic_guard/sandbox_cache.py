"""
Cache helpers for sandbox snapshot management.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Dict, Tuple

import hashlib
_CACHE_ROOT = Path(tempfile.gettempdir()) / "metamorphic_guard_cache"
_CACHE_ROOT.mkdir(parents=True, exist_ok=True)
_SNAPSHOT_CACHE: Dict[str, Tuple[Path, bool]] = {}
_SNAPSHOT_LOCK = threading.Lock()


def snapshot_source(source: Path) -> tuple[Path, bool]:
    """Return a cached snapshot path and whether it represents a directory."""
    resolved = source.resolve()
    try:
        mtime = resolved.stat().st_mtime_ns
    except FileNotFoundError as exc:  # pragma: no cover - source removed mid-run
        raise FileNotFoundError(f"Source path not found: {resolved}") from exc

    key_material = f"{resolved}:{mtime}".encode("utf-8")
    digest = hashlib.sha256(key_material).hexdigest()

    with _SNAPSHOT_LOCK:
        cached = _SNAPSHOT_CACHE.get(digest)
        if cached and cached[0].exists():
            return cached

        snapshot_base = _CACHE_ROOT / digest
        if snapshot_base.exists():
            shutil.rmtree(snapshot_base)
        snapshot_base.mkdir(parents=True, exist_ok=True)

        if resolved.is_dir():
            target = snapshot_base / resolved.name
            shutil.copytree(resolved, target, dirs_exist_ok=True)
            result = (target, True)
        else:
            target = snapshot_base / resolved.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(resolved, target)
            result = (target, False)

        _SNAPSHOT_CACHE[digest] = result
        return result


def clone_snapshot_dir(snapshot: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(snapshot, destination, copy_function=link_or_copy)


def clone_snapshot_file(snapshot: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()
    link_or_copy(snapshot, destination)


def link_or_copy(src: str | Path, dst: str | Path) -> None:
    src_path = os.fspath(src)
    dst_path = os.fspath(dst)
    try:
        os.link(src_path, dst_path)
    except OSError:
        shutil.copy2(src_path, dst_path)


__all__ = [
    "snapshot_source",
    "clone_snapshot_dir",
    "clone_snapshot_file",
    "link_or_copy",
]

