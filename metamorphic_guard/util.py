"""
Utility functions for file operations and report generation.
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path


def sha256_file(path: str) -> str:
    """Compute a deterministic SHA256 hash for a file or directory tree."""
    hash_sha256 = hashlib.sha256()
    target = Path(path)

    if target.is_file():
        with target.open("rb") as file_obj:
            for chunk in iter(lambda: file_obj.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

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
        return hash_sha256.hexdigest()

    raise FileNotFoundError(f"Path not found: {path}")


def write_report(payload: dict) -> str:
    """Write JSON report to reports directory with timestamp."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"report_{timestamp}.json"
    
    # Ensure reports directory exists
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    
    filepath = reports_dir / filename
    
    with open(filepath, 'w') as f:
        json.dump(payload, f, indent=2)
    
    return str(filepath)
