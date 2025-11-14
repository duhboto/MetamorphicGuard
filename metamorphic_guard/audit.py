"""
Lightweight audit logging for evaluation decisions.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

_AUDIT_LOCK = threading.Lock()
_CANONICAL_FIELDS = ("timestamp", "task", "decision", "config", "hashes")


def write_audit_entry(payload: Dict[str, Any]) -> None:
    """
    Persist an append-only audit record to disk.

    If METAMORPHIC_GUARD_AUDIT_KEY is set, entries are signed with HMAC-SHA256.
    """
    entry = canonicalize_entry(
        {
            "timestamp": time.time(),
            "task": payload.get("task"),
            "decision": payload.get("decision"),
            "config": payload.get("config"),
            "hashes": payload.get("hashes"),
        }
    )
    raw = json.dumps(entry, sort_keys=True).encode("utf-8")
    audit_key = os.getenv("METAMORPHIC_GUARD_AUDIT_KEY")
    if audit_key:
        signature = hmac.new(audit_key.encode("utf-8"), raw, hashlib.sha256).hexdigest()
        entry["signature"] = signature

    path = audit_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _AUDIT_LOCK:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")


def audit_log_path() -> Path:
    """Return the configured audit log path."""
    return Path(os.getenv("METAMORPHIC_GUARD_AUDIT_LOG", "reports/audit.log"))


def canonicalize_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Return entry restricted to canonical fields for signing."""
    return {field: entry.get(field) for field in _CANONICAL_FIELDS if field in entry}


def sign_entry(entry: Dict[str, Any], *, key: str) -> str:
    raw = json.dumps(canonicalize_entry(entry), sort_keys=True).encode("utf-8")
    return hmac.new(key.encode("utf-8"), raw, hashlib.sha256).hexdigest()


def verify_entry_signature(entry: Dict[str, Any], *, key: str) -> bool:
    signature = entry.get("signature")
    if not signature:
        return False
    expected = sign_entry(entry, key=key)
    return hmac.compare_digest(str(signature), expected)


def read_audit_entries(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Read audit entries from disk (most recent last)."""
    path = audit_log_path()
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        lines: Iterable[str]
        if limit is None:
            lines = handle.readlines()
        else:
            lines = _tail(handle, limit)
    entries: List[Dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                entries.append(parsed)
        except json.JSONDecodeError:
            continue
    return entries


def _tail(handle, limit: int) -> List[str]:
    handle.seek(0, os.SEEK_END)
    buffer = ""
    lines: List[str] = []
    pointer = handle.tell()
    while pointer > 0 and len(lines) < limit:
        pointer -= 1
        handle.seek(pointer)
        char = handle.read(1)
        if char == "\n":
            if buffer:
                lines.append(buffer[::-1])
                buffer = ""
        else:
            buffer += char
    if buffer:
        lines.append(buffer[::-1])
    return list(reversed(lines[-limit:]))


__all__ = [
    "write_audit_entry",
    "audit_log_path",
    "read_audit_entries",
    "verify_entry_signature",
    "canonicalize_entry",
    "sign_entry",
]

