from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from functools import lru_cache
from importlib import import_module
from importlib.metadata import EntryPoint, entry_points
from typing import Any, Callable, Dict, Iterable, Mapping, Optional

PLUGIN_GROUP_MONITORS = "metamorphic_guard.monitors"
PLUGIN_GROUP_DISPATCHERS = "metamorphic_guard.dispatchers"
PLUGIN_GROUP_EXECUTORS = "metamorphic_guard.executors"
PLUGIN_GROUP_MUTANTS = "metamorphic_guard.mutants"
PLUGIN_GROUP_JUDGES = "metamorphic_guard.judges"
PLUGIN_GROUP_TASKS = "metamorphic_guard.tasks"
PLUGIN_GROUP_RELATIONS = "metamorphic_guard.relations"


@dataclass(frozen=True)
class PluginMetadata:
    name: str
    version: Optional[str] = None
    description: Optional[str] = None
    guard_min: Optional[str] = None
    guard_max: Optional[str] = None
    author: Optional[str] = None
    url: Optional[str] = None
    sandbox: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PluginDefinition:
    name: str
    group: str
    factory: Callable[..., Any]
    module: str
    attr: Optional[str]
    metadata: PluginMetadata


def _coerce_optional(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value)


def _extract_metadata(ep: EntryPoint, factory: Callable[..., Any]) -> PluginMetadata:
    module_meta: Optional[Any] = None
    callable_meta: Optional[Any] = getattr(factory, "PLUGIN_METADATA", None)

    try:
        module = import_module(ep.module)
        module_meta = getattr(module, "PLUGIN_METADATA", None)
    except Exception:  # pragma: no cover - metadata best effort
        module_meta = None

    for raw in (callable_meta, module_meta):
        if isinstance(raw, Mapping):
            data = dict(raw)
            name = _coerce_optional(data.pop("name", ep.name)) or ep.name
            version = _coerce_optional(data.pop("version", None))
            description = _coerce_optional(data.pop("description", None))
            guard_min = _coerce_optional(data.pop("guard_min", None))
            guard_max = _coerce_optional(data.pop("guard_max", None))
            author = _coerce_optional(data.pop("author", None))
            url = _coerce_optional(data.pop("url", None))
            sandbox_flag = bool(data.pop("sandbox", False))
            return PluginMetadata(
                name=name,
                version=version,
                description=description,
                guard_min=guard_min,
                guard_max=guard_max,
                author=author,
                url=url,
                sandbox=sandbox_flag,
                extra={k: v for k, v in data.items()},
            )

    return PluginMetadata(name=ep.name)


def _load_entry_points(group: str) -> Mapping[str, PluginDefinition]:
    eps = entry_points()
    candidates: Iterable[Any]
    try:
        candidates = eps.select(group=group)
    except AttributeError:  # pragma: no cover - Python <3.10 fallback
        candidates = eps.get(group, [])

    registry: Dict[str, PluginDefinition] = {}
    for ep in candidates:
        try:
            factory = ep.load()
        except Exception as exc:  # pragma: no cover - best effort
            warnings.warn(
                f"Failed to load plugin '{ep.name}' in group '{group}': {exc}",
                RuntimeWarning,
                stacklevel=2,
            )
            continue

        metadata = _extract_metadata(ep, factory)
        registry[ep.name.lower()] = PluginDefinition(
            name=ep.name,
            group=group,
            factory=factory,
            module=ep.module,
            attr=getattr(ep, "attr", None),
            metadata=metadata,
        )
    return registry


@lru_cache(maxsize=None)
def monitor_plugins() -> Mapping[str, PluginDefinition]:
    return _load_entry_points(PLUGIN_GROUP_MONITORS)


@lru_cache(maxsize=None)
def dispatcher_plugins() -> Mapping[str, PluginDefinition]:
    return _load_entry_points(PLUGIN_GROUP_DISPATCHERS)


@lru_cache(maxsize=None)
def executor_plugins() -> Mapping[str, PluginDefinition]:
    return _load_entry_points(PLUGIN_GROUP_EXECUTORS)


@lru_cache(maxsize=None)
def mutant_plugins() -> Mapping[str, PluginDefinition]:
    return _load_entry_points(PLUGIN_GROUP_MUTANTS)


@lru_cache(maxsize=None)
def judge_plugins() -> Mapping[str, PluginDefinition]:
    return _load_entry_points(PLUGIN_GROUP_JUDGES)


@lru_cache(maxsize=None)
def task_plugins() -> Mapping[str, PluginDefinition]:
    """Load task plugins from entry points."""
    return _load_entry_points(PLUGIN_GROUP_TASKS)


@lru_cache(maxsize=None)
def relation_plugins() -> Mapping[str, PluginDefinition]:
    """Load relation plugins from entry points."""
    return _load_entry_points(PLUGIN_GROUP_RELATIONS)


def plugin_registry(kind: Optional[str] = None) -> Dict[str, PluginDefinition]:
    """Return a mapping of plugin name -> definition for the requested kind."""

    normalized = (kind or "all").lower()
    registry: Dict[str, PluginDefinition] = {}
    if normalized in {"monitor", "all"}:
        registry.update(monitor_plugins())
    if normalized in {"dispatcher", "all"}:
        registry.update(dispatcher_plugins())
    if normalized in {"executor", "all"}:
        registry.update(executor_plugins())
    if normalized in {"mutant", "all"}:
        registry.update(mutant_plugins())
    if normalized in {"judge", "all"}:
        registry.update(judge_plugins())
    if normalized in {"task", "all"}:
        registry.update(task_plugins())
    if normalized in {"relation", "all"}:
        registry.update(relation_plugins())
    return registry

