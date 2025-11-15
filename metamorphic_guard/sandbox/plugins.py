"""
Executor plugin resolution and loading.
"""

from __future__ import annotations

import importlib
import json
import os
from typing import Any, Callable, Dict, Optional

from ..plugins import executor_plugins


def _resolve_executor_name(explicit: Optional[str]) -> str:
    """Resolve executor name from explicit value or environment variable."""
    if explicit and explicit.strip():
        return explicit.strip()
    env_value = os.environ.get("METAMORPHIC_GUARD_EXECUTOR")
    if env_value and env_value.strip():
        return env_value.strip()
    return "local"


def _load_executor_config() -> Optional[Dict[str, Any]]:
    """Load executor config from environment variable."""
    raw = os.environ.get("METAMORPHIC_GUARD_EXECUTOR_CONFIG")
    if not raw:
        return None
    try:
        config = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return config if isinstance(config, dict) else None


def _load_executor_callable(path: str) -> Callable[..., Dict[str, Any]]:
    """Load an executor callable from a module path."""
    if not path:
        raise ValueError("Executor path cannot be empty.")

    module_name: Optional[str]
    attr_name: str
    if ":" in path:
        module_name, attr_name = path.split(":", 1)
    else:
        module_name, _, attr_name = path.rpartition(".")
        if not module_name:
            raise ValueError(
                f"Executor '{path}' must be in 'module:callable' or dotted form."
            )

    module = importlib.import_module(module_name)
    target = getattr(module, attr_name)

    if isinstance(target, type):
        target = target()

    if hasattr(target, "run") and callable(target.run):
        return target.run  # type: ignore[return-value]

    if callable(target):
        return target  # type: ignore[return-value]

    raise TypeError(f"Executor '{path}' is not callable.")


def _resolve_executor(
    executor_name: Optional[str],
    executor_config: Optional[Dict[str, Any]],
) -> tuple[str, Optional[Dict[str, Any]]]:
    """
    Resolve executor name and config.

    Returns:
        Tuple of (executor_name, executor_config)
    """
    backend = _resolve_executor_name(executor_name)
    config = executor_config if executor_config is not None else _load_executor_config()
    return backend, config


def _get_executor_plugin(backend: str):
    """Get executor plugin from registry."""
    plugin_registry = executor_plugins()
    plugin_def = plugin_registry.get(backend.lower())
    return plugin_def



