from __future__ import annotations

import importlib
from importlib.metadata import entry_points


def test_console_scripts_resolve():
    # Validate console script entry points exist and are importable callables
    scripts = {
        "metamorphic-guard": "metamorphic_guard.cli:main",
        "metaguard": "metamorphic_guard.cli:main",
        "metamorphic-guard-worker": "metamorphic_guard.worker:main",
    }
    for name, target in scripts.items():
        module_name, func_name = target.split(":")
        module = importlib.import_module(module_name)
        func = getattr(module, func_name, None)
        assert callable(func), f"Console script {name} target {target} is not callable"


def _load_all(group: str):
    eps = entry_points().select(group=group)
    loaded = []
    for ep in eps:
        # Ensure loading does not raise and object is present
        obj = ep.load()
        loaded.append((ep.name, obj))
    return loaded


def test_plugin_entry_points_load():
    # Executors
    execs = _load_all("metamorphic_guard.executors")
    assert execs, "No executors discovered"
    # Monitors
    mons = _load_all("metamorphic_guard.monitors")
    assert mons, "No monitors discovered"
    # Mutants
    muts = _load_all("metamorphic_guard.mutants")
    assert muts, "No mutants discovered"
    # Judges
    judges = _load_all("metamorphic_guard.judges")
    assert judges, "No judges discovered"


def test_pytest_plugin_registered():
    # Pytest will auto-discover via entry point 'pytest11'
    eps = entry_points().select(group="pytest11")
    names = {ep.name for ep in eps}
    assert "metamorphic" in names, "pytest plugin 'metamorphic' not registered"


