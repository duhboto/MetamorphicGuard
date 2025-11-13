import pytest
from click.testing import CliRunner

from metamorphic_guard import monitoring
from metamorphic_guard.cli import main
from metamorphic_guard.plugins import dispatcher_plugins, monitor_plugins


class FakeEntryPoint:
    def __init__(self, name, obj, group, module=None, attr=None):
        self.name = name
        self._obj = obj
        self.group = group
        self.module = module or __name__
        self.attr = attr

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


class SandboxMonitorPlugin(monitoring.Monitor):
    PLUGIN_METADATA = {
        "name": "Sandbox Monitor",
        "sandbox": True,
    }

    def __init__(self) -> None:
        super().__init__()
        self._records: list[int] = []

    def record(self, record):
        self._records.append(record.case_index)

    def finalize(self):
        return {
            "id": self.identifier(),
            "type": "sandbox",
            "summary": {"count": len(self._records)},
            "alerts": [],
        }


class DemoMonitorCLIPlugin(monitoring.Monitor):
    PLUGIN_METADATA = {"name": "Demo CLI Monitor", "version": "0.1"}

    def record(self, record):
        pass

    def finalize(self):
        return {"id": self.identifier(), "type": "cli", "summary": {}, "alerts": []}


def test_monitor_plugin_loading(monkeypatch):
    class DemoMonitor(monitoring.Monitor):
        PLUGIN_METADATA = {
            "name": "Demo Monitor",
            "version": "1.0.0",
            "author": "QA",
        }

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

    registry = monitor_plugins()
    definition = registry["demo_monitor"]
    assert definition.metadata.name == "Demo Monitor"

    resolved = monitoring.resolve_monitors(["demo_monitor"], sandbox_plugins=False)
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


def test_monitor_plugin_sandbox(monkeypatch):
    fake_entry = FakeEntryPoint("sandbox", SandboxMonitorPlugin, "metamorphic_guard.monitors")
    monkeypatch.setattr(
        "metamorphic_guard.plugins.entry_points",
        lambda: fake_entry_points(monitors=[fake_entry]),
    )
    monitor_plugins.cache_clear()

    monitors = monitoring.resolve_monitors(["sandbox"], sandbox_plugins=False)
    monitor = monitors[0]
    assert isinstance(monitor, monitoring.SandboxedMonitorProxy)

    context = monitoring.MonitorContext(task="demo", total_cases=2)
    monitor.start(context)
    monitor.record(monitoring.MonitorRecord(0, "baseline", duration_ms=1.0, success=True, result={}))
    result = monitor.finalize()
    assert result["summary"]["count"] == 1


def test_plugin_cli_list(monkeypatch):
    fake_entry = FakeEntryPoint("cli_monitor", DemoMonitorCLIPlugin, "metamorphic_guard.monitors")
    monkeypatch.setattr(
        "metamorphic_guard.plugins.entry_points",
        lambda: fake_entry_points(monitors=[fake_entry]),
    )
    monitor_plugins.cache_clear()

    runner = CliRunner()
    result = runner.invoke(main, ["plugin", "list", "--json"])
    assert result.exit_code == 0
    assert "cli_monitor" in result.output

    result = runner.invoke(main, ["plugin", "info", "cli_monitor", "--kind", "monitor", "--json"])
    assert result.exit_code == 0
    assert "Demo CLI Monitor" in result.output

    monitor_plugins.cache_clear()
    dispatcher_plugins.cache_clear()

