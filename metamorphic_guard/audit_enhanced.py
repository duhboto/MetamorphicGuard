"""
Enhanced audit trails with tamper detection and integrity verification.

This module provides enhanced audit logging with cryptographic integrity
checks and tamper detection.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from .types import JSONDict


@dataclass
class AuditEntry:
    """An audit log entry."""
    
    timestamp: str
    event_type: str
    event_data: Dict[str, Any]
    hash: str  # Hash of entry for integrity
    previous_hash: Optional[str] = None  # Hash of previous entry (chain)


@dataclass
class AuditTrail:
    """Complete audit trail with integrity verification."""
    
    entries: List[AuditEntry]
    chain_hash: str  # Hash of entire chain
    created_at: str
    version: str = "1.0"


def compute_entry_hash(entry: AuditEntry) -> str:
    """
    Compute hash for an audit entry.
    
    Args:
        entry: Audit entry
    
    Returns:
        SHA-256 hash as hex string
    """
    data = {
        "timestamp": entry.timestamp,
        "event_type": entry.event_type,
        "event_data": entry.event_data,
        "previous_hash": entry.previous_hash,
    }
    data_str = json.dumps(data, sort_keys=True)
    return hashlib.sha256(data_str.encode()).hexdigest()


def create_audit_entry(
    event_type: str,
    event_data: Dict[str, Any],
    previous_hash: Optional[str] = None,
) -> AuditEntry:
    """
    Create a new audit entry.
    
    Args:
        event_type: Type of event
        event_data: Event data
        previous_hash: Hash of previous entry (for chaining)
    
    Returns:
        AuditEntry with computed hash
    """
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    entry = AuditEntry(
        timestamp=timestamp,
        event_type=event_type,
        event_data=event_data,
        hash="",  # Will be computed
        previous_hash=previous_hash,
    )
    
    # Compute hash
    entry.hash = compute_entry_hash(entry)
    
    return entry


def verify_audit_trail(trail: AuditTrail) -> tuple[bool, List[str]]:
    """
    Verify integrity of an audit trail.
    
    Args:
        trail: Audit trail to verify
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    if not trail.entries:
        errors.append("Empty audit trail")
        return False, errors
    
    # Verify chain integrity
    previous_hash = None
    for i, entry in enumerate(trail.entries):
        # Verify entry hash
        computed_hash = compute_entry_hash(entry)
        if computed_hash != entry.hash:
            errors.append(f"Entry {i} hash mismatch")
        
        # Verify chain
        if entry.previous_hash != previous_hash:
            errors.append(f"Entry {i} chain broken (previous_hash mismatch)")
        
        previous_hash = entry.hash
    
    # Verify chain hash
    if trail.entries:
        last_hash = trail.entries[-1].hash
        if trail.chain_hash != last_hash:
            errors.append("Chain hash mismatch")
    
    return len(errors) == 0, errors


def create_audit_trail(entries: List[AuditEntry]) -> AuditTrail:
    """
    Create an audit trail from entries.
    
    Args:
        entries: List of audit entries
    
    Returns:
        AuditTrail with computed chain hash
    """
    # Ensure entries are chained correctly
    previous_hash = None
    for entry in entries:
        entry.previous_hash = previous_hash
        entry.hash = compute_entry_hash(entry)
        previous_hash = entry.hash
    
    chain_hash = entries[-1].hash if entries else ""
    
    return AuditTrail(
        entries=entries,
        chain_hash=chain_hash,
        created_at=datetime.utcnow().isoformat() + "Z",
    )


def add_audit_entry(
    trail: AuditTrail,
    event_type: str,
    event_data: Dict[str, Any],
) -> AuditTrail:
    """
    Add a new entry to an audit trail.
    
    Args:
        trail: Existing audit trail
        event_type: Type of event
        event_data: Event data
    
    Returns:
        Updated audit trail
    """
    previous_hash = trail.chain_hash if trail.entries else None
    
    new_entry = create_audit_entry(
        event_type=event_type,
        event_data=event_data,
        previous_hash=previous_hash,
    )
    
    new_entries = trail.entries + [new_entry]
    return create_audit_trail(new_entries)


def export_audit_trail(trail: AuditTrail, format: str = "json") -> str:
    """
    Export audit trail in various formats.
    
    Args:
        trail: Audit trail
        format: Export format ("json", "text", "csv")
    
    Returns:
        Exported trail as string
    """
    if format == "json":
        return json.dumps({
            "version": trail.version,
            "created_at": trail.created_at,
            "chain_hash": trail.chain_hash,
            "entries": [
                {
                    "timestamp": e.timestamp,
                    "event_type": e.event_type,
                    "event_data": e.event_data,
                    "hash": e.hash,
                    "previous_hash": e.previous_hash,
                }
                for e in trail.entries
            ],
        }, indent=2)
    
    if format == "text":
        lines = [
            f"Audit Trail v{trail.version}",
            f"Created: {trail.created_at}",
            f"Chain Hash: {trail.chain_hash}",
            f"Entries: {len(trail.entries)}",
            "",
        ]
        
        for i, entry in enumerate(trail.entries):
            lines.append(f"Entry {i + 1}:")
            lines.append(f"  Timestamp: {entry.timestamp}")
            lines.append(f"  Event: {entry.event_type}")
            lines.append(f"  Hash: {entry.hash}")
            lines.append(f"  Previous: {entry.previous_hash}")
            lines.append("")
        
        return "\n".join(lines)
    
    if format == "csv":
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow(["timestamp", "event_type", "hash", "previous_hash"])
        for entry in trail.entries:
            writer.writerow([
                entry.timestamp,
                entry.event_type,
                entry.hash,
                entry.previous_hash,
            ])
        
        return output.getvalue()
    
    return str(trail)

