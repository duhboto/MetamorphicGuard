"""
Task specification framework with property and metamorphic relation definitions.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Hashable, List, Optional, Tuple
import functools


@dataclass
class Property:
    """A property to check on function outputs."""
    check: Callable[..., bool]
    description: str
    mode: str = "hard"  # "hard" or "soft"


@dataclass
class MetamorphicRelation:
    """A metamorphic relation for testing."""
    name: str
    transform: Callable[..., Tuple[Any, ...]]
    expect: str = "equal"  # For v1, only "equal" is supported
    accepts_rng: bool = False
    category: Optional[str] = None
    description: Optional[str] = None


@dataclass
class Metric:
    """A continuous metric to track during evaluation."""
    name: str
    extract: Callable[[Any, Tuple[Any, ...]], float]
    kind: str = "mean"
    higher_is_better: bool = True
    ci_method: Optional[str] = "bootstrap"
    bootstrap_samples: int = 500
    alpha: float = 0.05
    seed: Optional[int] = None
    memoize: bool = False
    memoize_key: Optional[str] = None
    sample_rate: float = 1.0


@dataclass
class Spec:
    """Complete specification for a task."""
    gen_inputs: Callable[[int, int], List[Tuple[Any, ...]]]
    properties: List[Property]
    relations: List[MetamorphicRelation]
    equivalence: Callable[[Any, Any], bool]
    fmt_in: Callable[[Tuple[Any, ...]], str] = lambda args: str(args)
    fmt_out: Callable[[Any], str] = lambda result: str(result)
    cluster_key: Optional[Callable[[Tuple[Any, ...]], Hashable]] = None
    metrics: List[Metric] = field(default_factory=list)


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
    # First check built-in registry
    if name in _TASK_REGISTRY:
        spec_func = _TASK_REGISTRY[name]
        return spec_func()
    
    # Then check plugin registry
    try:
        from .plugins import task_plugins
        
        plugin_registry = task_plugins()
        plugin_def = plugin_registry.get(name.lower())
        if plugin_def is not None:
            # Plugin factory should return a Spec or a callable that returns a Spec
            factory = plugin_def.factory
            if callable(factory):
                result = factory()
                if isinstance(result, Spec):
                    return result
                # If it's a callable that returns Spec, call it
                if callable(result):
                    return result()
            raise TypeError(f"Task plugin '{name}' must return a Spec")
    except ImportError:
        pass
    
    # Not found in either registry
    available = list(_TASK_REGISTRY.keys())
    try:
        from .plugins import task_plugins
        available.extend(list(task_plugins().keys()))
    except ImportError:
        pass
    
    raise ValueError(f"Task '{name}' not found in registry. Available: {available}")


def list_tasks() -> List[str]:
    """List all registered task names (built-in + plugins)."""
    tasks = list(_TASK_REGISTRY.keys())
    try:
        from .plugins import task_plugins
        tasks.extend(list(task_plugins().keys()))
    except ImportError:
        pass
    return sorted(set(tasks))
