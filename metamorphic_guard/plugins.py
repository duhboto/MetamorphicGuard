from __future__ import annotations

import warnings
from functools import lru_cache
from importlib.metadata import entry_points
from typing import Any, Callable, Dict, Iterable, Mapping, Optional

PLUGIN_GROUP_MONITORS = "metamorphic_guard.monitors"
PLUGIN_GROUP_DISPATCHERS = "metamorphic_guard.dispatchers"


def _load_entry_points(group: str) -> Mapping[str, Callable[..., Any]]:
    eps = entry_points()
    candidates: Iterable[Any]
    try:
        candidates = eps.select(group=group)
    except AttributeError:  # pragma: no cover - Python <3.10 fallback
        candidates = eps.get(group, [])

    registry: Dict[str, Callable[..., Any]] = {}
    for ep in candidates:
        try:
            registry[ep.name] = ep.load()
        except Exception as exc:  # pragma: no cover - best effort
            warnings.warn(
                f"Failed to load plugin '{ep.name}' in group '{group}': {exc}",
                RuntimeWarning,
                stacklevel=2,
            )
    return registry


@lru_cache(maxsize=None)
def monitor_plugins() -> Mapping[str, Callable[..., Any]]:
    return _load_entry_points(PLUGIN_GROUP_MONITORS)


@lru_cache(maxsize=None)
def dispatcher_plugins() -> Mapping[str, Callable[..., Any]]:
    return _load_entry_points(PLUGIN_GROUP_DISPATCHERS)

