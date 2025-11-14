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
from typing import Any, Dict

_AUDIT_PATH = Path(os.getenv("METAMORPHIC_GUARD_AUDIT_LOG", "reports/audit.log"))
_AUDIT_LOCK = threading.Lock()


def write_audit_entry(payload: Dict[str, Any]) -> None:
    """
    Persist an append-only audit record to disk.

    If METAMORPHIC_GUARD_AUDIT_KEY is set, entries are signed with HMAC-SHA256.
    """
    entry = {
        "timestamp": time.time(),
        "task": payload.get("task"),
        "decision": payload.get("decision"),
        "config": payload.get("config"),
        "hashes": payload.get("hashes"),
    }
    raw = json.dumps(entry, sort_keys=True).encode("utf-8")
    audit_key = os.getenv("METAMORPHIC_GUARD_AUDIT_KEY")
    if audit_key:
        signature = hmac.new(audit_key.encode("utf-8"), raw, hashlib.sha256).hexdigest()
        entry["signature"] = signature

    _AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _AUDIT_LOCK:
        with _AUDIT_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")

