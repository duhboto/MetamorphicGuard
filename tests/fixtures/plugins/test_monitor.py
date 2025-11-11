"""Test monitor plugin for contract testing."""

from __future__ import annotations

from typing import Any, Dict

from metamorphic_guard.monitoring import Monitor, MonitorRecord


class TestMonitor(Monitor):
    """A simple test monitor that tracks test case counts."""
    
    PLUGIN_METADATA = {
        "name": "Test Monitor",
        "version": "1.0.0",
        "description": "Test monitor for plugin contract verification",
    }
    
    def __init__(self, config: Dict[str, Any] | None = None) -> None:
        super().__init__()
        self._counts: Dict[str, int] = {"baseline": 0, "candidate": 0}
        self._successes: Dict[str, int] = {"baseline": 0, "candidate": 0}
    
    def record(self, record: MonitorRecord) -> None:
        """Record a test case."""
        role = record.role
        self._counts[role] = self._counts.get(role, 0) + 1
        if record.success:
            self._successes[role] = self._successes.get(role, 0) + 1
    
    def finalize(self) -> Dict[str, Any]:
        """Return monitor summary."""
        return {
            "id": self.identifier(),
            "type": "test_monitor",
            "summary": {
                "baseline": {
                    "total": self._counts.get("baseline", 0),
                    "successes": self._successes.get("baseline", 0),
                },
                "candidate": {
                    "total": self._counts.get("candidate", 0),
                    "successes": self._successes.get("candidate", 0),
                },
            },
            "alerts": [],
        }

