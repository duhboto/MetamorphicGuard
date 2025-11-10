"""Evaluation helper orchestration for the Fairness Guard project."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from metamorphic_guard.gate import decide_adopt
from metamorphic_guard.harness import run_eval
from metamorphic_guard.util import write_report
from metamorphic_guard.sandbox import run_in_sandbox

from .spec import SENSITIVE_GROUPS, credit_fairness_spec

Applicants = List[Dict[str, float | int | str]]
Constraints = Dict[str, float]
TaskInput = Tuple[Applicants, Constraints]


@dataclass
class FairnessMetrics:
    """Aggregated approval statistics for a model run."""

    overall_approval_rate: float
    fairness_gap: float
    group_approval_rates: Dict[str, float]
    applicants_evaluated: int
    datasets_evaluated: int

    def to_dict(self) -> Dict[str, object]:
        return {
            "overall_approval_rate": self.overall_approval_rate,
            "fairness_gap": self.fairness_gap,
            "group_approval_rates": self.group_approval_rates,
            "applicants_evaluated": self.applicants_evaluated,
            "datasets_evaluated": self.datasets_evaluated,
        }


@dataclass
class EvaluationOutcome:
    """Summary of a Fairness Guard evaluation."""

    candidate_path: Path
    adopted: bool
    reason: str
    report_path: Path
    delta_pass_rate: float
    ci_lower: float
    ci_upper: float
    baseline_metrics: FairnessMetrics
    candidate_metrics: FairnessMetrics


def evaluate_candidate(
    candidate_path: Path,
    *,
    baseline_path: Optional[Path] = None,
    test_cases: int = 400,
    seed: int = 42,
    timeout_s: float = 2.0,
    mem_mb: int = 512,
    improve_delta: float = 0.0,
    min_pass_rate: float = 0.85,
    violation_cap: int = 25,
    parallel: int = 1,
    bootstrap_samples: int = 500,
    report_dir: Optional[Path] = None,
    executor: Optional[str] = None,
    executor_config: Optional[Dict[str, object]] = None,
) -> EvaluationOutcome:
    """
    Run the Metamorphic Guard evaluation for credit fairness policies.

    The baseline defaults to the production policy bundled with the project.
    """
    project_root = Path(__file__).resolve().parents[2]
    default_baseline = project_root / "implementations" / "baseline_model.py"
    baseline = baseline_path or default_baseline

    result = run_eval(
        task_name="credit_fairness",
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
        executor=executor,
        executor_config=executor_config,
    )

    test_inputs = _load_test_inputs(test_cases, seed)
    baseline_metrics = _compute_fairness_metrics(
        str(baseline), test_inputs, timeout_s, mem_mb
    )
    candidate_metrics = _compute_fairness_metrics(
        str(candidate_path), test_inputs, timeout_s, mem_mb
    )

    decision = decide_adopt(
        result,
        improve_delta=improve_delta,
        min_pass_rate=min_pass_rate,
    )
    result["decision"] = decision
    result["baseline"]["fairness_metrics"] = baseline_metrics.to_dict()
    result["candidate"]["fairness_metrics"] = candidate_metrics.to_dict()
    report = Path(write_report(result, directory=report_dir))

    delta_ci = result["delta_ci"]
    return EvaluationOutcome(
        candidate_path=Path(candidate_path),
        adopted=decision["adopt"],
        reason=decision["reason"],
        report_path=report,
        delta_pass_rate=result["delta_pass_rate"],
        ci_lower=float(delta_ci[0]),
        ci_upper=float(delta_ci[1]),
        baseline_metrics=baseline_metrics,
        candidate_metrics=candidate_metrics,
    )


def _load_test_inputs(n: int, seed: int) -> Sequence[TaskInput]:
    spec = credit_fairness_spec()
    return spec.gen_inputs(n, seed)


def _compute_fairness_metrics(
    file_path: str,
    test_inputs: Sequence[TaskInput],
    timeout_s: float,
    mem_mb: int,
) -> FairnessMetrics:
    total_applicants = 0
    total_approvals = 0
    datasets_evaluated = 0

    group_totals: Dict[str, int] = {group: 0 for group in SENSITIVE_GROUPS}
    group_approvals: Dict[str, int] = {group: 0 for group in SENSITIVE_GROUPS}

    for applicants, constraints in test_inputs:
        sandbox_args = _clone_task_input(applicants, constraints)
        result = run_in_sandbox(
            file_path,
            "solve",
            sandbox_args,
            timeout_s,
            mem_mb,
        )
        if not result.get("success"):
            continue

        output = result.get("result")
        if not isinstance(output, dict):
            continue

        datasets_evaluated += 1
        for applicant in applicants:
            applicant_id = str(applicant["id"])
            group = str(applicant["group"])
            approved = bool(output.get(applicant_id, False))
            total_applicants += 1
            if group not in group_totals:
                group_totals[group] = 0
                group_approvals[group] = 0
            group_totals[group] += 1
            if approved:
                total_approvals += 1
                group_approvals[group] += 1

    overall_rate = (
        total_approvals / total_applicants if total_applicants else 0.0
    )

    group_rates: Dict[str, float] = {}
    for group, total in group_totals.items():
        if total == 0:
            continue
        group_rates[group] = group_approvals.get(group, 0) / total

    if group_rates:
        fairness_gap = max(group_rates.values()) - min(group_rates.values())
    else:
        fairness_gap = 0.0

    return FairnessMetrics(
        overall_rate,
        fairness_gap,
        group_rates,
        total_applicants,
        datasets_evaluated,
    )


def _clone_task_input(
    applicants: Sequence[Dict[str, float | int | str]],
    constraints: Dict[str, float],
) -> Tuple[List[Dict[str, float | int | str]], Dict[str, float]]:
    cloned_applicants = [dict(applicant) for applicant in applicants]
    cloned_constraints = dict(constraints)
    return cloned_applicants, cloned_constraints
