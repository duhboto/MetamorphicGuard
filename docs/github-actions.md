# GitHub Actions Integration

Metamorphic Guard can be integrated into your CI/CD pipeline using GitHub Actions. This guide shows how to set up automated evaluation workflows.

## Quick Start

Copy the template workflow from `.github/workflows/metamorphic-guard-template.yml` to your repository's `.github/workflows/` directory and customize it for your needs.

## Basic Workflow

Here's a minimal example:

```yaml
name: Metamorphic Guard

on:
  pull_request:
    branches: ["main"]

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      
      - name: Install and run
        run: |
          pip install metamorphic-guard
          metamorphic-guard evaluate \
            --task top_k \
            --baseline baseline.py \
            --candidate candidate.py \
            --html-report report.html \
            --junit-report junit.xml
      
      - name: Upload reports
        uses: actions/upload-artifact@v4
        with:
          name: reports
          path: |
            report.html
            junit.xml
            reports/*.json
```

## Features

The template workflow includes:

1. **Automatic Evaluation**: Runs on pull requests and manual triggers
2. **Report Upload**: Uploads HTML, JSON, and JUnit XML reports as artifacts
3. **PR Comments**: Automatically comments on PRs with evaluation results
4. **Badge Generation**: Creates a status badge based on the decision
5. **Job Failure**: Fails the CI job if the candidate is rejected

## Customization

### Using a Policy File

```yaml
- name: Run evaluation
  run: |
    metamorphic-guard evaluate \
      --task my_task \
      --baseline baseline.py \
      --candidate candidate.py \
      --policy policies/strict.toml \
      --html-report report.html
```

### Custom Parameters

```yaml
- name: Run evaluation
  run: |
    metamorphic-guard evaluate \
      --task my_task \
      --baseline baseline.py \
      --candidate candidate.py \
      --n 1000 \
      --stability 3 \
      --shrink-violations \
      --ci-method bootstrap-cluster \
      --min-delta 0.05 \
      --min-pass-rate 0.90
```

### Using Config Files

Create a `metaguard.toml` in your repo:

```toml
task = "my_task"
baseline = "baseline.py"
candidate = "candidate.py"
n = 1000
stability = 3
ci_method = "bootstrap"
min_delta = 0.05
min_pass_rate = 0.90
```

Then reference it in the workflow:

```yaml
- name: Run evaluation
  run: |
    metamorphic-guard --config metaguard.toml \
      --html-report report.html \
      --junit-report junit.xml
```

## PR Comments

The template workflow automatically comments on pull requests with:

- Decision (adopt/reject)
- Delta pass rate and confidence interval
- Baseline vs candidate metrics
- Relation coverage summary
- Link to full report

## Badges

The workflow generates an SVG badge indicating pass/fail status. You can:

1. Upload the badge to your repository
2. Reference it in your README: `![Metamorphic Guard](https://github.com/your-org/your-repo/actions/workflows/metamorphic-guard.yml/badge.svg)`
3. Use GitHub's badge service: `https://img.shields.io/github/actions/workflow/status/your-org/your-repo/metamorphic-guard.yml`

## Exit Codes

- `0`: Candidate adopted (passes gate)
- `1`: Candidate rejected (fails gate)
- `2`: Internal error

Configure your workflow to fail on rejection:

```yaml
- name: Fail on rejection
  run: |
    metamorphic-guard evaluate ... || exit 1
```

## Advanced: Multiple Tasks

Evaluate multiple tasks in parallel:

```yaml
jobs:
  evaluate-ranking:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install metamorphic-guard
      - run: |
          metamorphic-guard evaluate \
            --task ranking \
            --baseline ranking_baseline.py \
            --candidate ranking_candidate.py
  
  evaluate-fairness:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install metamorphic-guard
      - run: |
          metamorphic-guard evaluate \
            --task fairness \
            --baseline fairness_baseline.py \
            --candidate fairness_candidate.py
```

## See Also

- [First PR Gate Tutorial](first-pr-gate-tutorial.md) - Step-by-step setup guide
- [MR Library](mr-library.md) - Choosing appropriate metamorphic relations
- [Policy Documentation](policies.md) - Configuring adoption gates

