"""Task registration for fairness-aware credit approval evaluation."""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Sequence, Tuple

from metamorphic_guard import MetamorphicRelation, Property, Spec, task

Applicant = Dict[str, float | int | str]
Constraints = Dict[str, float]
TaskInput = Tuple[List[Applicant], Constraints]

SENSITIVE_GROUPS: Sequence[str] = ("A", "B")


def gen_credit_inputs(n: int, seed: int) -> List[TaskInput]:
    """Generate synthetic credit datasets with parity constraints."""
    rng = random.Random(seed)
    datasets: List[TaskInput] = []

    for dataset_index in range(n):
        applicant_count = rng.randint(32, 56)
        applicants: List[Applicant] = []

        base_income = rng.uniform(45_000, 110_000)
        base_debt = rng.uniform(12_000, 28_000)
        base_credit = rng.uniform(640, 710)

        for idx in range(applicant_count):
            group = SENSITIVE_GROUPS[idx % 2]
            if rng.random() < 0.15:
                group = rng.choice(SENSITIVE_GROUPS)

            income = max(22_000.0, rng.gauss(base_income, base_income * 0.35))
            debt = max(1_000.0, rng.gauss(base_debt * (1.05 if group == "B" else 0.95), base_debt * 0.4))
            credit_score = int(max(520, min(820, rng.gauss(base_credit + (10 if group == "A" else -10), 60))))
            employment_years = max(0, int(rng.gauss(6.5 if group == "A" else 5.5, 3.0)))
            dependents = max(0, int(rng.gauss(1.8 if group == "B" else 1.4, 1.2)))
            delinquencies = max(0, int(rng.gauss(1.2 if group == "B" else 0.8, 0.9)))

            applicant: Applicant = {
                "id": f"ds{dataset_index}_app{idx}",
                "group": group,
                "income": income,
                "debt": debt,
                "credit_score": credit_score,
                "employment_years": employment_years,
                "dependents": dependents,
                "delinquencies": delinquencies,
            }
            applicants.append(applicant)

        constraints: Constraints = {
            "fairness_gap": rng.uniform(0.18, 0.26),
            "min_positive_rate": rng.uniform(0.26, 0.36),
        }
        datasets.append((applicants, constraints))

    return datasets


def _property_output_shape(output: Dict[str, bool], applicants: List[Applicant], constraints: Constraints) -> bool:
    """Ensure outputs are boolean approvals keyed by applicant id."""
    if not isinstance(output, dict):
        return False

    expected_ids = {app["id"] for app in applicants}
    if set(output.keys()) != expected_ids:
        return False

    return all(isinstance(value, bool) for value in output.values())


def _property_minimum_approval(output: Dict[str, bool], applicants: List[Applicant], constraints: Constraints) -> bool:
    """Require a minimum approval rate to maintain portfolio health."""
    if not applicants:
        return True

    approvals = sum(1 for approved in output.values() if approved)
    rate = approvals / len(applicants)
    return rate + 1e-9 >= constraints["min_positive_rate"]


def _property_fairness_gap(output: Dict[str, bool], applicants: List[Applicant], constraints: Constraints) -> bool:
    """Enforce demographic-parity style fairness gap."""
    if not applicants:
        return True

    totals: Dict[str, int] = {group: 0 for group in SENSITIVE_GROUPS}
    approvals: Dict[str, int] = {group: 0 for group in SENSITIVE_GROUPS}

    for app in applicants:
        group = str(app["group"])
        totals[group] += 1
        if output.get(str(app["id"]), False):
            approvals[group] += 1

    present_groups = [group for group, total in totals.items() if total > 0]
    if len(present_groups) < 2:
        return True

    rates = [
        approvals[group] / totals[group] if totals[group] else 0.0
        for group in present_groups
    ]
    gap = max(rates) - min(rates)
    return gap <= constraints["fairness_gap"] + 1e-6


def _shuffle_applicants(
    applicants: List[Applicant],
    constraints: Constraints,
    *,
    rng: Optional[random.Random] = None,
) -> TaskInput:
    shuffled = [dict(app) for app in applicants]
    local_rng = rng or random.Random(len(applicants))
    local_rng.shuffle(shuffled)
    return shuffled, constraints


def _scale_currency(
    applicants: List[Applicant],
    constraints: Constraints,
    *,
    rng: Optional[random.Random] = None,
) -> TaskInput:
    local_rng = rng or random.Random(len(applicants) + 17)
    factor = local_rng.choice([0.5, 1.5, 2.0])
    scaled = []
    for app in applicants:
        clone = dict(app)
        clone["income"] = float(clone["income"]) * factor
        clone["debt"] = float(clone["debt"]) * factor
        scaled.append(clone)
    return scaled, constraints


def _inject_uninformative_feature(
    applicants: List[Applicant],
    constraints: Constraints,
    *,
    rng: Optional[random.Random] = None,
) -> TaskInput:
    base_seed = int(sum(float(app["credit_score"]) for app in applicants))
    local_rng = rng or random.Random(base_seed)
    augmented = []
    for app in applicants:
        clone = dict(app)
        clone["marketing_score"] = local_rng.uniform(-1.0, 1.0)
        augmented.append(clone)
    return augmented, constraints


def _mapping_equal(lhs: Dict[str, bool], rhs: Dict[str, bool]) -> bool:
    return lhs == rhs


def _fmt_in(args: TaskInput) -> str:
    applicants, constraints = args
    return (
        f"{len(applicants)} applicants | "
        f"gap≤{constraints['fairness_gap']:.2f} | "
        f"min_rate≥{constraints['min_positive_rate']:.2f}"
    )


def _fmt_out(output: Dict[str, bool]) -> str:
    approvals = sum(1 for approved in output.values() if approved)
    return f"approvals={approvals}"


@task("credit_fairness")
def credit_fairness_spec() -> Spec:
    """Register the fairness-focused credit approval task."""
    return Spec(
        gen_inputs=gen_credit_inputs,
        properties=[
            Property(
                check=_property_output_shape,
                description="Outputs map applicant ids to boolean approvals",
            ),
            Property(
                check=_property_minimum_approval,
                description="Portfolio maintains minimum approval rate",
            ),
            Property(
                check=_property_fairness_gap,
                description="Approval rate gap respects fairness constraint",
            ),
        ],
        relations=[
            MetamorphicRelation(
                name="shuffle_applicants",
                transform=_shuffle_applicants,
                expect="equal",
                accepts_rng=True,
                category="permutation_invariance",
                description="Shuffling applicant order should not change approvals",
            ),
            MetamorphicRelation(
                name="scale_currency",
                transform=_scale_currency,
                expect="equal",
                accepts_rng=True,
                category="scale_invariance",
                description="Scaling monetary features should not affect outcomes",
            ),
            MetamorphicRelation(
                name="inject_uninformative_feature",
                transform=_inject_uninformative_feature,
                expect="equal",
                accepts_rng=True,
                category="feature_invariance",
                description="Adding uninformative features should not change approvals",
            ),
        ],
        equivalence=_mapping_equal,
        fmt_in=_fmt_in,
        fmt_out=_fmt_out,
    )
