from __future__ import annotations

import textwrap

from tests.callable_fixtures import (
    bad_candidate_callable,
    baseline_callable,
    candidate_callable,
)

from metamorphic_guard.api import (
    EvaluationConfig,
    Implementation,
    Metric,
    Property,
    TaskSpec,
    run,
)


def _build_task_spec() -> TaskSpec:
    def gen_inputs(n: int, seed: int):
        return [(i,) for i in range(n)]

    def eq(a, b):
        return a == b

    return TaskSpec(
        name="api_test_task",
        gen_inputs=gen_inputs,
        properties=[
            Property(
                check=lambda output, x: isinstance(output, dict) and "value" in output,
                description="Returns dict with value key",
            ),
            Property(
                check=lambda output, x: float(output["value"]) >= float(x),
                description="Candidate value should not drop below input",
            ),
        ],
        relations=[],
        equivalence=eq,
        metrics=[
            Metric(
                name="value_mean",
                extract=lambda output, _: float(output["value"]),
                kind="mean",
                seed=123,
            )
        ],
    )


def test_api_run_accepts_candidate(tmp_path):
    baseline_code = textwrap.dedent(
        """
        def solve(x):
            return {"value": float(x)}
        """
    )
    candidate_code = textwrap.dedent(
        """
        def solve(x):
            return {"value": float(x) + 0.5}
        """
    )

    baseline_file = tmp_path / "baseline.py"
    candidate_file = tmp_path / "candidate.py"
    baseline_file.write_text(baseline_code, encoding="utf-8")
    candidate_file.write_text(candidate_code, encoding="utf-8")

    result = run(
        task=_build_task_spec(),
        baseline=Implementation(path=str(baseline_file)),
        candidate=Implementation(path=str(candidate_file)),
        config=EvaluationConfig(
            n=10,
            seed=123,
            bootstrap_samples=200,
            improve_delta=0.0,
        ),
    )

    assert isinstance(result.report, dict)
    assert result.adopt is True
    assert "value_mean" in result.report.get("metrics", {})


def test_api_run_rejects_candidate(tmp_path):
    baseline_code = textwrap.dedent(
        """
        def solve(x):
            return {"value": float(x)}
        """
    )
    candidate_code = textwrap.dedent(
        """
        def solve(x):
            return {"value": float(x) - 5.0}
        """
    )

    baseline_file = tmp_path / "baseline_bad.py"
    candidate_file = tmp_path / "candidate_bad.py"
    baseline_file.write_text(baseline_code, encoding="utf-8")
    candidate_file.write_text(candidate_code, encoding="utf-8")

    result = run(
        task=_build_task_spec(),
        baseline=Implementation(path=str(baseline_file)),
        candidate=Implementation(path=str(candidate_file)),
        config=EvaluationConfig(
            n=10,
            seed=321,
            bootstrap_samples=200,
            improve_delta=0.0,
        ),
    )

    assert isinstance(result.report, dict)
    assert result.adopt is False
    assert "reason" in result.report.get("decision", {})


def test_api_run_accepts_callable():
    result = run(
        task=_build_task_spec(),
        baseline=Implementation.from_callable(baseline_callable),
        candidate=Implementation.from_callable(candidate_callable),
        config=EvaluationConfig(
            n=10,
            seed=777,
            bootstrap_samples=200,
            improve_delta=0.0,
        ),
    )

    assert result.adopt is True
    assert "value_mean" in result.report.get("metrics", {})


def test_api_run_rejects_callable(tmp_path):
    result = run(
        task=_build_task_spec(),
        baseline=Implementation.from_callable(baseline_callable),
        candidate=Implementation.from_callable(bad_candidate_callable),
        config=EvaluationConfig(
            n=10,
            seed=888,
            bootstrap_samples=200,
            improve_delta=0.0,
        ),
    )

    assert result.adopt is False


def test_callable_must_be_module_scoped():
    def local_fn(x):
        return {"value": float(x)}

    import pytest

    with pytest.raises(ValueError):
        Implementation.from_callable(local_fn)


def test_dotted_path_supports_callable():
    impl = Implementation.from_dotted("tests.callable_fixtures:baseline_callable")
    with impl.materialize() as path:
        assert path.endswith(".py")

    result = run(
        task=_build_task_spec(),
        baseline=impl,
        candidate=Implementation.from_dotted("tests.callable_fixtures:candidate_callable"),
        config=EvaluationConfig(
            n=5,
            seed=999,
            bootstrap_samples=100,
            improve_delta=0.0,
        ),
    )
    assert result.adopt is True


def test_dotted_path_rejects_bad_input():
    import pytest

    with pytest.raises(ValueError):
        Implementation.from_dotted("unknownmodule:func")

    with pytest.raises(ValueError):
        Implementation.from_dotted("tests.callable_fixtures:missing_attr")

    with pytest.raises(ValueError):
        Implementation.from_dotted("tests.callable_fixtures")

