from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from metamorphic_guard.api import Implementation, TaskSpec, run_with_config
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


def test_run_with_config_dict(monkeypatch, task_spec):
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

