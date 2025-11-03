# Fairness Guard Project

Fairness Guard demonstrates how Metamorphic Guard can enforce social-impact
requirements on machine learning systems. The project evaluates credit approval
models against a fairness-focused task specification that blends functional
invariants, counterfactual checks, and parity metrics. The harness decides
whether a candidate model should replace a production baseline by auditing both
robustness and equality of opportunity.

## Scenario

A responsible lending team maintains a baseline credit approval policy. New
models must:

1. Preserve functional guarantees (stable outputs, boolean decisions, minimum
   approval rate).
2. Respect metamorphic relations that mimic deployment realities (data order,
   currency scaling, superfluous features).
3. Meet a demographic-parity bound: the difference in approval rates between
   sensitive groups must stay within a configurable fairness gap.

The evaluation pipeline renders machine-readable JSON reports so teams can plug
results into governance dashboards, CI gates, or model cards.

## Layout

```
fairness_guard_project/
├── implementations/
│   ├── baseline_model.py       # Current production policy
│   ├── candidate_fair.py       # Fairness-aware upgrade (expected to pass)
│   └── candidate_biased.py     # Regression that violates fairness
├── src/fairness_guard/
│   ├── __init__.py
│   ├── cli.py                  # CLI entry point
│   ├── runner.py               # Evaluation helper
│   └── spec.py                 # Task registration & generators
└── pyproject.toml
```

## Quick start

```bash
cd fairness_guard_project
python -m pip install -e .
fairness-guard evaluate --candidate implementations/candidate_fair.py
```

Run both candidates to observe adoption vs rejection:

```bash
fairness-guard evaluate --candidate implementations/candidate_fair.py
fairness-guard evaluate --candidate implementations/candidate_biased.py
```

Reports land under `reports/` in the repository root so you can commit them,
attach them to review threads, or surface them in compliance tooling. Each run
records fairness diagnostics—overall approval rate, group-level approval rates,
and the observed parity gap—so dashboards and auditors can trace exactly how a
candidate behaves.
