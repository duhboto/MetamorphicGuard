import json
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from metamorphic_guard.relations import permute_input
from metamorphic_guard.monitoring import (
    LatencyMonitor,
    MonitorContext,
    MonitorRecord,
    SuccessRateMonitor,
    TrendMonitor,
    FairnessGapMonitor,
    ResourceUsageMonitor,
    resolve_monitors,
)
from metamorphic_guard.util import write_report, write_failed_artifacts
from metamorphic_guard.reporting import render_html_report
from metamorphic_guard.observability import configure_logging, log_event, clear_log_context
from metamorphic_guard.notifications import collect_alerts, send_webhook_alerts


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

    path = write_failed_artifacts(payload, directory=tmp_path, run_id="run-1")
    assert path is not None and path.exists()
    stored = json.loads(path.read_text())
    assert stored["run_id"] == "run-1"


def test_write_failed_artifacts_prunes(tmp_path, monkeypatch):
    payload = {
        "task": "demo",
        "config": {},
        "baseline": {"prop_violations": []},
        "candidate": {
            "prop_violations": [{"test_case": 0, "property": "demo"}],
            "mr_violations": [],
        },
    }

    first = write_failed_artifacts(payload, directory=tmp_path, limit=1, run_id="first")
    assert first and first.exists()
    second = write_failed_artifacts(payload, directory=tmp_path, limit=1, run_id="second")
    assert second and second.exists()
    remaining_files = list(tmp_path.glob("*.json"))
    assert len(remaining_files) == 1
    assert remaining_files[0] == second


def test_log_event_emits_json(capsys):
    buffer = StringIO()
    configure_logging(True, stream=buffer)
    clear_log_context()
    log_event("test_event", foo="bar")
    output = buffer.getvalue()
    assert "test_event" in output
    assert "foo" in output
    configure_logging(False)


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


def test_resource_usage_monitor_alert():
    monitor = ResourceUsageMonitor(metric="cpu_ms", alert_ratio=1.5)
    monitor.start(MonitorContext(task="demo", total_cases=4))

    for idx in range(4):
        monitor.record(MonitorRecord(idx, "baseline", duration_ms=1.0, success=True, result={"resource_usage": {"cpu_ms": 10.0}}))

    for idx in range(4):
        monitor.record(MonitorRecord(idx, "candidate", duration_ms=1.0, success=True, result={"resource_usage": {"cpu_ms": 20.0}}))

    output = monitor.finalize()
    assert output["alerts"], "Expected resource regression alert"


def test_fairness_monitor_alert():
    monitor = FairnessGapMonitor(max_gap=0.1, field="group")
    monitor.start(MonitorContext(task="demo", total_cases=4))

    # Baseline balanced
    monitor.record(MonitorRecord(0, "baseline", duration_ms=1.0, success=True, result={"group": "A"}))
    monitor.record(MonitorRecord(1, "baseline", duration_ms=1.0, success=True, result={"group": "B"}))

    # Candidate regresses group B success
    monitor.record(MonitorRecord(0, "candidate", duration_ms=1.0, success=True, result={"group": "A"}))
    monitor.record(MonitorRecord(1, "candidate", duration_ms=1.0, success=False, result={"group": "B"}))
    monitor.record(MonitorRecord(2, "candidate", duration_ms=1.0, success=False, result={"group": "B"}))

    output = monitor.finalize()
    assert output["alerts"], "Expected fairness gap alert"


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
    assert monitors[0].percentile == 0.9
    assert monitors[1].identifier() == "SuccessRateMonitor"


def test_render_html_report_embeds_charts(tmp_path):
    payload = {
        "task": "demo",
        "baseline": {
            "pass_rate": 0.6,
            "passes": 6,
            "total": 10,
            "prop_violations": [],
            "mr_violations": [],
        },
        "candidate": {
            "pass_rate": 0.75,
            "passes": 7,
            "total": 10,
            "prop_violations": [],
            "mr_violations": [],
        },
        "delta_pass_rate": 0.15,
        "delta_ci": [0.05, 0.25],
        "relative_risk": 1.2,
        "relative_risk_ci": [1.0, 1.4],
        "monitors": {
            "fair": {
                "type": "fairness_gap",
                "summary": {
                    "baseline": {"A": 0.6, "B": 0.6},
                    "candidate": {"A": 0.8, "B": 0.5},
                    "max_gap": 0.3,
                },
                "alerts": [],
            },
            "resources": {
                "type": "resource_usage",
                "metric": "cpu_ms",
                "summary": {
                    "baseline": {"mean": 10.0},
                    "candidate": {"mean": 14.0},
                },
                "alerts": [],
            },
        },
    }

    destination = tmp_path / "report.html"
    render_html_report(payload, destination)
    content = destination.read_text(encoding="utf-8")

    assert "pass-rate-chart" in content
    assert "fairness-chart" in content
    assert "resource-chart" in content
    assert "chart.umd.min.js" in content


def test_collect_alerts():
    alerts = collect_alerts(
        {
            "LatencyMonitor": {"alerts": [{"type": "latency_regression"}]},
            "Fairness": {"alerts": []},
        }
    )
    assert alerts == [{"monitor": "LatencyMonitor", "type": "latency_regression"}]


def test_send_webhook_alerts(monkeypatch):
    captured: list[dict[str, Any]] = []

    def fake_opener(request):
        captured.append(json.loads(request.data.decode("utf-8")))
        class _Response:
            def read(self):
                return b""
        return _Response()

    alerts = [{"monitor": "LatencyMonitor", "type": "latency_regression"}]
    send_webhook_alerts(alerts, ["http://example.com/webhook"], metadata={"task": "demo"}, opener=fake_opener)
    assert captured and captured[0]["alerts"][0]["monitor"] == "LatencyMonitor"

