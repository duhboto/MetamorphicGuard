"""
Task specification framework with property and metamorphic relation definitions.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Tuple
import functools


@dataclass
class Property:
    """A property to check on function outputs."""
    check: Callable[[Any], bool]
    description: str
    mode: str = "hard"  # "hard" or "soft"


@dataclass
class MetamorphicRelation:
    """A metamorphic relation for testing."""
    name: str
    transform: Callable[..., Tuple[Any, ...]]
    expect: str = "equal"  # For v1, only "equal" is supported


@dataclass
class Spec:
    """Complete specification for a task."""
    gen_inputs: Callable[[int, int], List[Tuple[Any, ...]]]
    properties: List[Property]
    relations: List[MetamorphicRelation]
    equivalence: Callable[[Any, Any], bool]
    fmt_in: Callable[[Tuple[Any, ...]], str] = lambda args: str(args)
    fmt_out: Callable[[Any], str] = lambda result: str(result)


# Global task registry
_TASK_REGISTRY: Dict[str, Spec] = {}


def task(name: str):
    """Decorator to register a task specification."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        # Store the spec in registry
        _TASK_REGISTRY[name] = wrapper
        return wrapper
    return decorator


def get_task(name: str) -> Spec:
    """Get a registered task specification."""
    if name not in _TASK_REGISTRY:
        raise ValueError(f"Task '{name}' not found in registry. Available: {list(_TASK_REGISTRY.keys())}")
    
    spec_func = _TASK_REGISTRY[name]
    return spec_func()


def list_tasks() -> List[str]:
    """List all registered task names."""
    return list(_TASK_REGISTRY.keys())
