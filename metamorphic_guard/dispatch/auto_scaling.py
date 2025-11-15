"""
Dynamic worker pool scaling based on queue depth and throughput.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional

from ..queue_adapter import QueueAdapter


class AutoScaler:
    """
    Automatically scales worker pools based on queue metrics.
    
    Scaling strategies:
    - Queue depth: Scale up when queue depth exceeds threshold
    - Throughput: Scale up when throughput is below target
    - Worker utilization: Scale down when workers are idle
    """
    
    def __init__(
        self,
        adapter: QueueAdapter,
        min_workers: int = 1,
        max_workers: int = 100,
        target_queue_depth: int = 10,
        scale_up_threshold: int = 20,
        scale_down_threshold: int = 5,
        scale_up_factor: float = 1.5,
        scale_down_factor: float = 0.8,
        cooldown_seconds: float = 30.0,
    ) -> None:
        """
        Initialize auto-scaler.
        
        Args:
            adapter: Queue adapter to monitor
            min_workers: Minimum number of workers
            max_workers: Maximum number of workers
            target_queue_depth: Target queue depth for optimal throughput
            scale_up_threshold: Queue depth threshold to trigger scale-up
            scale_down_threshold: Queue depth threshold to trigger scale-down
            scale_up_factor: Multiplier for scale-up (e.g., 1.5 = 50% increase)
            scale_down_factor: Multiplier for scale-down (e.g., 0.8 = 20% decrease)
            cooldown_seconds: Minimum time between scaling actions
        """
        self.adapter = adapter
        self.min_workers = min_workers
        self.max_workers = max_workers
        self.target_queue_depth = target_queue_depth
        self.scale_up_threshold = scale_up_threshold
        self.scale_down_threshold = scale_down_threshold
        self.scale_up_factor = scale_up_factor
        self.scale_down_factor = scale_down_factor
        self.cooldown_seconds = cooldown_seconds
        
        self._last_scale_time = 0.0
        self._current_workers = min_workers
        self._throughput_history: list[float] = []  # Tasks per second
        self._queue_depth_history: list[int] = []
    
    def should_scale_up(self, current_workers: int, queue_depth: int, throughput: float) -> bool:
        """Determine if we should scale up."""
        if current_workers >= self.max_workers:
            return False
        
        if time.monotonic() - self._last_scale_time < self.cooldown_seconds:
            return False
        
        # Scale up if queue depth is high
        if queue_depth > self.scale_up_threshold:
            return True
        
        # Scale up if throughput is low relative to queue depth
        if queue_depth > self.target_queue_depth and throughput < (current_workers * 0.5):
            return True
        
        return False
    
    def should_scale_down(self, current_workers: int, queue_depth: int, throughput: float) -> bool:
        """Determine if we should scale down."""
        if current_workers <= self.min_workers:
            return False
        
        if time.monotonic() - self._last_scale_time < self.cooldown_seconds:
            return False
        
        # Scale down if queue is nearly empty and throughput is low
        if queue_depth < self.scale_down_threshold and throughput < (current_workers * 0.3):
            return True
        
        return False
    
    def calculate_target_workers(
        self,
        current_workers: int,
        queue_depth: int,
        throughput: float,
    ) -> int:
        """
        Calculate target number of workers based on current metrics.
        
        Returns:
            Target number of workers
        """
        if self.should_scale_up(current_workers, queue_depth, throughput):
            # Scale up: increase by factor, but ensure we can process queue
            target = int(current_workers * self.scale_up_factor)
            # Also consider queue depth
            queue_based = max(1, queue_depth // self.target_queue_depth)
            target = max(target, queue_based)
            return min(target, self.max_workers)
        
        if self.should_scale_down(current_workers, queue_depth, throughput):
            # Scale down: decrease by factor
            target = int(current_workers * self.scale_down_factor)
            return max(target, self.min_workers)
        
        return current_workers
    
    def update_metrics(self, queue_depth: int, tasks_completed: int, time_elapsed: float) -> None:
        """Update internal metrics for scaling decisions."""
        if time_elapsed > 0:
            throughput = tasks_completed / time_elapsed
            self._throughput_history.append(throughput)
            # Keep only recent history (last 10 samples)
            if len(self._throughput_history) > 10:
                self._throughput_history.pop(0)
        
        self._queue_depth_history.append(queue_depth)
        if len(self._queue_depth_history) > 10:
            self._queue_depth_history.pop(0)
    
    def get_recommended_workers(self, current_workers: int) -> int:
        """
        Get recommended number of workers based on current queue state.
        
        Args:
            current_workers: Current number of workers
        
        Returns:
            Recommended number of workers
        """
        queue_depth = self.adapter.pending_count()
        
        # Calculate average throughput
        avg_throughput = (
            sum(self._throughput_history) / len(self._throughput_history)
            if self._throughput_history
            else 0.0
        )
        
        target = self.calculate_target_workers(current_workers, queue_depth, avg_throughput)
        
        if target != current_workers:
            self._last_scale_time = time.monotonic()
        
        return target


def create_auto_scaler(
    adapter: QueueAdapter,
    config: Optional[Dict[str, Any]] = None,
) -> Optional[AutoScaler]:
    """
    Create an auto-scaler from configuration.
    
    Args:
        adapter: Queue adapter to monitor
        config: Auto-scaling configuration (None to disable)
    
    Returns:
        AutoScaler instance or None if disabled
    """
    if config is None or not config.get("enabled", False):
        return None
    
    return AutoScaler(
        adapter=adapter,
        min_workers=int(config.get("min_workers", 1)),
        max_workers=int(config.get("max_workers", 100)),
        target_queue_depth=int(config.get("target_queue_depth", 10)),
        scale_up_threshold=int(config.get("scale_up_threshold", 20)),
        scale_down_threshold=int(config.get("scale_down_threshold", 5)),
        scale_up_factor=float(config.get("scale_up_factor", 1.5)),
        scale_down_factor=float(config.get("scale_down_factor", 0.8)),
        cooldown_seconds=float(config.get("cooldown_seconds", 30.0)),
    )

