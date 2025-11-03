"""Baseline credit approval policy with fairness post-processing."""

from __future__ import annotations

from collections import defaultdict
import math
from statistics import mean
from typing import Dict, Iterable, List, Tuple


Applicant = Dict[str, float | int | str]
Constraints = Dict[str, float]


def solve(applicants: List[Applicant], constraints: Constraints) -> Dict[str, bool]:
    """
    Produce boolean approval decisions keyed by applicant id.

    The baseline blends a simple scoring model with demographic parity
    adjustments to keep group approval rates within the configured gap.
    """
    if not applicants:
        return {}

    fairness_gap = float(constraints.get("fairness_gap", 0.25))
    min_positive_rate = float(constraints.get("min_positive_rate", 0.3))

    scored = _score_applicants(applicants)
    _apply_group_offsets(scored)

    approvals, target = _initial_approvals(scored, min_positive_rate)
    approvals = _rebalance_groups(approvals, scored, fairness_gap, target)
    return approvals


def _score_applicants(applicants: List[Applicant]) -> List[Dict[str, object]]:
    scored: List[Dict[str, object]] = []
    for applicant in applicants:
        income = float(applicant.get("income", 0.0))
        debt = float(applicant.get("debt", 0.0))
        credit_score = float(applicant.get("credit_score", 0.0))
        employment_years = float(applicant.get("employment_years", 0.0))
        dependents = float(applicant.get("dependents", 0.0))
        delinquencies = float(applicant.get("delinquencies", 0.0))

        capacity_ratio = income / (debt + 1.0)
        capacity_component = min(capacity_ratio / 12.0, 1.0)
        credit_component = min(max(credit_score - 500.0, 0.0) / 350.0, 1.0)
        tenure_component = min(employment_years / 20.0, 1.0)
        dependent_penalty = 1.0 - min(dependents / 12.0, 0.6)
        delinquency_penalty = 1.0 - min(delinquencies / 8.0, 1.0)

        base_score = (
            0.42 * credit_component
            + 0.28 * capacity_component
            + 0.12 * tenure_component
            + 0.10 * dependent_penalty
            + 0.08 * delinquency_penalty
        )

        scored.append(
            {
                "id": str(applicant["id"]),
                "group": str(applicant.get("group", "A")),
                "base_score": max(0.0, min(1.0, base_score)),
            }
        )
    return scored


def _apply_group_offsets(scored: List[Dict[str, object]]) -> None:
    """Center group means to reduce systemic bias prior to gating."""
    group_scores: Dict[str, List[float]] = defaultdict(list)
    for record in scored:
        group_scores[str(record["group"])].append(float(record["base_score"]))

    all_scores = [score for scores in group_scores.values() for score in scores]
    if not all_scores:
        for record in scored:
            record["adjusted"] = float(record["base_score"])
        return

    global_mean = mean(all_scores)
    offsets = {
        group: (mean(scores) - global_mean) * 0.65
        for group, scores in group_scores.items()
    }

    for record in scored:
        group = str(record["group"])
        adjustment = offsets.get(group, 0.0)
        record["adjusted"] = float(record["base_score"]) - adjustment


def _initial_approvals(
    scored: List[Dict[str, object]],
    min_positive_rate: float,
) -> Tuple[Dict[str, bool], int]:
    sorted_records = sorted(scored, key=lambda rec: rec["adjusted"], reverse=True)
    approvals_needed = max(1, math.ceil(len(sorted_records) * min_positive_rate))

    approved_ids = {
        record["id"] for record in sorted_records[:approvals_needed]
    }
    approvals = {record["id"]: record["id"] in approved_ids for record in scored}
    return approvals, approvals_needed


def _rebalance_groups(
    approvals: Dict[str, bool],
    scored: List[Dict[str, object]],
    fairness_gap: float,
    target_approvals: int,
) -> Dict[str, bool]:
    if len(scored) <= 1:
        return approvals

    records_by_id = {record["id"]: record for record in scored}

    for _ in range(len(scored) * 2):
        rates = _approval_rates(approvals, scored)
        if len(rates) < 2:
            break

        max_group = max(rates, key=rates.get)
        min_group = min(rates, key=rates.get)
        if rates[max_group] - rates[min_group] <= fairness_gap + 1e-12:
            break

        demote_candidates = sorted(
            (
                record
                for record in scored
                if approvals[record["id"]] and record["group"] == max_group
            ),
            key=lambda rec: rec["adjusted"],
        )
        promote_candidates = sorted(
            (
                record
                for record in scored
                if not approvals[record["id"]] and record["group"] == min_group
            ),
            key=lambda rec: rec["adjusted"],
            reverse=True,
        )

        if not demote_candidates or not promote_candidates:
            break

        demote = demote_candidates[0]["id"]
        promote = promote_candidates[0]["id"]

        approvals[demote] = False
        approvals[promote] = True

    approved_records = sorted(
        (records_by_id[app_id] for app_id, approved in approvals.items() if approved),
        key=lambda rec: rec["adjusted"],
    )
    while len(approved_records) > target_approvals:
        lowest = approved_records.pop(0)
        approvals[lowest["id"]] = False

    return approvals


def _approval_rates(approvals: Dict[str, bool], scored: Iterable[Dict[str, object]]) -> Dict[str, float]:
    totals: Dict[str, int] = defaultdict(int)
    wins: Dict[str, int] = defaultdict(int)

    for record in scored:
        group = str(record["group"])
        totals[group] += 1
        if approvals.get(record["id"], False):
            wins[group] += 1

    rates = {
        group: (wins[group] / totals[group]) if totals[group] else 0.0
        for group in totals
    }
    return rates
