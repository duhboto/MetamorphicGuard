"""
Enhanced enterprise audit logging with user tracking and compliance features.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Dict, List, Optional

from ..types import JSONDict


class AuditEventType(Enum):
    """Types of audit events."""

    # Authentication events
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"

    # Evaluation events
    EVALUATION_STARTED = "evaluation_started"
    EVALUATION_COMPLETED = "evaluation_completed"
    EVALUATION_FAILED = "evaluation_failed"

    # Configuration events
    POLICY_CREATED = "policy_created"
    POLICY_UPDATED = "policy_updated"
    POLICY_DELETED = "policy_deleted"

    # Data events
    REPORT_VIEWED = "report_viewed"
    REPORT_EXPORTED = "report_exported"
    DATA_DELETED = "data_deleted"

    # Administrative events
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REMOVED = "role_removed"


@dataclass
class AuditEvent:
    """Audit event record."""

    event_type: AuditEventType
    user_id: str
    timestamp: float
    resource: Optional[str] = None
    action: Optional[str] = None
    result: Optional[str] = None
    metadata: Optional[JSONDict] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    def to_dict(self) -> JSONDict:
        """Convert audit event to dictionary."""
        result = asdict(self)
        result["event_type"] = self.event_type.value
        return result


class EnterpriseAuditLogger:
    """Enhanced audit logger for enterprise deployments."""

    def __init__(
        self,
        log_file: Optional[str] = None,
        enable_console: bool = True,
        retention_days: int = 90,
    ) -> None:
        """
        Initialize enterprise audit logger.

        Args:
            log_file: Path to audit log file (optional)
            enable_console: Whether to log to console
            retention_days: Number of days to retain audit logs
        """
        self.log_file = log_file
        self.enable_console = enable_console
        self.retention_days = retention_days
        self.events: List[AuditEvent] = []

    def log(
        self,
        event_type: AuditEventType,
        user_id: str,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        result: Optional[str] = None,
        metadata: Optional[JSONDict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """
        Log an audit event.

        Args:
            event_type: Type of event
            user_id: User who performed the action
            resource: Resource affected (e.g., evaluation ID, report ID)
            action: Action performed
            result: Result of the action (e.g., "success", "failure")
            metadata: Additional metadata
            ip_address: IP address of the user
            user_agent: User agent string
        """
        event = AuditEvent(
            event_type=event_type,
            user_id=user_id,
            timestamp=time.time(),
            resource=resource,
            action=action,
            result=result,
            metadata=metadata,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        self.events.append(event)

        # Log to console if enabled
        if self.enable_console:
            print(f"[AUDIT] {event.event_type.value} | User: {user_id} | Resource: {resource} | Result: {result}")

        # Log to file if specified
        if self.log_file:
            try:
                with open(self.log_file, "a") as f:
                    f.write(json.dumps(event.to_dict()) + "\n")
            except Exception as e:
                print(f"Warning: Failed to write audit log: {e}")

    def get_events(
        self,
        user_id: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> List[AuditEvent]:
        """
        Retrieve audit events matching criteria.

        Args:
            user_id: Filter by user ID
            event_type: Filter by event type
            start_time: Filter events after this timestamp
            end_time: Filter events before this timestamp

        Returns:
            List of matching audit events
        """
        filtered = self.events

        if user_id:
            filtered = [e for e in filtered if e.user_id == user_id]

        if event_type:
            filtered = [e for e in filtered if e.event_type == event_type]

        if start_time:
            filtered = [e for e in filtered if e.timestamp >= start_time]

        if end_time:
            filtered = [e for e in filtered if e.timestamp <= end_time]

        return filtered

    def export_audit_log(
        self,
        output_file: str,
        user_id: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> None:
        """
        Export audit log to a file.

        Args:
            output_file: Path to output file
            user_id: Filter by user ID
            event_type: Filter by event type
            start_time: Filter events after this timestamp
            end_time: Filter events before this timestamp
        """
        events = self.get_events(user_id, event_type, start_time, end_time)

        with open(output_file, "w") as f:
            for event in events:
                f.write(json.dumps(event.to_dict()) + "\n")

