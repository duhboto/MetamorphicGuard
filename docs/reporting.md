# Reporting & Replay

This guide shows how to generate, replay, and render reports produced by Metamorphic Guard.

## JSON Report

Evaluations produce a JSON file with configuration, decisions, statistics, and artifacts:

- `decision`: `{ adopt: bool, reason: str }`
- `statistics`: pass rates, deltas, confidence intervals
- `relation_coverage`: per-relation results
- `provenance`: environment, git, versions
- `replay.cli`: a copy-pastable CLI command to reproduce the run

## Replay an Evaluation

From a report, copy the `replay.cli` field:

```bash
# Example
metamorphic-guard evaluate --task top_k \
  --baseline examples/top_k_baseline.py \
  --candidate examples/top_k_improved.py \
  --n 400 --seed 42 --ci-method bootstrap
```

You can add `--html-report` or `--junit-report` to generate additional artifacts.

## Render HTML

Generate an HTML summary from a JSON report:

```bash
metamorphic-guard report reports/report_2025-01-01T12-00-00.json -o report.html
```

Or during evaluation:

```bash
metamorphic-guard evaluate ... --html-report report.html
```

## CI Tips

- Upload `report.html` and the JSON report as workflow artifacts.
- Use `--junit-report` for CI test summaries and dashboards.
- Fail CI on rejection (non-zero exit) to prevent unsafe promotion.


