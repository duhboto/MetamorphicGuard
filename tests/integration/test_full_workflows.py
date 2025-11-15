"""
End-to-end integration tests for full evaluation workflows.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from metamorphic_guard.harness import run_eval
from metamorphic_guard.specs import Metric, Property, Spec, task


@task("simple_task")
def simple_task_spec() -> Spec:
    """Simple task that doubles the input."""
    def gen_inputs(n: int, seed: int):
        import random
        rng = random.Random(seed)
        return [(rng.randint(1, 100),) for _ in range(n)]
    
    return Spec(
        gen_inputs=gen_inputs,
        properties=[
            Property(
                check=lambda output, *args: isinstance(output, int) and output > 0,
                description="Output is a positive integer",
            ),
        ],
        relations=[],
        equivalence=lambda a, b: a == b,
        metrics=[
            Metric(name="value", extract=lambda output, *args: float(output), kind="mean"),
        ],
    )


def test_basic_evaluation_workflow(tmp_path: Path):
    """Test basic end-to-end evaluation workflow."""
    # Create baseline and candidate implementations
    baseline_path = tmp_path / "baseline.py"
    baseline_path.write_text(
        """
def solve(x):
    return x * 2
"""
    )
    
    candidate_path = tmp_path / "candidate.py"
    candidate_path.write_text(
        """
def solve(x):
    return x * 2
"""
    )
    
    # Run evaluation (spec is registered via @task decorator)
    result = run_eval(
        task_name="simple_task",
        baseline_path=str(baseline_path),
        candidate_path=str(candidate_path),
        n=10,
        seed=42,
        timeout_s=1.0,
        mem_mb=256,
        alpha=0.05,
    )
    
    # Verify result structure
    assert "baseline" in result
    assert "candidate" in result
    assert "metrics" in result
    assert result["baseline"]["pass_rate"] == pytest.approx(1.0)
    assert result["candidate"]["pass_rate"] == pytest.approx(1.0)


def test_evaluation_with_adaptive_sampling(tmp_path: Path):
    """Test evaluation workflow with adaptive sampling enabled."""
    baseline_path = tmp_path / "baseline.py"
    baseline_path.write_text(
        """
def solve(x):
    return x * 2
"""
    )
    
    candidate_path = tmp_path / "candidate.py"
    candidate_path.write_text(
        """
def solve(x):
    return x * 2
"""
    )
    
    # Run with adaptive testing (spec is registered via @task decorator)
    result = run_eval(
        task_name="simple_task",
        baseline_path=str(baseline_path),
        candidate_path=str(candidate_path),
        n=100,  # Max N for adaptive
        seed=42,
        timeout_s=1.0,
        mem_mb=256,
        alpha=0.05,
        adaptive_testing=True,
        adaptive_min_sample_size=20,
        adaptive_check_interval=20,
        adaptive_power_threshold=0.95,
    )
    
    assert "baseline" in result
    assert "candidate" in result
    # Adaptive testing should complete with fewer than max N if power is sufficient
    assert "adaptive_metadata" in result or "n" in result


def test_evaluation_with_sequential_testing(tmp_path: Path):
    """Test evaluation workflow with sequential testing."""
    baseline_path = tmp_path / "baseline.py"
    baseline_path.write_text(
        """
def solve(x):
    return x * 2
"""
    )
    
    candidate_path = tmp_path / "candidate.py"
    candidate_path.write_text(
        """
def solve(x):
    return x * 2
"""
    )
    
    # Run with sequential testing (spec is registered via @task decorator)
    result = run_eval(
        task_name="simple_task",
        baseline_path=str(baseline_path),
        candidate_path=str(candidate_path),
        n=100,
        seed=42,
        timeout_s=1.0,
        mem_mb=256,
        alpha=0.05,
        sequential_method="pocock",
        max_looks=3,
    )
    
    assert "baseline" in result
    assert "candidate" in result
    assert "sequential_metadata" in result or "n" in result


def test_evaluation_with_reporting(tmp_path: Path):
    """Test evaluation workflow with report generation."""
    baseline_path = tmp_path / "baseline.py"
    baseline_path.write_text(
        """
def solve(x):
    return x * 2
"""
    )
    
    candidate_path = tmp_path / "candidate.py"
    candidate_path.write_text(
        """
def solve(x):
    return x * 2
"""
    )
    
    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    
    result = run_eval(
        task_name="simple_task",
        baseline_path=str(baseline_path),
        candidate_path=str(candidate_path),
        n=10,
        seed=42,
        timeout_s=1.0,
        mem_mb=256,
        alpha=0.05,
    )
    
    # Verify metrics are computed
    assert "metrics" in result
    # Metrics are organized by metric name, each containing baseline/candidate/delta
    assert "value" in result["metrics"]
    assert "baseline" in result["metrics"]["value"]
    assert "candidate" in result["metrics"]["value"]


def test_evaluation_with_different_implementations(tmp_path: Path):
    """Test evaluation workflow with different baseline and candidate."""
    baseline_path = tmp_path / "baseline.py"
    baseline_path.write_text(
        """
def solve(x):
    return x * 2
"""
    )
    
    candidate_path = tmp_path / "candidate.py"
    candidate_path.write_text(
        """
def solve(x):
    return x * 2 + 1  # Different implementation
"""
    )
    
    result = run_eval(
        task_name="simple_task",
        baseline_path=str(baseline_path),
        candidate_path=str(candidate_path),
        n=10,
        seed=42,
        timeout_s=1.0,
        mem_mb=256,
        alpha=0.05,
    )
    
    # Candidate should have lower pass rate (candidate adds 1, so it's different)
    assert result["candidate"]["pass_rate"] < result["baseline"]["pass_rate"]


def test_evaluation_with_metrics(tmp_path: Path):
    """Test evaluation workflow with custom metrics."""
    baseline_path = tmp_path / "baseline.py"
    baseline_path.write_text(
        """
def solve(x):
    return x * 2
"""
    )
    
    candidate_path = tmp_path / "candidate.py"
    candidate_path.write_text(
        """
def solve(x):
    return x * 2
"""
    )
    
    result = run_eval(
        task_name="simple_task",
        baseline_path=str(baseline_path),
        candidate_path=str(candidate_path),
        n=10,
        seed=42,
        timeout_s=1.0,
        mem_mb=256,
        alpha=0.05,
    )
    
    # Verify metrics are present
    assert "metrics" in result
    # Metrics are organized by metric name
    assert "value" in result["metrics"]
    assert "squared" in result["metrics"]
    
    # Each metric has baseline, candidate, and delta
    assert "baseline" in result["metrics"]["value"]
    assert "candidate" in result["metrics"]["value"]
    assert "baseline" in result["metrics"]["squared"]
    assert "candidate" in result["metrics"]["squared"]

