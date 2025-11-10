import json
from pathlib import Path

import pytest

from metamorphic_guard.relations import permute_input
from metamorphic_guard.monitoring import (
    LatencyMonitor,
    MonitorContext,
    MonitorRecord,
    SuccessRateMonitor,
    TrendMonitor,
    resolve_monitors,
)
from metamorphic_guard.util import write_report, write_failed_artifacts
from metamorphic_guard.observability import log_event


def test_permute_input_deterministic():
    sample = [3, 1, 4, 1, 5, 9]
    first_result = permute_input(sample, 3)
    second_result = permute_input(sample, 3)

    assert first_result == second_result
    # The original list should not be mutated.
    assert sample == [3, 1, 4, 1, 5, 9]


def test_write_report_custom_directory(tmp_path, monkeypatch):
    monkeypatch.delenv("METAMORPHIC_GUARD_REPORT_DIR", raising=False)
    target_dir = tmp_path / "artifacts"

    path = Path(write_report({"status": "ok"}, directory=target_dir))

    assert path.parent == target_dir
    assert path.exists()
    assert path.read_text(encoding="utf-8")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["status"] == "ok"


def test_write_report_env_directory(tmp_path, monkeypatch):
    env_dir = tmp_path / "env_reports"
    monkeypatch.setenv("METAMORPHIC_GUARD_REPORT_DIR", str(env_dir))

    path = Path(write_report({"status": "env"}))

    assert path.parent == env_dir
    assert path.exists()


def test_write_failed_artifacts(tmp_path):
    payload = {
        "task": "demo",
        "config": {},
        "baseline": {"prop_violations": []},
        "candidate": {
            "prop_violations": [{"test_case": 0, "property": "demo"}],
            "mr_violations": [],
        },
    }

    path = write_failed_artifacts(payload, directory=tmp_path)
    assert path is not None and path.exists()


def test_log_event_emits_json(monkeypatch, capsys):
    monkeypatch.setenv("METAMORPHIC_GUARD_LOG_JSON", "1")
    log_event("test_event", foo="bar")
    captured = capsys.readouterr()
    assert "test_event" in captured.out
    assert "foo" in captured.out


def test_latency_monitor_alerts():
    monitor = LatencyMonitor(percentile=0.95, alert_ratio=1.1)
    monitor.start(MonitorContext(task="demo", total_cases=4))

    for idx, latency in enumerate([10.0, 12.0, 11.5, 10.5]):
        monitor.record(
            MonitorRecord(
                case_index=idx,
                role="baseline",
                duration_ms=latency,
                success=True,
                result={},
            )
        )

    for idx, latency in enumerate([15.0, 18.0, 16.5, 17.0]):
        monitor.record(
            MonitorRecord(
                case_index=idx,
                role="candidate",
                duration_ms=latency,
                success=True,
                result={},
            )
        )

    output = monitor.finalize()
    assert output["id"] == "LatencyMonitor"
    assert output["summary"]["candidate"]["count"] == 4
    assert output["alerts"], "Expected latency regression alert"


def test_success_rate_monitor_alert():
    monitor = SuccessRateMonitor(alert_drop_ratio=0.9)
    monitor.start(MonitorContext(task="demo", total_cases=4))

    for idx in range(4):
        monitor.record(MonitorRecord(idx, "baseline", duration_ms=1.0, success=True, result={}))

    for idx in range(4):
        monitor.record(
            MonitorRecord(idx, "candidate", duration_ms=1.0, success=(idx < 2), result={})
        )

    output = monitor.finalize()
    assert output["alerts"], "Expected success rate drop alert"


def test_trend_monitor_alert():
    monitor = TrendMonitor(window=5, alert_slope_ms=0.5)
    monitor.start(MonitorContext(task="demo", total_cases=5))

    for idx in range(5):
        monitor.record(
            MonitorRecord(idx, "candidate", duration_ms=idx * 1.0, success=True, result={})
        )

    output = monitor.finalize()
    assert output["alerts"], "Expected trend alert"


def test_resolve_monitors_with_params():
    monitors = resolve_monitors(["latency:percentile=0.9,alert_ratio=1.1", "success_rate"])
    assert len(monitors) == 2
    assert monitors[0].percentile == 0.9  # type: ignore[attr-defined]

