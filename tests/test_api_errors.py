from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any, Dict

import pytest

from metamorphic_guard.api import (
    Implementation,
    TaskSpec,
    EvaluationConfig,
    run,
    run_with_config,
    resolve_monitor_specs,
)
from metamorphic_guard.monitoring import LatencyMonitor
from tests.callable_fixtures import baseline_callable


@pytest.fixture
def task_spec() -> TaskSpec:
    from metamorphic_guard.api import TaskSpec, Property, Metric

    def gen_inputs(n: int, seed: int):
        return [(i,) for i in range(n)]

    return TaskSpec(
        name="api_test_task",
        gen_inputs=gen_inputs,
        properties=[
            Property(
                check=lambda output, x: isinstance(output, dict) and "value" in output,
                description="Returns dict with value key",
            ),
        ],
        relations=[],
        equivalence=lambda a, b: a == b,
        metrics=[
            Metric(
                name="value_mean",
                extract=lambda output, _: float(output["value"]),
                kind="mean",
            )
        ],
    )


def test_from_specifier_invalid_string():
    with pytest.raises(ValueError):
        Implementation.from_specifier("")


def test_from_specifier_invalid_dotted():
    with pytest.raises(ValueError):
        Implementation.from_specifier("module_without_callable:")


def test_from_specifier_windows_drive_detection(monkeypatch, tmp_path):
    impl = tmp_path / "impl.py"
    impl.write_text("def solve(x):\n    return {'value': float(x)}\n", encoding="utf-8")
    with monkeypatch.context() as m:
        m.setattr("pathlib.Path.drive", property(lambda self: "C:" if self == Path(impl) else ""))
        resolved = Implementation.from_specifier(str(impl))
    with resolved.materialize() as path:
        assert Path(path).exists()


def test_run_with_config_invalid_task(tmp_path, task_spec):
    config_text = textwrap.dedent(
        """
        [metamorphic_guard]
        task = "different_task"
        baseline = "tests.callable_fixtures:baseline_callable"
        candidate = "tests.callable_fixtures:baseline_callable"
        """
    )
    config_path = tmp_path / "guard.toml"
    config_path.write_text(config_text, encoding="utf-8")

    with pytest.raises(ValueError):
        run_with_config(config_path, task=task_spec)


def test_run_with_config_toml_error(tmp_path, task_spec):
    config_path = tmp_path / "guard.toml"
    config_path.write_text("not toml", encoding="utf-8")

    with pytest.raises(Exception):
        run_with_config(config_path, task=task_spec)


def test_run_with_config_evaluator_config(task_spec):
    from metamorphic_guard.api import EvaluatorConfig

    cfg = EvaluatorConfig(
        task="api_test_task",
        baseline="tests.callable_fixtures:baseline_callable",
        candidate="tests.callable_fixtures:baseline_callable",
        n=1,
        seed=42,
        min_delta=0.0,
    )
    result = run_with_config(cfg, task=task_spec)
    assert result.adopt is True


def test_run_with_config_mapping(task_spec):
    data = {
        "metamorphic_guard": {
            "task": "api_test_task",
            "baseline": "tests.callable_fixtures:baseline_callable",
            "candidate": "tests.callable_fixtures:baseline_callable",
            "n": 1,
            "seed": 99,
            "min_delta": 0.0,
        }
    }
    result = run_with_config(data, task=task_spec)
    assert result.adopt is True


def test_run_with_config_policy_preset(tmp_path, task_spec):
    config_text = textwrap.dedent(
        """
        [metamorphic_guard]
        task = "api_test_task"
        baseline = "tests.callable_fixtures:baseline_callable"
        candidate = "tests.callable_fixtures:baseline_callable"
        policy = "superiority:margin=0.05"
        n = 5
        seed = 123
        """
    )
    config_path = tmp_path / "guard.toml"
    config_path.write_text(config_text, encoding="utf-8")

    result = run_with_config(config_path, task=task_spec)
    assert result.adopt is False


def test_run_with_config_policy_invalid(tmp_path, task_spec):
    config_text = textwrap.dedent(
        """
        [metamorphic_guard]
        task = "api_test_task"
        baseline = "tests.callable_fixtures:baseline_callable"
        candidate = "tests.callable_fixtures:baseline_callable"
        policy = "unknownpreset"
        """
    )
    config_path = tmp_path / "guard.toml"
    config_path.write_text(config_text, encoding="utf-8")

    with pytest.raises(ValueError):
        run_with_config(config_path, task=task_spec)


def test_run_with_config_sends_alerts(monkeypatch, task_spec):
    mapping = {
        "metamorphic_guard": {
            "task": "api_test_task",
            "baseline": "tests.callable_fixtures:baseline_callable",
            "candidate": "tests.callable_fixtures:baseline_callable",
            "n": 1,
            "seed": 7,
            "min_delta": 0.0,
        }
    }

    captured: Dict[str, Any] = {}

    def fake_collect(_):
        return [{"monitor": "latency", "severity": "high"}]

    def fake_send(alerts, webhooks, metadata=None, opener=None):
        captured["alerts"] = list(alerts)
        captured["webhooks"] = list(webhooks)
        captured["metadata"] = dict(metadata or {})

    monkeypatch.setattr("metamorphic_guard.api.collect_alerts", fake_collect)
    monkeypatch.setattr("metamorphic_guard.api.send_webhook_alerts", fake_send)

    result = run_with_config(
        mapping,
        task=task_spec,
        alert_webhooks=["https://example.com/hooks/alert"],
        alert_metadata={"pipeline": "ci"},
    )

    assert result.adopt is True
    assert captured["webhooks"] == ["https://example.com/hooks/alert"]
    assert captured["alerts"][0]["monitor"] == "latency"
    assert captured["metadata"]["task"] == "api_test_task"
    assert captured["metadata"]["pipeline"] == "ci"


def test_run_with_config_observability(monkeypatch, task_spec, tmp_path):
    calls: Dict[str, Any] = {}

    def fake_logging(*, enabled=None, stream=None, context=None, path=None):
        calls["logging"] = {"enabled": enabled, "path": path, "context": context}

    def fake_close_logging():
        calls["closed"] = True

    def fake_metrics(*, enabled=None, port=None, host="0.0.0.0"):
        calls["metrics"] = {"enabled": enabled, "port": port, "host": host}

    monkeypatch.setattr("metamorphic_guard.api.configure_logging", fake_logging)
    monkeypatch.setattr("metamorphic_guard.api.close_logging", fake_close_logging)
    monkeypatch.setattr("metamorphic_guard.api.configure_metrics", fake_metrics)

    mapping = {
        "metamorphic_guard": {
            "task": "api_test_task",
            "baseline": "tests.callable_fixtures:baseline_callable",
            "candidate": "tests.callable_fixtures:baseline_callable",
            "n": 1,
            "seed": 5,
            "min_delta": 0.0,
            "log_json": True,
            "log_file": str(tmp_path / "run.jsonl"),
            "metrics_enabled": True,
            "metrics_port": 9100,
            "metrics_host": "127.0.0.1",
        }
    }

    result = run_with_config(
        mapping,
        task=task_spec,
        logging_enabled=False,
        log_path=tmp_path / "override.jsonl",
        log_context={"job": "ci"},
        metrics_enabled=True,
        metrics_port=9200,
        metrics_host="127.0.0.2",
    )

    assert result.adopt is True
    assert calls["logging"]["enabled"] is False
    assert Path(calls["logging"]["path"]) == tmp_path / "override.jsonl"
    assert calls["logging"]["context"] == {"job": "ci"}
    assert calls["metrics"]["enabled"] is True
    assert calls["metrics"]["port"] == 9200
    assert calls["metrics"]["host"] == "127.0.0.2"
    assert calls["closed"] is True


def test_run_applies_dispatcher_and_queue(monkeypatch, task_spec):
    captured: Dict[str, Any] = {}

    def fake_run_eval(*args, **kwargs):
        captured.update(kwargs)
        return {
            "task": task_spec.name,
            "n": 1,
            "seed": 1,
            "decision": {"adopt": True, "reason": "ok"},
            "baseline": {"pass_rate": 1.0, "passes": 1, "total": 1, "prop_violations": [], "mr_violations": []},
            "candidate": {"pass_rate": 1.0, "passes": 1, "total": 1, "prop_violations": [], "mr_violations": []},
            "delta_pass_rate": 0.0,
            "delta_ci": [0.0, 0.0],
            "relative_risk": 1.0,
            "relative_risk_ci": [1.0, 1.0],
            "monitors": {},
            "config": {},
        }

    monkeypatch.setattr("metamorphic_guard.api.run_eval", fake_run_eval)
    monkeypatch.setattr("metamorphic_guard.api._dispatch_alerts", lambda *args, **kwargs: None)

    result = run(
        task=task_spec,
        baseline=Implementation.from_callable(baseline_callable),
        candidate=Implementation.from_callable(baseline_callable),
        config=EvaluationConfig(n=1, seed=1),
        dispatcher="queue",
        queue_config={"backend": "redis"},
        monitor_specs=["latency:percentile=0.9"],
    )

    assert result.adopt is True
    assert captured["dispatcher"] == "queue"
    assert captured["queue_config"] == {"backend": "redis"}
    assert len(captured["monitors"]) == 1
    assert isinstance(captured["monitors"][0], LatencyMonitor)


def test_resolve_monitor_specs_returns_instances():
    monitors = resolve_monitor_specs(["latency:percentile=0.8"], sandbox_plugins=False)
    assert len(monitors) == 1
    assert isinstance(monitors[0], LatencyMonitor)

