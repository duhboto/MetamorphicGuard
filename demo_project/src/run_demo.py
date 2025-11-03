"""
Demonstration script showing how to call Metamorphic Guard as a library.

It imports the published package, runs an evaluation between the bundled
top_k baseline and improved candidate, and prints the gate decision.
"""

from __future__ import annotations

from pathlib import Path

from metamorphic_guard.gate import decide_adopt
from metamorphic_guard.harness import run_eval
from metamorphic_guard.util import write_report


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    baseline = repo_root / "examples" / "top_k_baseline.py"
    candidate = repo_root / "examples" / "top_k_improved.py"

    result = run_eval(
        task_name="top_k",
        baseline_path=str(baseline),
        candidate_path=str(candidate),
        n=50,
        seed=123,
        timeout_s=1.0,
        mem_mb=128,
        alpha=0.05,
        violation_cap=10,
        parallel=1,
        improve_delta=0.01,
        bootstrap_samples=200,
    )

    decision = decide_adopt(result, improve_delta=0.01, min_pass_rate=0.8)
    result["decision"] = decision
    report_path = write_report(result)

    print("Metamorphic Guard demo")
    print("----------------------")
    print(f"Baseline:  {baseline}")
    print(f"Candidate: {candidate}")
    print(f"Pass delta: {result['delta_pass_rate']:.3f}")
    print(f"95% CI:     [{result['delta_ci'][0]:.3f}, {result['delta_ci'][1]:.3f}]")
    print(f"Adopt?     {decision['adopt']} ({decision['reason']})")
    print(f"Report:    {report_path}")


if __name__ == "__main__":
    main()
