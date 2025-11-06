# Ranking Guard Project

This project models a realistic workflow for qualifying new ranking algorithms
before rolling them into production. It uses the published `metamorphic-guard`
package to compare baseline and candidate implementations of a `top_k` style
ranker and decides whether to adopt the candidate.

## Scenario

A search team maintains a baseline ranking implementation. Engineers submit new
algorithms that must:

1. Pass all property-based checks (results have correct length, ordering, and elements).
2. Respect metamorphic relations (permuting inputs or adding low-value noise does not change outputs).
3. Achieve at least the baseline pass rate with a non-negative improvement delta.

## Layout

```
ranking_guard_project/
├── implementations/
│   ├── baseline_ranker.py      # Current production algorithm
│   ├── candidate_heap.py       # Efficient heap implementation (expected to pass)
│   └── candidate_buggy.py      # Regression that should be rejected
├── src/ranking_guard/
│   ├── __init__.py
│   ├── cli.py                  # CLI entry point
│   └── runner.py               # Library utilities
└── pyproject.toml
```

## Quick start

```bash
cd ranking_guard_project
python -m pip install -e .
ranking-guard evaluate --candidate implementations/candidate_heap.py
```

Run both candidates to see adoption vs rejection decisions:

```bash
ranking-guard evaluate --candidate implementations/candidate_heap.py
ranking-guard evaluate --candidate implementations/candidate_buggy.py
```

Useful flags:

- `--ci-method` to choose between `bootstrap`, `newcombe`, or `wilson` intervals for the
  pass-rate delta.
- `--rr-ci-method` to report relative risk confidence bounds.
- `--improve-delta` to enforce a minimum improvement threshold.
- `--parallel` to tune sandbox worker concurrency.

Reports are saved under `reports/` in the repository root so they can be fed
into dashboards or pull-request bots.
