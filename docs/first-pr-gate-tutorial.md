# First PR Gate Tutorial: End-to-End Guide

This tutorial walks you through setting up Metamorphic Guard as a CI gate for your first pull request. You'll learn how to:

1. Fork/clone a repository
2. Create baseline and candidate implementations
3. Run Metamorphic Guard evaluation
4. Generate HTML reports
5. Set up GitHub Actions badge

## Prerequisites

- Python 3.10+
- Git
- GitHub account
- Basic understanding of Python

## Step 1: Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
```

## Step 2: Install Metamorphic Guard

```bash
pip install metamorphic-guard
```

Or for one-off usage:

```bash
pipx run metamorphic-guard --help
```

## Step 3: Create Baseline Implementation

Create a baseline implementation file:

```python
# baseline.py
def solve(L, k):
    """Baseline implementation: simple sorting approach."""
    if not L or k <= 0:
        return []
    sorted_L = sorted(L, reverse=True)
    return sorted_L[:min(k, len(L))]
```

## Step 4: Create Candidate Implementation

Create your improved candidate:

```python
# candidate.py
def solve(L, k):
    """Improved candidate: optimized for large inputs."""
    if not L or k <= 0:
        return []
    if k >= len(L):
        return sorted(L, reverse=True)
    # Use heap for better performance on large inputs
    import heapq
    return sorted(heapq.nlargest(k, L), reverse=True)
```

## Step 5: Run Initial Evaluation

Test your candidate locally:

```bash
metamorphic-guard evaluate \
  --task top_k \
  --baseline baseline.py \
  --candidate candidate.py \
  --n 100 \
  --html-report report.html
```

Check the output:

```
DECISION:
  Adopt: ✅ Yes
  Reason: meets_gate
  Δ Pass Rate: 0.0125
  Δ 95% CI: [0.0040, 0.0210]
  
Report saved to: reports/report_20250110_120000.json
HTML report written to: report.html
```

## Step 6: Create GitHub Actions Workflow

Create `.github/workflows/metamorphic-guard.yml`:

```yaml
name: Metamorphic Guard Gate

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install Metamorphic Guard
        run: pip install metamorphic-guard
      
      - name: Run Evaluation
        run: |
          metamorphic-guard evaluate \
            --task top_k \
            --baseline baseline.py \
            --candidate candidate.py \
            --n 200 \
            --html-report report.html \
            --junit-xml test-results.xml
      
      - name: Upload HTML Report
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: metamorphic-report
          path: report.html
      
      - name: Publish Test Results
        uses: EnricoMi/publish-unit-test-result-action@v2
        if: always()
        with:
          files: test-results.xml
      
      - name: Check Adoption Decision
        run: |
          # Extract decision from JSON report
          DECISION=$(python -c "
          import json, glob
          reports = glob.glob('reports/report_*.json')
          if reports:
              with open(max(reports), 'r') as f:
                  data = json.load(f)
                  print('adopt' if data.get('decision', {}).get('adopt', False) else 'reject')
          ")
          if [ "$DECISION" != "adopt" ]; then
            echo "❌ Candidate rejected by Metamorphic Guard"
            exit 1
          fi
          echo "✅ Candidate approved by Metamorphic Guard"
```

## Step 7: Add Status Badge

Add a status badge to your README.md:

```markdown
[![Metamorphic Guard](https://github.com/YOUR_USERNAME/YOUR_REPO/actions/workflows/metamorphic-guard.yml/badge.svg)](https://github.com/YOUR_USERNAME/YOUR_REPO/actions/workflows/metamorphic-guard.yml)
```

## Step 8: Create Pull Request

```bash
# Create a feature branch
git checkout -b feature/improved-algorithm

# Add your candidate
git add candidate.py
git commit -m "feat: improve algorithm performance"

# Push and create PR
git push origin feature/improved-algorithm
```

## Step 9: Review Results

1. **GitHub Actions**: Check the workflow run in the Actions tab
2. **Artifacts**: Download the HTML report from the workflow artifacts
3. **Test Results**: View JUnit XML results in the workflow summary
4. **Decision**: The workflow will fail if the candidate is rejected

## Step 10: Interpret Results

### HTML Report

Open `report.html` to see:
- Pass rate comparison (baseline vs candidate)
- Confidence intervals
- Violations (if any)
- Monitor results (latency, fairness, etc.)

### JSON Report

The JSON report (`reports/report_*.json`) contains:
- Statistical metrics
- Decision and reasoning
- Full violation details
- Monitor summaries

### Key Metrics

- **Δ Pass Rate**: Difference in pass rates (candidate - baseline)
- **Δ 95% CI**: Confidence interval for the difference
- **Adopt**: Boolean indicating if candidate should be adopted
- **Reason**: Explanation of the decision

## Advanced: Custom Task Specification

For custom tasks, create a task specification:

```python
# my_task_spec.py
from metamorphic_guard import task, Spec, Property, MetamorphicRelation
from metamorphic_guard.generators import gen_top_k_inputs
from metamorphic_guard.relations import permute_input
from metamorphic_guard.stability import multiset_equal

@task("my_custom_task")
def my_task_spec() -> Spec:
    return Spec(
        gen_inputs=gen_top_k_inputs,
        properties=[
            Property(
                check=lambda out, L, k: len(out) == min(k, len(L)),
                description="Output length equals min(k, len(L))"
            ),
        ],
        relations=[
            MetamorphicRelation(
                name="permute_input",
                transform=permute_input,
                expect="equal",
                accepts_rng=True,
            ),
        ],
        equivalence=multiset_equal,
    )
```

Then use it:

```bash
metamorphic-guard evaluate \
  --task my_custom_task \
  --baseline baseline.py \
  --candidate candidate.py
```

## Troubleshooting

### Test Failures

If tests fail:
1. Check violation details in the HTML report
2. Review property/MR violations
3. Fix implementation issues
4. Re-run evaluation

### CI Failures

If CI fails:
1. Check GitHub Actions logs
2. Verify file paths are correct
3. Ensure task specification is registered
4. Check Python version compatibility

### Performance Issues

For slow evaluations:
- Reduce `--n` (number of test cases)
- Use `--parallel` for multi-core execution
- Enable `--dispatcher queue` for distributed runs

## Next Steps

- Explore [LLM evaluation features](../docs/llm-usage-example.md)
- Set up [distributed execution](../docs/cookbook.md#distributed-execution)
- Configure [monitors and alerts](../README.md#monitors--alerts)
- Create [custom plugins](../README.md#plugin-system)

## Resources

- [Full Documentation](../README.md)
- [Cookbook Guide](../docs/cookbook.md)
- [LLM Usage Examples](../docs/llm-usage-example.md)
- [API Reference](../README.md#python-api)

