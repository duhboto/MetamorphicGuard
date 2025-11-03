"""Fairness-aware upgrade that emphasises calibrated credit approvals."""

from __future__ import annotations

import math
from collections import defaultdict
from statistics import mean
from typing import Dict, Iterable, List, Tuple


Applicant = Dict[str, float | int | str]
Constraints = Dict[str, float]


def solve(applicants: List[Applicant], constraints: Constraints) -> Dict[str, bool]:
    """
    Produce approval decisions with calibrated parity.

    Compared with the baseline, this candidate emphasises probability
    calibration before the fairness adjustment step, which yields tighter
    confidence bounds on the pass-rate delta.
    """
    if not applicants:
        return {}

    fairness_gap = float(constraints.get("fairness_gap", 0.24))
    min_positive_rate = float(constraints.get("min_positive_rate", 0.3))

    scored = _score(applicants)
    _calibrate_groups(scored)

    approvals, target = _select_minimum_portfolio(scored, min_positive_rate)
    approvals = _parity_adjustment(approvals, scored, fairness_gap, target)
    return approvals


def _score(applicants: List[Applicant]) -> List[Dict[str, object]]:
    results: List[Dict[str, object]] = []
    for applicant in applicants:
        income = float(applicant.get("income", 0.0))
        debt = float(applicant.get("debt", 0.0))
        credit_score = float(applicant.get("credit_score", 0.0))
        employment_years = float(applicant.get("employment_years", 0.0))
        dependents = float(applicant.get("dependents", 0.0))
        delinquencies = float(applicant.get("delinquencies", 0.0))

        utilisation = income / (debt + 1.0)
        utilisation_component = min(utilisation / 12.0, 1.0)
        credit_component = min(max(credit_score - 480.0, 0.0) / 360.0, 1.0)
        stability_component = min(employment_years / 18.0, 1.0)
        dependent_penalty = 1.0 - min(dependents / 8.0, 0.5)
        delinquency_penalty = 1.0 - min(delinquencies / 6.0, 1.0)

        linear_score = (
            0.50 * credit_component
            + 0.23 * utilisation_component
            + 0.12 * stability_component
            + 0.08 * dependent_penalty
            + 0.07 * delinquency_penalty
        )
        calibrated = 1.0 / (1.0 + math.exp(-6.0 * (linear_score - 0.5)))

        results.append(
            {
                "id": str(applicant["id"]),
                "group": str(applicant.get("group", "A")),
                "score": calibrated,
            }
        )
    return results


def _calibrate_groups(scored: List[Dict[str, object]]) -> None:
    group_scores: Dict[str, List[float]] = defaultdict(list)
    for record in scored:
        group_scores[record["group"]].append(float(record["score"]))

    all_scores = [score for scores in group_scores.values() for score in scores]
    if not all_scores:
        for record in scored:
            record["adjusted"] = float(record["score"])
        return

    global_mean = mean(all_scores)
    offsets = {
        group: (mean(scores) - global_mean) * 0.7
        for group, scores in group_scores.items()
    }

    for record in scored:
        adjustment = offsets.get(record["group"], 0.0)
        record["adjusted"] = float(record["score"]) - adjustment


def _select_minimum_portfolio(
    scored: List[Dict[str, object]],
    min_positive_rate: float,
) -> Tuple[Dict[str, bool], int]:
    ordered = sorted(scored, key=lambda rec: rec["adjusted"], reverse=True)
    approvals_needed = max(1, math.ceil(len(ordered) * min_positive_rate))
    approved_ids = {record["id"] for record in ordered[:approvals_needed]}
    approvals = {record["id"]: record["id"] in approved_ids for record in scored}
    return approvals, approvals_needed


def _parity_adjustment(
    approvals: Dict[str, bool],
    scored: List[Dict[str, object]],
    fairness_gap: float,
    approvals_needed: int,
) -> Dict[str, bool]:
    if len(scored) <= 1:
        return approvals

    for _ in range(len(scored) * 2):
        rates = _rates(approvals, scored)
        if len(rates) < 2:
            break
        advantaged = max(rates, key=rates.get)
        disadvantaged = min(rates, key=rates.get)
        if rates[advantaged] - rates[disadvantaged] <= fairness_gap + 1e-12:
            break

        demote_candidates = sorted(
            (
                record
                for record in scored
                if approvals[record["id"]] and record["group"] == advantaged
            ),
            key=lambda rec: rec["adjusted"],
        )
        promote_candidates = sorted(
            (
                record
                for record in scored
                if not approvals[record["id"]] and record["group"] == disadvantaged
            ),
            key=lambda rec: rec["adjusted"],
            reverse=True,
        )

        if not demote_candidates or not promote_candidates:
            break

        approvals[demote_candidates[0]["id"]] = False
        approvals[promote_candidates[0]["id"]] = True

    approved = [
        record for record in scored if approvals.get(record["id"], False)
    ]
    approved.sort(key=lambda rec: rec["adjusted"], reverse=True)
    if len(approved) > approvals_needed:
        for record in approved[approvals_needed:]:
            approvals[record["id"]] = False

    return approvals


def _rates(approvals: Dict[str, bool], scored: Iterable[Dict[str, object]]) -> Dict[str, float]:
    totals: Dict[str, int] = defaultdict(int)
    wins: Dict[str, int] = defaultdict(int)
    for record in scored:
        group = record["group"]
        totals[group] += 1
        if approvals.get(record["id"], False):
            wins[group] += 1
    return {
        group: (wins[group] / totals[group]) if totals[group] else 0.0
        for group in totals
    }
