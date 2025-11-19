from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from ..monitoring import Monitor

RunCase = Callable[[int, Tuple[Any, ...]], Dict[str, Any]]


class Dispatcher(ABC):
    """Abstract base class for dispatching evaluation tasks."""

    def __init__(self, workers: int = 1, *, kind: str = "local") -> None:
        self.workers = max(1, workers)
        self.kind = kind

    @abstractmethod
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
        """Execute the provided run_case function against all inputs."""

