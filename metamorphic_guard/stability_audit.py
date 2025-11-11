"""
Stability audit tool for running evaluations across multiple seeds.

Detects flakiness and non-deterministic behavior by running the same evaluation
with different seeds and checking for consistent decisions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .harness import run_eval


def run_stability_audit(
    task_name: str,
    baseline_path: str,
    candidate_path: str,
    n: int = 400,
    seed_start: int = 42,
    num_seeds: int = 10,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Run evaluation across multiple seeds to detect flakiness.
    
    Args:
        task_name: Task to evaluate
        baseline_path: Path to baseline implementation
        candidate_path: Path to candidate implementation
        n: Number of test cases per run
        seed_start: Starting seed value
        num_seeds: Number of different seeds to test
        **kwargs: Additional arguments passed to run_eval
        
    Returns:
        Dictionary with stability audit results:
        - seeds: List of seeds tested
        - decisions: List of adoption decisions per seed
        - delta_pass_rates: List of delta pass rates per seed
        - delta_cis: List of delta CIs per seed
        - consensus: Whether all runs agreed
        - adopt_count: Number of runs that adopted
        - reject_count: Number of runs that rejected
        - flaky: Whether decisions were inconsistent
    """
    seeds = list(range(seed_start, seed_start + num_seeds))
    decisions: List[bool] = []
    delta_pass_rates: List[float] = []
    delta_cis: List[List[float]] = []
    reasons: List[str] = []
    
    for seed in seeds:
        result = run_eval(
            task_name=task_name,
            baseline_path=baseline_path,
            candidate_path=candidate_path,
            n=n,
            seed=seed,
            **kwargs,
        )
        
        decision = result.get("decision", {})
        decisions.append(decision.get("adopt", False))
        delta_pass_rates.append(result.get("delta_pass_rate", 0.0))
        delta_cis.append(result.get("delta_ci", [0.0, 0.0]))
        reasons.append(decision.get("reason", "unknown"))
    
    adopt_count = sum(decisions)
    reject_count = len(decisions) - adopt_count
    consensus = adopt_count == len(decisions) or reject_count == len(decisions)
    flaky = not consensus
    
    return {
        "seeds": seeds,
        "decisions": decisions,
        "delta_pass_rates": delta_pass_rates,
        "delta_cis": delta_cis,
        "reasons": reasons,
        "consensus": consensus,
        "adopt_count": adopt_count,
        "reject_count": reject_count,
        "flaky": flaky,
        "num_runs": len(seeds),
    }


def audit_to_report(audit_result: Dict[str, Any]) -> str:
    """Format stability audit results as a human-readable report."""
    lines = [
        "=" * 60,
        "Stability Audit Report",
        "=" * 60,
        "",
        f"Runs: {audit_result['num_runs']}",
        f"Adopt: {audit_result['adopt_count']}",
        f"Reject: {audit_result['reject_count']}",
        f"Consensus: {'Yes' if audit_result['consensus'] else 'No'}",
        f"Flaky: {'Yes ⚠️' if audit_result['flaky'] else 'No ✓'}",
        "",
        "Per-Seed Results:",
        "-" * 60,
    ]
    
    for i, seed in enumerate(audit_result["seeds"]):
        decision = "ADOPT" if audit_result["decisions"][i] else "REJECT"
        delta = audit_result["delta_pass_rates"][i]
        ci = audit_result["delta_cis"][i]
        reason = audit_result["reasons"][i]
        lines.append(
            f"Seed {seed:4d}: {decision:6s} | Δ={delta:7.4f} | CI=[{ci[0]:7.4f}, {ci[1]:7.4f}] | {reason}"
        )
    
    lines.append("")
    
    if audit_result["flaky"]:
        lines.append("⚠️  WARNING: Inconsistent decisions detected across seeds!")
        lines.append("   This indicates non-deterministic behavior or insufficient sample size.")
    
    return "\n".join(lines)

