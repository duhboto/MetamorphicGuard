from types import SimpleNamespace

import pytest

from metamorphic_guard import monitoring
from metamorphic_guard.plugins import dispatcher_plugins, monitor_plugins


class FakeEntryPoint:
    def __init__(self, name, obj, group):
        self.name = name
        self._obj = obj
        self.group = group

    def load(self):
        return self._obj


def fake_entry_points(monitors=None, dispatchers=None):
    monitors = monitors or []
    dispatchers = dispatchers or []

    class _EP:
        def __init__(self, monitors, dispatchers):
            self._monitors = monitors
            self._dispatchers = dispatchers

        def select(self, *, group):
            if group == "metamorphic_guard.monitors":
                return self._monitors
            if group == "metamorphic_guard.dispatchers":
                return self._dispatchers
            return []

    return _EP(monitors, dispatchers)


def test_monitor_plugin_loading(monkeypatch):
    class DemoMonitor(monitoring.Monitor):
        def record(self, record):
            pass

        def finalize(self):
            return {"id": self.identifier(), "type": "demo", "summary": {}, "alerts": []}

    fake_entry = FakeEntryPoint("demo_monitor", DemoMonitor, "metamorphic_guard.monitors")
    monkeypatch.setattr(
        "metamorphic_guard.plugins.entry_points",
        lambda: fake_entry_points(monitors=[fake_entry]),
    )
    monitor_plugins.cache_clear()

    resolved = monitoring.resolve_monitors(["demo_monitor"])
    assert isinstance(resolved[0], DemoMonitor)


def test_dispatcher_plugin_loading(monkeypatch):
    from metamorphic_guard.dispatch import Dispatcher

    class DemoDispatcher(Dispatcher):
        def __init__(self, workers: int = 1, config=None):
            super().__init__(workers, kind="demo")
            self.config = config or {}

        def execute(self, *, test_inputs, run_case, role, monitors=None, call_spec=None):
            return [run_case(i, args) for i, args in enumerate(test_inputs)]

    fake_entry = FakeEntryPoint("demo", DemoDispatcher, "metamorphic_guard.dispatchers")
    monkeypatch.setattr(
        "metamorphic_guard.plugins.entry_points",
        lambda: fake_entry_points(dispatchers=[fake_entry]),
    )
    dispatcher_plugins.cache_clear()

    from metamorphic_guard.dispatch import ensure_dispatcher

    dispatcher = ensure_dispatcher("demo", workers=1, queue_config={})
    assert isinstance(dispatcher, DemoDispatcher)

