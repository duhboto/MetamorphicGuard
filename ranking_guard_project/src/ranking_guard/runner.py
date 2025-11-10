"""
Core evaluation helpers that orchestrate Metamorphic Guard for ranking releases.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from metamorphic_guard.gate import decide_adopt
from metamorphic_guard.harness import run_eval
from metamorphic_guard.util import write_report


@dataclass
class EvaluationOutcome:
    """Summary of a single evaluation run."""

    candidate_path: Path
    adopted: bool
    reason: str
    report_path: Path
    delta_pass_rate: float
    ci_lower: float
    ci_upper: float
    relative_risk: float
    rr_ci_lower: float
    rr_ci_upper: float


def evaluate_candidate(
    candidate_path: Path,
    *,
    baseline_path: Optional[Path] = None,
    test_cases: int = 400,
    seed: int = 42,
    timeout_s: float = 2.0,
    mem_mb: int = 512,
    improve_delta: float = 0.0,
    min_pass_rate: float = 0.8,
    violation_cap: int = 25,
    parallel: int = 1,
    bootstrap_samples: int = 500,
    ci_method: str = "bootstrap",
    rr_ci_method: str = "log",
    report_dir: Optional[Path] = None,
    executor: Optional[str] = None,
    executor_config: Optional[Dict[str, object]] = None,
) -> EvaluationOutcome:
    """
    Run the Metamorphic Guard evaluation and return a structured summary.

    The baseline defaults to the production implementation bundled with this
    project if not explicitly supplied.
    """
    project_root = Path(__file__).resolve().parents[2]
    default_baseline = project_root / "implementations" / "baseline_ranker.py"
    baseline = baseline_path or default_baseline

    result = run_eval(
        task_name="top_k",
        baseline_path=str(baseline),
        candidate_path=str(candidate_path),
        n=test_cases,
        seed=seed,
        timeout_s=timeout_s,
        mem_mb=mem_mb,
        alpha=0.05,
        violation_cap=violation_cap,
        parallel=parallel,
        improve_delta=improve_delta,
        bootstrap_samples=bootstrap_samples,
        ci_method=ci_method,
        rr_ci_method=rr_ci_method,
        executor=executor,
        executor_config=executor_config,
    )

    decision = decide_adopt(
        result,
        improve_delta=improve_delta,
        min_pass_rate=min_pass_rate,
    )
    result["decision"] = decision
    report = Path(write_report(result, directory=report_dir))

    delta_ci = result["delta_ci"]
    rr_ci = result["relative_risk_ci"]
    return EvaluationOutcome(
        candidate_path=Path(candidate_path),
        adopted=decision["adopt"],
        reason=decision["reason"],
        report_path=report,
        delta_pass_rate=result["delta_pass_rate"],
        ci_lower=float(delta_ci[0]),
        ci_upper=float(delta_ci[1]),
        relative_risk=float(result["relative_risk"]),
        rr_ci_lower=float(rr_ci[0]),
        rr_ci_upper=float(rr_ci[1]),
    )
