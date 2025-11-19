from __future__ import annotations

import logging
import random
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

from ..monitoring import Monitor
from ..redaction import SecretRedactor, get_redactor
from .base import Dispatcher, RunCase

logger = logging.getLogger(__name__)


class TrafficSource(ABC):
    """Abstract base class for fetching production traffic."""

    @abstractmethod
    def fetch_batch(self, size: int) -> List[Tuple[Any, ...]]:
        """Fetch a batch of inputs from the traffic source."""
        pass

    @abstractmethod
    def ack(self, message_ids: Sequence[str]) -> None:
        """Acknowledge processing of messages (if applicable)."""
        pass


class InMemoryTrafficSource(TrafficSource):
    """Simple in-memory traffic source for testing or simulation."""

    def __init__(self, items: List[Tuple[Any, ...]]) -> None:
        self.items = items
        self._cursor = 0

    def fetch_batch(self, size: int) -> List[Tuple[Any, ...]]:
        if self._cursor >= len(self.items):
            return []
        end = min(self._cursor + size, len(self.items))
        batch = self.items[self._cursor : end]
        self._cursor = end
        return batch

    def ack(self, message_ids: Sequence[str]) -> None:
        pass


class ShadowDispatcher(Dispatcher):
    """
    A dispatcher designed for "Shadow Mode" operations.
    
    Features:
    - Wraps another dispatcher (delegate) for actual execution.
    - Supports traffic sampling (execute only a % of requests).
    - Redacts sensitive data in results/logs using SecretRedactor.
    - "Safe Mode": Swallows exceptions to prevent impacting production if running inline.
    - Can pull from a TrafficSource if no inputs are provided explicitly (optional).
    """

    def __init__(
        self,
        delegate: Dispatcher,
        *,
        traffic_source: Optional[TrafficSource] = None,
        sample_rate: float = 1.0,
        redactor: Optional[SecretRedactor] = None,
        safe_mode: bool = True,
    ) -> None:
        super().__init__(workers=delegate.workers, kind="shadow")
        self.delegate = delegate
        self.traffic_source = traffic_source
        self.sample_rate = max(0.0, min(1.0, sample_rate))
        self.redactor = redactor or get_redactor()
        self.safe_mode = safe_mode

    def execute(
        self,
        *,
        test_inputs: Sequence[Tuple[Any, ...]],
        run_case: RunCase,
        role: str,
        monitors: Sequence[Monitor] | None = None,
        call_spec: Optional[Dict[str, Any]] = None,
        seed: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        
        # 1. Resolve Inputs
        inputs_to_use = list(test_inputs)
        if not inputs_to_use and self.traffic_source:
            # If no explicit inputs, try to fetch from source
            # We default to a batch size equal to workers * 2 or some reasonable default
            batch_size = self.workers * 4
            inputs_to_use = self.traffic_source.fetch_batch(batch_size)
        
        if not inputs_to_use:
            return []

        # 2. Sampling
        if self.sample_rate < 1.0:
            # Deterministic sampling if seed provided? 
            # For shadow mode, we usually want random sampling or hash-based.
            # Here we simply filter the list.
            rng = random.Random(seed) if seed is not None else random.Random()
            inputs_to_use = [
                inp for inp in inputs_to_use 
                if rng.random() < self.sample_rate
            ]
            if not inputs_to_use:
                return []

        # 3. Safe Execution Wrapper
        def safe_run_case(index: int, args: Tuple[Any, ...]) -> Dict[str, Any]:
            try:
                result = run_case(index, args)
                # Redact result
                if self.redactor:
                    result = self.redactor.redact(result)
                return result
            except Exception as e:
                logger.error(f"Shadow execution failed for case {index}: {e}", exc_info=True)
                if self.safe_mode:
                    return {
                        "success": False,
                        "error": f"Shadow execution error: {str(e)}",
                        "duration_ms": 0.0,
                        "shadow_suppressed": True
                    }
                raise

        # 4. Delegate Execution
        results = self.delegate.execute(
            test_inputs=inputs_to_use,
            run_case=safe_run_case,
            role=role,
            monitors=monitors,
            call_spec=call_spec,
            seed=seed,
        )
        
        return results

