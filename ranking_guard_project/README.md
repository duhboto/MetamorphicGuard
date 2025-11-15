# Ranking Guard Project

A production-ready workflow for qualifying new ranking algorithms before rolling them into production. This project demonstrates how to use Metamorphic Guard to compare baseline and candidate implementations of a `top_k` style ranker and make data-driven adoption decisions.

## Overview

Ranking Guard provides a realistic example of how search teams can integrate Metamorphic Guard into their release process. It evaluates candidate ranking algorithms against a production baseline using:

1. **Property-based checks**: Verifies results have correct length, ordering, and elements
2. **Metamorphic relations**: Ensures permuting inputs or adding low-value noise doesn't change outputs
3. **Statistical analysis**: Computes bootstrap confidence intervals on pass-rate differences
4. **Adoption gating**: Makes data-driven decisions about whether to adopt candidates

## Scenario

A search team maintains a baseline ranking implementation. Engineers submit new algorithms that must:

- Pass all property-based checks (results have correct length, ordering, and elements)
- Respect metamorphic relations (permuting inputs or adding low-value noise does not change outputs)
- Achieve at least the baseline pass rate with a non-negative improvement delta

## Project Structure

```
ranking_guard_project/
├── implementations/
│   ├── baseline_ranker.py      # Current production algorithm
│   ├── candidate_heap.py       # Efficient heap implementation (expected to pass)
│   └── candidate_buggy.py     # Regression that should be rejected
├── src/ranking_guard/
│   ├── __init__.py
│   ├── cli.py                  # CLI entry point
│   └── runner.py               # Library utilities
├── pyproject.toml
└── README.md
```

## Installation

### Prerequisites

- Python 3.10 or higher
- pip

### Install from Source

```bash
cd ranking_guard_project
pip install -e .
```

This installs:
- `metamorphic-guard` (core library)
- `click` (CLI framework)
- `rich` (terminal formatting)
- The `ranking-guard` CLI command

## Quick Start

### Basic Evaluation

Evaluate a candidate implementation:

```bash
ranking-guard evaluate --candidate implementations/candidate_heap.py
```

### Compare Multiple Candidates

Run both candidates to see adoption vs rejection decisions:

```bash
# This should pass (heap implementation matches baseline)
ranking-guard evaluate --candidate implementations/candidate_heap.py

# This should fail (buggy implementation has regressions)
ranking-guard evaluate --candidate implementations/candidate_buggy.py
```

### Example Output

**Accepted Candidate:**
```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                              Ranking Guard Result                                ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Field           Value                                                            ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Candidate       implementations/candidate_heap.py                                 ┃
┃ Adopt?          ✅ Yes                                                           ┃
┃ Reason          meets_gate                                                       ┃
┃ Δ Pass Rate     0.0125                                                          ┃
┃ Δ 95% CI        [0.0040, 0.0210]                                                ┃
┃ Relative Risk   1.0125                                                           ┃
┃ RR 95% CI       [1.0040, 1.0210]                                                ┃
┃ Report          reports/report_2025-01-15T12-00-00.json                        ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

**Rejected Candidate:**
```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                              Ranking Guard Result                                ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Field           Value                                                            ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Candidate       implementations/candidate_buggy.py                              ┃
┃ Adopt?          ❌ No                                                            ┃
┃ Reason          Improvement insufficient: CI lower bound -0.0050 < 0.02          ┃
┃ Δ Pass Rate     -0.0025                                                          ┃
┃ Δ 95% CI        [-0.0100, 0.0050]                                               ┃
┃ Relative Risk   0.9975                                                           ┃
┃ RR 95% CI       [0.9900, 1.0050]                                                 ┃
┃ Report          reports/report_2025-01-15T12-00-05.json                         ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

## CLI Options

### Core Options

- `--candidate PATH` (required): Path to the candidate ranking implementation
- `--baseline PATH` (optional): Path to baseline implementation (defaults to bundled `baseline_ranker.py`)
- `--n INT` (default: 400): Number of test cases to run
- `--seed INT` (default: 42): Random seed for reproducible tests

### Statistical Options

- `--ci-method METHOD` (default: `bootstrap`): Method for pass-rate delta confidence intervals
  - `bootstrap`: Bootstrap resampling (recommended for most cases)
  - `newcombe`: Newcombe's method for two-proportion intervals
  - `wilson`: Wilson score interval
- `--rr-ci-method METHOD` (default: `log`): Method for relative risk confidence intervals
  - `log`: Log-normal approximation (recommended)

### Adoption Criteria

- `--improve-delta FLOAT` (default: 0.0): Minimum improvement required for the CI lower bound
- `--min-pass-rate FLOAT` (default: 0.8): Minimum candidate pass rate

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
ranking-guard evaluate \
    --candidate implementations/candidate_heap.py \
    --n 1000 \
    --seed 123 \
    --ci-method bootstrap \
    --improve-delta 0.01 \
    --min-pass-rate 0.85 \
    --parallel 4 \
    --timeout-s 5.0 \
    --mem-mb 1024
```

## Report Structure

Evaluation reports are saved as JSON files in the `reports/` directory. Each report contains:

### Core Fields

- `task`: Task name (`"top_k"`)
- `baseline`: Baseline metrics (passes, total, pass_rate, violations)
- `candidate`: Candidate metrics (passes, total, pass_rate, violations)
- `decision`: Adoption decision (`adopt`, `reason`)
- `delta_pass_rate`: Difference in pass rates (candidate - baseline)
- `delta_ci`: 95% confidence interval for pass-rate delta `[lower, upper]`
- `relative_risk`: Ratio of candidate pass rate to baseline pass rate
- `relative_risk_ci`: 95% confidence interval for relative risk `[lower, upper]`

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
  "task": "top_k",
  "baseline": {
    "passes": 400,
    "total": 400,
    "pass_rate": 1.0,
    "prop_violations": [],
    "mr_violations": []
  },
  "candidate": {
    "passes": 405,
    "total": 400,
    "pass_rate": 1.0125,
    "prop_violations": [],
    "mr_violations": []
  },
  "decision": {
    "adopt": true,
    "reason": "meets_gate"
  },
  "delta_pass_rate": 0.0125,
  "delta_ci": [0.0040, 0.0210],
  "relative_risk": 1.0125,
  "relative_risk_ci": [1.0040, 1.0210],
  "config": {
    "n": 400,
    "seed": 42,
    "timeout_s": 2.0,
    "mem_mb": 512,
    "alpha": 0.05,
    "ci_method": "bootstrap",
    "rr_ci_method": "log",
    "min_delta": 0.0,
    "min_pass_rate": 0.8
  },
  "hashes": {
    "baseline": "2a92fe4bb6d8fdf45bb6152718146f86a8ee5ef91b7eaf0dc4447a2fb4ae607f",
    "candidate": "3b03ff5cc7e9gge56cc726382925g97b9ff0gc88fbf0ed5558b3gc5bf5bf718g"
  },
  "job_metadata": {
    "run_id": "run-2025-01-15-12345",
    "timestamp": "2025-01-15T12:00:00Z"
  }
}
```

## Programmatic Usage

You can also use Ranking Guard programmatically:

```python
from pathlib import Path
from ranking_guard.runner import evaluate_candidate

# Evaluate a candidate
outcome = evaluate_candidate(
    candidate_path=Path("implementations/candidate_heap.py"),
    test_cases=400,
    seed=42,
    min_delta=0.0,
    min_pass_rate=0.8,
    ci_method="bootstrap",
    rr_ci_method="log",
)

# Check adoption decision
if outcome.adopted:
    print(f"✅ Candidate adopted: {outcome.reason}")
    print(f"   Δ Pass Rate: {outcome.delta_pass_rate:.4f}")
    print(f"   95% CI: [{outcome.ci_lower:.4f}, {outcome.ci_upper:.4f}]")
else:
    print(f"❌ Candidate rejected: {outcome.reason}")
    print(f"   Δ Pass Rate: {outcome.delta_pass_rate:.4f}")
    print(f"   95% CI: [{outcome.ci_lower:.4f}, {outcome.ci_upper:.4f}]")

# Access report
print(f"Report saved to: {outcome.report_path}")
```

## CI/CD Integration

### GitHub Actions

Create `.github/workflows/ranking-guard.yml`:

```yaml
name: Ranking Guard Evaluation

on:
  pull_request:
    paths:
      - 'implementations/candidate_*.py'
      - 'ranking_guard_project/**'
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
          cd ranking_guard_project
          pip install -e .
      
      - name: Find candidate implementations
        id: candidates
        run: |
          cd ranking_guard_project
          echo "candidates=$(ls implementations/candidate_*.py | tr '\n' ' ')" >> $GITHUB_OUTPUT
      
      - name: Evaluate candidates
        run: |
          cd ranking_guard_project
          for candidate in ${{ steps.candidates.outputs.candidates }}; do
            echo "Evaluating $candidate..."
            ranking-guard evaluate --candidate "$candidate" --n 400 || exit 1
          done
      
      - name: Upload reports
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: ranking-guard-reports
          path: reports/*.json
```

### GitLab CI

Create `.gitlab-ci.yml`:

```yaml
stages:
  - evaluate

ranking-guard:
  stage: evaluate
  image: python:3.11
  script:
    - pip install --upgrade pip
    - cd ranking_guard_project
    - pip install -e .
    - |
      for candidate in implementations/candidate_*.py; do
        ranking-guard evaluate --candidate "$candidate" --n 400 || exit 1
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
                    cd ranking_guard_project
                    pip install -e .
                    for candidate in implementations/candidate_*.py; do
                        ranking-guard evaluate --candidate "$candidate" --n 400 || exit 1
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

1. **Pass Rate**: Candidate must meet minimum pass rate (`--min-pass-rate`)
2. **Improvement Delta**: CI lower bound must exceed improvement threshold (`--improve-delta`)
3. **No Regressions**: Candidate must not have significantly lower pass rate than baseline

### Confidence Intervals

- **Delta CI**: Confidence interval for the difference in pass rates
  - If lower bound > 0: Candidate is better than baseline (with confidence)
  - If upper bound < 0: Candidate is worse than baseline (with confidence)
  - If CI contains 0: No statistically significant difference

- **Relative Risk CI**: Confidence interval for the ratio of pass rates
  - If lower bound > 1: Candidate is better than baseline
  - If upper bound < 1: Candidate is worse than baseline
  - If CI contains 1: No statistically significant difference

### Violations

Reports include detailed violation information:

- `prop_violations`: Property violations (test case, property, input, output, error)
- `mr_violations`: Metamorphic relation violations (test case, relation, input, output, relation_output, error)

## Best Practices

### 1. Use Appropriate Sample Sizes

- **Development**: 100-200 test cases for quick feedback
- **Pre-production**: 400-1000 test cases for statistical confidence
- **Production gates**: 1000+ test cases for high-stakes decisions

### 2. Set Realistic Improvement Thresholds

- Start with `--improve-delta 0.0` to detect regressions
- Increase to `--improve-delta 0.01` or higher for meaningful improvements
- Consider business impact when setting thresholds

### 3. Use Bootstrap CI for Most Cases

- `bootstrap`: Recommended for most use cases (robust, handles non-normal distributions)
- `newcombe`: Good for two-proportion comparisons
- `wilson`: Alternative for proportion intervals

### 4. Enable Parallel Execution

- Use `--parallel 4` or higher for faster evaluation
- Balance parallelism with resource constraints

### 5. Store Reports for Auditing

- Commit reports to version control for audit trails
- Use consistent naming conventions (e.g., `report_<timestamp>.json`)
- Archive reports for compliance and historical analysis

## Troubleshooting

### Candidate Fails Evaluation

1. **Check violations**: Review `prop_violations` and `mr_violations` in the report
2. **Verify implementation**: Ensure candidate matches baseline semantics
3. **Review test cases**: Check if violations are edge cases or systematic issues

### Low Statistical Power

1. **Increase sample size**: Use `--n 1000` or higher
2. **Check pass rates**: Ensure both baseline and candidate have high pass rates
3. **Review CI width**: Wide CIs indicate insufficient data

### Slow Evaluation

1. **Enable parallelism**: Use `--parallel 4` or higher
2. **Reduce sample size**: Use `--n 200` for development
3. **Optimize timeout**: Adjust `--timeout-s` based on actual execution time

## See Also

- [Metamorphic Guard Documentation](https://github.com/duhboto/MetamorphicGuard)
- [Fairness Guard Project](../fairness_guard_project/README.md) - Similar workflow for fairness evaluation
- [First PR Gate Tutorial](../docs/first-pr-gate-tutorial.md) - Step-by-step walkthrough

## License

This project is part of the Metamorphic Guard repository and follows the same license.
