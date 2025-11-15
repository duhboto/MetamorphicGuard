# Fairness Guard Project

A responsibility-focused workflow for evaluating credit approval models against fairness requirements. This project demonstrates how to use Metamorphic Guard to enforce social-impact requirements on machine learning systems, blending functional invariants, counterfactual checks, and parity metrics.

## Overview

Fairness Guard provides a realistic example of how responsible lending teams can integrate Metamorphic Guard into their model evaluation process. It evaluates credit approval models against a fairness-focused task specification that:

1. **Preserves functional guarantees**: Stable outputs, boolean decisions, minimum approval rate
2. **Respects metamorphic relations**: Mimics deployment realities (data order, currency scaling, superfluous features)
3. **Enforces demographic parity**: Ensures approval rate differences between sensitive groups stay within a configurable fairness gap

The evaluation pipeline renders machine-readable JSON reports so teams can plug results into governance dashboards, CI gates, or model cards.

## Scenario

A responsible lending team maintains a baseline credit approval policy. New models must:

- Preserve functional guarantees (stable outputs, boolean decisions, minimum approval rate)
- Respect metamorphic relations that mimic deployment realities (data order, currency scaling, superfluous features)
- Meet a demographic-parity bound: the difference in approval rates between sensitive groups must stay within a configurable fairness gap

The evaluation pipeline renders machine-readable JSON reports so teams can plug results into governance dashboards, CI gates, or model cards.

## Project Structure

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
├── pyproject.toml
└── README.md
```

## Installation

### Prerequisites

- Python 3.10 or higher
- pip

### Install from Source

```bash
cd fairness_guard_project
pip install -e .
```

This installs:
- `metamorphic-guard` (core library)
- `click` (CLI framework)
- `rich` (terminal formatting)
- The `fairness-guard` CLI command

## Quick Start

### Basic Evaluation

Evaluate a candidate implementation:

```bash
fairness-guard evaluate --candidate implementations/candidate_fair.py
```

### Compare Multiple Candidates

Run both candidates to observe adoption vs rejection:

```bash
# This should pass (fairness-aware implementation)
fairness-guard evaluate --candidate implementations/candidate_fair.py

# This should fail (biased implementation violates fairness)
fairness-guard evaluate --candidate implementations/candidate_biased.py
```

### Example Output

**Accepted Candidate:**
```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                            Fairness Guard Result                                 ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Field                    Value                                                    ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Candidate                implementations/candidate_fair.py                       ┃
┃ Adopt?                   ✅ Yes                                                   ┃
┃ Reason                   meets_gate                                              ┃
┃ Δ Pass Rate              0.0150                                                 ┃
┃ Δ 95% CI                 [0.0050, 0.0250]                                       ┃
┃ Baseline Fairness Gap    0.12                                                   ┃
┃ Candidate Fairness Gap   0.10                                                   ┃
┃ Baseline Approval Rate   0.32                                                   ┃
┃ Candidate Approval Rate  0.33                                                   ┃
┃ Report                   reports/report_2025-01-15T12-00-00.json               ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

**Rejected Candidate:**
```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                            Fairness Guard Result                                 ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Field                    Value                                                    ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Candidate                implementations/candidate_biased.py                     ┃
┃ Adopt?                   ❌ No                                                    ┃
┃ Reason                   Improvement insufficient: CI lower bound -0.0100 < 0.0   ┃
┃ Δ Pass Rate              -0.0050                                                 ┃
┃ Δ 95% CI                 [-0.0150, 0.0050]                                      ┃
┃ Baseline Fairness Gap    0.12                                                   ┃
┃ Candidate Fairness Gap   0.28                                                    ┃
┃ Baseline Approval Rate   0.32                                                   ┃
┃ Candidate Approval Rate  0.31                                                   ┃
┃ Report                   reports/report_2025-01-15T12-00-05.json                ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

## CLI Options

### Core Options

- `--candidate PATH` (required): Path to the candidate credit approval implementation
- `--baseline PATH` (optional): Path to baseline implementation (defaults to bundled `baseline_model.py`)
- `--n INT` (default: 400): Number of test cases to run
- `--seed INT` (default: 42): Random seed for reproducible tests

### Statistical Options

- `--bootstrap-samples INT` (default: 500): Number of bootstrap samples for CI computation

### Adoption Criteria

- `--improve-delta FLOAT` (default: 0.0): Minimum improvement required for the CI lower bound
- `--min-pass-rate FLOAT` (default: 0.85): Minimum candidate pass rate (higher than ranking guard due to fairness requirements)

### Execution Options

- `--timeout-s FLOAT` (default: 2.0): Sandbox timeout per call (seconds)
- `--mem-mb INT` (default: 512): Sandbox memory limit (MB)
- `--parallel INT` (default: 1): Number of parallel workers

### Advanced Options

- `--report-dir PATH`: Directory for JSON evaluation reports (defaults to `reports/` in repository root)
- `--executor BACKEND`: Sandbox executor backend (e.g., `docker`)
- `--executor-config JSON`: JSON config passed to the sandbox executor

### Example: Custom Configuration

```bash
fairness-guard evaluate \
    --candidate implementations/candidate_fair.py \
    --n 1000 \
    --seed 123 \
    --improve-delta 0.01 \
    --min-pass-rate 0.90 \
    --parallel 4 \
    --timeout-s 5.0 \
    --mem-mb 1024 \
    --bootstrap-samples 1000
```

## Report Structure

Evaluation reports are saved as JSON files in the `reports/` directory. Each report contains:

### Core Fields

- `task`: Task name (`"credit_fairness"`)
- `baseline`: Baseline metrics (passes, total, pass_rate, violations, fairness_metrics)
- `candidate`: Candidate metrics (passes, total, pass_rate, violations, fairness_metrics)
- `decision`: Adoption decision (`adopt`, `reason`)
- `delta_pass_rate`: Difference in pass rates (candidate - baseline)
- `delta_ci`: 95% confidence interval for pass-rate delta `[lower, upper]`

### Fairness Metrics

Each implementation includes `fairness_metrics`:

- `overall_approval_rate`: Overall approval rate across all applicants
- `fairness_gap`: Maximum difference in approval rates between sensitive groups
- `group_approval_rates`: Approval rates by sensitive group (e.g., `{"A": 0.35, "B": 0.30}`)
- `applicants_evaluated`: Total number of applicants evaluated
- `datasets_evaluated`: Number of test datasets evaluated

### Configuration

- `config`: Evaluation configuration (timeout, memory, alpha, methods, etc.)
- `n`: Number of test cases
- `seed`: Random seed used

### Metadata

- `hashes`: SHA-256 hashes of baseline and candidate implementations
- `spec_fingerprint`: Fingerprints of task specification components
- `job_metadata`: Run metadata (run_id, timestamp, environment)
- `environment`: System environment information

### Sample Report

```json
{
  "task": "credit_fairness",
  "baseline": {
    "passes": 380,
    "total": 400,
    "pass_rate": 0.95,
    "prop_violations": [],
    "mr_violations": [],
    "fairness_metrics": {
      "overall_approval_rate": 0.32,
      "fairness_gap": 0.12,
      "group_approval_rates": {
        "A": 0.35,
        "B": 0.30
      },
      "applicants_evaluated": 17600,
      "datasets_evaluated": 400
    }
  },
  "candidate": {
    "passes": 395,
    "total": 400,
    "pass_rate": 0.9875,
    "prop_violations": [],
    "mr_violations": [],
    "fairness_metrics": {
      "overall_approval_rate": 0.33,
      "fairness_gap": 0.10,
      "group_approval_rates": {
        "A": 0.36,
        "B": 0.31
      },
      "applicants_evaluated": 17600,
      "datasets_evaluated": 400
    }
  },
  "decision": {
    "adopt": true,
    "reason": "meets_gate"
  },
  "delta_pass_rate": 0.0375,
  "delta_ci": [0.0150, 0.0600],
  "config": {
    "n": 400,
    "seed": 42,
    "timeout_s": 2.0,
    "mem_mb": 512,
    "alpha": 0.05,
    "min_delta": 0.0,
    "min_pass_rate": 0.85
  },
  "hashes": {
    "baseline": "1b92fe4bb6d8fdf45bb6152718146f86a8ee5ef91b7eaf0dc4447a2fb4ae607f",
    "candidate": "2c03ff5cc7e9gge56cc726382925g97b9ff0gc88fbf0ed5558b3gc5bf5bf718g"
  },
  "job_metadata": {
    "run_id": "run-2025-01-15-12345",
    "timestamp": "2025-01-15T12:00:00Z"
  }
}
```

## Programmatic Usage

You can also use Fairness Guard programmatically:

```python
from pathlib import Path
from fairness_guard.runner import evaluate_candidate

# Evaluate a candidate
outcome = evaluate_candidate(
    candidate_path=Path("implementations/candidate_fair.py"),
    test_cases=400,
    seed=42,
    min_delta=0.0,
    min_pass_rate=0.85,
)

# Check adoption decision
if outcome.adopted:
    print(f"✅ Candidate adopted: {outcome.reason}")
    print(f"   Δ Pass Rate: {outcome.delta_pass_rate:.4f}")
    print(f"   95% CI: [{outcome.ci_lower:.4f}, {outcome.ci_upper:.4f}]")
    print(f"   Baseline Fairness Gap: {outcome.baseline_metrics.fairness_gap:.2f}")
    print(f"   Candidate Fairness Gap: {outcome.candidate_metrics.fairness_gap:.2f}")
else:
    print(f"❌ Candidate rejected: {outcome.reason}")
    print(f"   Δ Pass Rate: {outcome.delta_pass_rate:.4f}")
    print(f"   95% CI: [{outcome.ci_lower:.4f}, {outcome.ci_upper:.4f}]")

# Access fairness metrics
print(f"Baseline Group Rates: {outcome.baseline_metrics.group_approval_rates}")
print(f"Candidate Group Rates: {outcome.candidate_metrics.group_approval_rates}")

# Access report
print(f"Report saved to: {outcome.report_path}")
```

## CI/CD Integration

### GitHub Actions

Create `.github/workflows/fairness-guard.yml`:

```yaml
name: Fairness Guard Evaluation

on:
  pull_request:
    paths:
      - 'implementations/candidate_*.py'
      - 'fairness_guard_project/**'
  workflow_dispatch:

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install --upgrade pip
          cd fairness_guard_project
          pip install -e .
      
      - name: Find candidate implementations
        id: candidates
        run: |
          cd fairness_guard_project
          echo "candidates=$(ls implementations/candidate_*.py | tr '\n' ' ')" >> $GITHUB_OUTPUT
      
      - name: Evaluate candidates
        run: |
          cd fairness_guard_project
          for candidate in ${{ steps.candidates.outputs.candidates }}; do
            echo "Evaluating $candidate..."
            fairness-guard evaluate --candidate "$candidate" --n 400 || exit 1
          done
      
      - name: Upload reports
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: fairness-guard-reports
          path: reports/*.json
      
      - name: Check fairness metrics
        run: |
          cd fairness_guard_project
          python -c "
          import json
          import glob
          for report_file in glob.glob('../reports/report_*.json'):
              with open(report_file) as f:
                  report = json.load(f)
              candidate_gap = report['candidate']['fairness_metrics']['fairness_gap']
              baseline_gap = report['baseline']['fairness_metrics']['fairness_gap']
              if candidate_gap > baseline_gap * 1.1:
                  print(f'⚠️  {report_file}: Candidate fairness gap ({candidate_gap:.2f}) exceeds baseline ({baseline_gap:.2f})')
                  exit(1)
          "
```

### GitLab CI

Create `.gitlab-ci.yml`:

```yaml
stages:
  - evaluate

fairness-guard:
  stage: evaluate
  image: python:3.11
  script:
    - pip install --upgrade pip
    - cd fairness_guard_project
    - pip install -e .
    - |
      for candidate in implementations/candidate_*.py; do
        fairness-guard evaluate --candidate "$candidate" --n 400 || exit 1
      done
  artifacts:
    paths:
      - reports/*.json
    expire_in: 1 week
```

### Jenkins

Create `Jenkinsfile`:

```groovy
pipeline {
    agent any
    
    stages {
        stage('Evaluate Candidates') {
            steps {
                sh '''
                    pip install --upgrade pip
                    cd fairness_guard_project
                    pip install -e .
                    for candidate in implementations/candidate_*.py; do
                        fairness-guard evaluate --candidate "$candidate" --n 400 || exit 1
                    done
                '''
            }
        }
    }
    
    post {
        always {
            archiveArtifacts artifacts: 'reports/*.json', fingerprint: true
        }
    }
}
```

## Understanding Results

### Adoption Decision

The adoption decision is based on:

1. **Pass Rate**: Candidate must meet minimum pass rate (`--min-pass-rate`, default 0.85)
2. **Improvement Delta**: CI lower bound must exceed improvement threshold (`--improve-delta`)
3. **No Regressions**: Candidate must not have significantly lower pass rate than baseline
4. **Fairness Compliance**: Candidate must respect fairness constraints (enforced via properties)

### Fairness Metrics

- **Overall Approval Rate**: Overall approval rate across all applicants
- **Fairness Gap**: Maximum difference in approval rates between sensitive groups
  - Lower is better (0.0 = perfect parity)
  - Should be within configured constraint
- **Group Approval Rates**: Approval rates by sensitive group
  - Used to compute fairness gap
  - Helps identify which groups are advantaged/disadvantaged

### Confidence Intervals

- **Delta CI**: Confidence interval for the difference in pass rates
  - If lower bound > 0: Candidate is better than baseline (with confidence)
  - If upper bound < 0: Candidate is worse than baseline (with confidence)
  - If CI contains 0: No statistically significant difference

### Violations

Reports include detailed violation information:

- `prop_violations`: Property violations including:
  - Output shape violations (incorrect structure)
  - Minimum approval rate violations
  - Fairness gap violations
- `mr_violations`: Metamorphic relation violations:
  - Shuffle invariance (order shouldn't matter)
  - Currency scale invariance (scaling shouldn't matter)
  - Feature invariance (uninformative features shouldn't matter)

## Best Practices

### 1. Use Higher Sample Sizes for Fairness

- **Development**: 200-400 test cases
- **Pre-production**: 400-1000 test cases
- **Production gates**: 1000+ test cases for high-stakes decisions

Fairness evaluation benefits from larger sample sizes to ensure statistical power across sensitive groups.

### 2. Set Appropriate Fairness Thresholds

- Review fairness gaps in baseline to set realistic expectations
- Consider regulatory requirements (e.g., 4/5ths rule, demographic parity)
- Monitor fairness gaps over time to detect drift

### 3. Monitor Group-Level Metrics

- Track approval rates by sensitive group
- Identify groups that are consistently advantaged/disadvantaged
- Use group-level metrics to inform model improvements

### 4. Enable Parallel Execution

- Use `--parallel 4` or higher for faster evaluation
- Balance parallelism with resource constraints

### 5. Store Reports for Compliance

- Commit reports to version control for audit trails
- Use consistent naming conventions (e.g., `report_<timestamp>.json`)
- Archive reports for regulatory compliance

## Troubleshooting

### Candidate Fails Fairness Check

1. **Check fairness gap**: Review `fairness_metrics.fairness_gap` in the report
2. **Review group rates**: Check `group_approval_rates` to identify disparities
3. **Verify constraints**: Ensure candidate respects fairness constraints in properties

### Low Statistical Power

1. **Increase sample size**: Use `--n 1000` or higher
2. **Check pass rates**: Ensure both baseline and candidate have high pass rates
3. **Review CI width**: Wide CIs indicate insufficient data

### Slow Evaluation

1. **Enable parallelism**: Use `--parallel 4` or higher
2. **Reduce sample size**: Use `--n 200` for development
3. **Optimize timeout**: Adjust `--timeout-s` based on actual execution time

## Regulatory Compliance

Fairness Guard reports can be used for regulatory compliance:

- **Model Cards**: Include fairness metrics in model documentation
- **Audit Trails**: Reports provide auditable evidence of fairness evaluation
- **Governance Dashboards**: Integrate reports into compliance dashboards
- **Regulatory Submissions**: Use reports as evidence of fairness testing

## See Also

- [Metamorphic Guard Documentation](https://github.com/duhboto/MetamorphicGuard)
- [Ranking Guard Project](../ranking_guard_project/README.md) - Similar workflow for ranking evaluation
- [First PR Gate Tutorial](../docs/first-pr-gate-tutorial.md) - Step-by-step walkthrough

## License

This project is part of the Metamorphic Guard repository and follows the same license.
