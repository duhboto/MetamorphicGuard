# Governance & Policy Integration Guide

This guide shows how to integrate Metamorphic Guard into your governance process and policy management systems.

## Goals
- Centralize evaluation policy definitions as code
- Ensure reproducible, auditable promotion decisions
- Integrate with approval workflows, ticketing, and dashboards

## Policy as Code
- Store policies in version control under `policies/`
- Reference policies via CLI `--policy` or config
- Use policy presets for simple cases (e.g., `superiority:margin=0.02`)

## Artifact Strategy
- JSON reports (`reports/*.json`) as the source of truth
- HTML reports (`*.html`) for human review
- JUnit XML for CI dashboards
- Link artifacts in PR descriptions

## RACI & Approvals
- Document who can override decisions and how
- Require approvals when policy gates fail
- Capture waiver justifications in PRs or tickets

## Integration Patterns

### GitHub / GitLab
- Status checks fail on rejection (`adopt = false`)
- Upload artifacts and link in PR comments
- Enforce code owners for policy changes

### Ticketing (Jira, Linear)
- Create tickets for regressions
- Attach report artifacts
- Track mitigation items per monitor category

### Dashboards
- Ingest JSON reports into BI tools
- Track trends: pass rate, Δ CI, violations, cost, latency
- Segment by task, team, model, release

## Reference Workflow (GitHub Actions)

```yaml
name: Eval Gate
on:
  pull_request:

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install metamorphic-guard
      - name: Evaluate candidate
        run: |
          metamorphic-guard evaluate \
            --config metamorphic.toml \
            --policy policies/policy-v1.toml \
            --html-report reports/report.html
      - uses: actions/upload-artifact@v4
        with:
          name: eval-artifacts
          path: |
            reports/*.json
            reports/*.html
      - name: Fail if rejected
        run: |
          python - <<'PY'
          import json,glob
          data = json.load(open(sorted(glob.glob('reports/*.json'))[-1]))
          if not data.get('decision',{}).get('adopt', False):
              raise SystemExit('Candidate rejected by policy gate')
          PY
```

## Governance Checklist
- [ ] Policies versioned and reviewed
- [ ] Reports archived and linked to releases
- [ ] Waiver process documented
- [ ] CI fails on policy rejection
- [ ] Dashboards include key KPIs

