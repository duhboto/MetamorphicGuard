"""
Utility functions for file operations and report generation.
"""

import hashlib
import inspect
import json
import os
import platform
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, Optional

_SHA_CACHE: Dict[tuple[str, int], str] = {}


def sha256_file(path: str) -> str:
    """Compute a deterministic SHA256 hash for a file or directory tree."""
    hash_sha256 = hashlib.sha256()
    target = Path(path)

    try:
        mtime = target.stat().st_mtime_ns
    except FileNotFoundError:
        mtime = 0
    cache_key = (str(target.resolve()), mtime)
    cached = _SHA_CACHE.get(cache_key)
    if cached is not None:
        return cached

    if target.is_file():
        with target.open("rb") as file_obj:
            for chunk in iter(lambda: file_obj.read(4096), b""):
                hash_sha256.update(chunk)
        digest = hash_sha256.hexdigest()
        _SHA_CACHE[cache_key] = digest
        return digest

    if target.is_dir():
        hash_sha256.update(b"dir")

        entries = sorted(
            (p for p in target.rglob("*") if p.is_file()),
            key=lambda p: p.relative_to(target).as_posix(),
        )

        for entry in entries:
            rel_path = entry.relative_to(target).as_posix().encode("utf-8")
            hash_sha256.update(rel_path)
            with entry.open("rb") as file_obj:
                for chunk in iter(lambda: file_obj.read(4096), b""):
                    hash_sha256.update(chunk)
        digest = hash_sha256.hexdigest()
        _SHA_CACHE[cache_key] = digest
        return digest

    raise FileNotFoundError(f"Path not found: {path}")


def write_report(payload: dict, *, directory: str | Path | None = None) -> str:
    """
    Write a JSON report to disk and return its path.

    The destination directory can be supplied explicitly, provided via the
    METAMORPHIC_GUARD_REPORT_DIR environment variable, or discovered by looking
    for a project root that contains a pyproject.toml/.git marker.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"report_{timestamp}.json"

    reports_dir = _select_reports_dir(directory)
    reports_dir.mkdir(parents=True, exist_ok=True)

    filepath = reports_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return str(filepath)


def hash_callable(func: Callable[..., Any]) -> str:
    """Return a stable hash for the source of a callable."""
    try:
        source = inspect.getsource(func)
    except (OSError, TypeError):
        # Fallback to repr when source is unavailable (builtins, lambdas in REPL, etc.).
        source = repr(func)
    normalized = source.strip().encode("utf-8", "ignore")
    return hashlib.sha256(normalized).hexdigest()


def compute_spec_fingerprint(spec: Any) -> dict[str, Any]:
    """Compute hashes for the critical components of a task spec."""

    properties = [
        {
            "description": prop.description,
            "mode": prop.mode,
            "hash": hash_callable(prop.check),
        }
        for prop in spec.properties
    ]

    relations = [
        {
            "name": relation.name,
            "expect": relation.expect,
            "hash": hash_callable(relation.transform),
        }
        for relation in spec.relations
    ]

    return {
        "gen_inputs": hash_callable(spec.gen_inputs),
        "properties": properties,
        "relations": relations,
        "equivalence": hash_callable(spec.equivalence),
        "formatters": {
            "fmt_in": hash_callable(spec.fmt_in),
            "fmt_out": hash_callable(spec.fmt_out),
        },
    }


def get_environment_fingerprint() -> dict[str, str]:
    """Capture runtime environment metadata for audit trails."""

    return {
        "python_version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "executable": sys.executable,
    }


def collect_job_metadata() -> Dict[str, Any]:
    """Capture Git commit, repository status, and host metadata for reports."""
    metadata: Dict[str, Any] = {}

    try:
        import socket
        metadata["hostname"] = socket.gethostname()
    except Exception:
        metadata["hostname"] = None

    metadata["executable"] = sys.executable
    metadata["python_version"] = platform.python_version()

    git_dir = Path.cwd() / ".git"
    if not git_dir.exists():
        return metadata

    try:
        import subprocess

        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        metadata["git_commit"] = commit.stdout.strip()

        status = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        )
        metadata["git_dirty"] = bool(status.stdout.strip())
    except Exception:
        metadata.setdefault("git_commit", None)
        metadata.setdefault("git_dirty", None)

    return metadata


def _select_reports_dir(directory: str | Path | None) -> Path:
    """Determine the directory used for report artifacts."""
    if directory is not None:
        return Path(directory).expanduser()

    env_dir = os.environ.get("METAMORPHIC_GUARD_REPORT_DIR")
    if env_dir:
        return Path(env_dir).expanduser()

    project_root = _discover_project_root(Path.cwd())
    if project_root is not None:
        return project_root / "reports"

    return Path.cwd() / "reports"


def _discover_project_root(start: Path) -> Path | None:
    """
    Attempt to locate the project root by searching for common markers.

    We walk up from the provided starting directory looking for either a Git
    repository or a pyproject.toml file.
    """
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists() or (candidate / "pyproject.toml").exists():
            return candidate
    return None


def write_failed_artifacts(
    result: dict,
    *,
    directory: str | Path | None = None,
    limit: Optional[int] = None,
    ttl_days: Optional[int] = None,
    run_id: Optional[str] = None,
) -> Optional[Path]:
    """Persist failed case information for later diagnostics."""
    artifact_dir = directory or os.getenv("METAMORPHIC_GUARD_FAILED_DIR")
    if artifact_dir is None:
        project_root = _discover_project_root(Path.cwd())
        if project_root is None:
            return None
        artifact_dir = project_root / "reports" / "failed_cases"
    path = Path(artifact_dir)
    path.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    prefix = run_id or f"failed_{result.get('task', 'task')}"
    filename = f"{prefix}_{timestamp}.json"
    payload = {
        "task": result.get("task"),
        "baseline": result.get("baseline", {}),
        "candidate": result.get("candidate", {}),
        "config": result.get("config", {}),
        "job_metadata": result.get("job_metadata", {}),
        "run_id": run_id,
    }
    target = path / filename
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _prune_failed_artifacts(path, limit=limit, ttl_days=ttl_days, now=now)
    return target


def _prune_failed_artifacts(
    directory: Path,
    *,
    limit: Optional[int],
    ttl_days: Optional[int],
    now: datetime,
) -> None:
    files = sorted(directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    if ttl_days is not None and ttl_days >= 0:
        cutoff = now - timedelta(days=ttl_days)
        for file_path in list(files):
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            if mtime < cutoff:
                file_path.unlink(missing_ok=True)
                files.remove(file_path)

    if limit is not None and limit > 0 and len(files) > limit:
        for file_path in files[limit:]:
            file_path.unlink(missing_ok=True)
