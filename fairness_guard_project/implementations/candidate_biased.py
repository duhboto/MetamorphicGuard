"""Intentionally biased candidate that favours one demographic group."""

from __future__ import annotations

from typing import Dict, List


Applicant = Dict[str, float | int | str]
Constraints = Dict[str, float]


def solve(applicants: List[Applicant], constraints: Constraints) -> Dict[str, bool]:
    if not applicants:
        return {}

    min_positive_rate = float(constraints.get("min_positive_rate", 0.3))
    approvals_needed = max(1, int(round(len(applicants) * min_positive_rate)))

    scored = []
    for applicant in applicants:
        income = float(applicant.get("income", 0.0))
        debt = float(applicant.get("debt", 0.0))
        credit_score = float(applicant.get("credit_score", 0.0))
        employment_years = float(applicant.get("employment_years", 0.0))
        group = str(applicant.get("group", "A"))

        capacity = income / (debt + 1.0)
        raw_score = (
            0.6 * min(max((credit_score - 500.0) / 350.0, 0.0), 1.0)
            + 0.2 * min(capacity / 12.0, 1.0)
            + 0.2 * min(employment_years / 20.0, 1.0)
        )

        # Problematic bias: give a fixed preference to group A.
        if group == "A":
            raw_score += 0.12
        else:
            raw_score -= 0.12

        scored.append(
            {
                "id": str(applicant["id"]),
                "group": group,
                "score": raw_score,
            }
        )

    scored.sort(key=lambda record: record["score"], reverse=True)
    approved_ids = {record["id"] for record in scored[:approvals_needed]}
    return {record["id"]: record["id"] in approved_ids for record in scored}
