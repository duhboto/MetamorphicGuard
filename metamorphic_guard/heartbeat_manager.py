"""
Enhanced heartbeat management with circuit-breaker and structured events.

Provides timeout detection, circuit-breaker behavior, and diagnostic events
for worker liveness tracking.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, Set, Any

from .observability import log_event


@dataclass
class HeartbeatConfig:
    """Configuration for heartbeat management."""
    timeout_seconds: float = 45.0
    circuit_breaker_threshold: int = 3  # Mark worker lost after N missed beats
    check_interval: float = 5.0  # How often to check heartbeats
    event_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None


@dataclass
class WorkerState:
    """State tracking for a worker."""
    last_heartbeat: float
    missed_beats: int = 0
    is_lost: bool = False
    registered_at: float = field(default_factory=time.monotonic)
    last_task_assignment: Optional[str] = None


class HeartbeatManager:
    """
    Manages worker heartbeats with timeout detection and circuit-breaker behavior.
    
    Features:
    - Detects stale workers based on heartbeat age
    - Circuit-breaker: marks workers as lost after K missed beats
    - Emits structured events for diagnostics
    - Tracks worker registration and task assignments
    """
    
    def __init__(self, config: HeartbeatConfig) -> None:
        self.config = config
        self._workers: Dict[str, WorkerState] = {}
        self._lost_workers: Set[str] = set()
        self._last_check: float = time.monotonic()
    
    def register_worker(self, worker_id: str) -> None:
        """Register or refresh a worker heartbeat."""
        now = time.monotonic()
        
        if worker_id in self._lost_workers:
            # Worker recovered - remove from lost set
            self._lost_workers.discard(worker_id)
            self._emit_event("worker_recovered", {
                "worker_id": worker_id,
                "recovered_at": now,
            })
        
        if worker_id in self._workers:
            # Refresh existing worker
            state = self._workers[worker_id]
            state.last_heartbeat = now
            state.missed_beats = 0
            state.is_lost = False
        else:
            # New worker registration
            self._workers[worker_id] = WorkerState(
                last_heartbeat=now,
                registered_at=now,
            )
            self._emit_event("worker_registered", {
                "worker_id": worker_id,
                "registered_at": now,
            })
    
    def record_task_assignment(self, worker_id: str, task_id: str) -> None:
        """Record that a worker was assigned a task."""
        if worker_id in self._workers:
            self._workers[worker_id].last_task_assignment = task_id
    
    def check_stale_workers(self, now: Optional[float] = None) -> Set[str]:
        """
        Check for stale workers and update circuit-breaker state.
        
        Returns:
            Set of worker IDs that are considered lost
        """
        if now is None:
            now = time.monotonic()
        
        # Throttle checks
        if now - self._last_check < self.config.check_interval:
            return self._lost_workers
        
        self._last_check = now
        newly_lost: Set[str] = set()
        
        for worker_id, state in list(self._workers.items()):
            age = now - state.last_heartbeat
            
            if age > self.config.timeout_seconds:
                # Worker is stale
                state.missed_beats += 1
                
                if state.missed_beats >= self.config.circuit_breaker_threshold:
                    # Circuit-breaker: mark as lost
                    if not state.is_lost:
                        state.is_lost = True
                        self._lost_workers.add(worker_id)
                        newly_lost.add(worker_id)
                        
                        self._emit_event("worker_lost", {
                            "worker_id": worker_id,
                            "heartbeat_age": age,
                            "missed_beats": state.missed_beats,
                            "last_task": state.last_task_assignment,
                            "registered_at": state.registered_at,
                            "lost_at": now,
                        })
                else:
                    # Warning: approaching threshold
                    self._emit_event("worker_stale", {
                        "worker_id": worker_id,
                        "heartbeat_age": age,
                        "missed_beats": state.missed_beats,
                        "threshold": self.config.circuit_breaker_threshold,
                    })
            else:
                # Worker is healthy - reset missed beats
                if state.missed_beats > 0:
                    state.missed_beats = 0
        
        return self._lost_workers
    
    def is_worker_lost(self, worker_id: str) -> bool:
        """Check if a worker is marked as lost."""
        return worker_id in self._lost_workers
    
    def get_worker_age(self, worker_id: str, now: Optional[float] = None) -> Optional[float]:
        """Get heartbeat age for a worker."""
        if now is None:
            now = time.monotonic()
        
        state = self._workers.get(worker_id)
        if state is None:
            return None
        
        return now - state.last_heartbeat
    
    def get_lost_workers(self) -> Set[str]:
        """Get set of lost worker IDs."""
        return self._lost_workers.copy()
    
    def get_worker_count(self) -> int:
        """Get total number of registered workers."""
        return len(self._workers)
    
    def get_healthy_worker_count(self) -> int:
        """Get number of healthy (non-lost) workers."""
        return len(self._workers) - len(self._lost_workers)
    
    def unregister_worker(self, worker_id: str) -> None:
        """Unregister a worker (e.g., on shutdown)."""
        if worker_id in self._workers:
            state = self._workers[worker_id]
            del self._workers[worker_id]
            self._lost_workers.discard(worker_id)
            
            self._emit_event("worker_unregistered", {
                "worker_id": worker_id,
                "registered_at": state.registered_at,
                "unregistered_at": time.monotonic(),
            })
    
    def reset(self) -> None:
        """Reset all state (for testing)."""
        self._workers.clear()
        self._lost_workers.clear()
        self._last_check = time.monotonic()
    
    def _emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Emit a structured event."""
        event_data = {
            "event": event_type,
            "timestamp": time.monotonic(),
            **data,
        }
        
        # Use callback if provided, otherwise use log_event
        if self.config.event_callback:
            self.config.event_callback(event_type, event_data)
        else:
            log_event(f"heartbeat_{event_type}", **event_data)

