"""
Utility functions for file operations and report generation.
"""

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path


def sha256_file(path: str) -> str:
    """Compute SHA256 hash of a file."""
    hash_sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest()


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
