# Quick Start Guide

This guide will walk you through your first Metamorphic Guard evaluation from installation to generating your first report.

## Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- Basic familiarity with Python and command-line tools

## Step 1: Installation

Install Metamorphic Guard using pip:

```bash
pip install metamorphic-guard
```

For development or to use optional features:

```bash
# With LLM support
pip install metamorphic-guard[llm]

# With all optional dependencies
pip install metamorphic-guard[all]
```

Verify the installation:

```bash
metamorphic-guard --version
```

You should see the version number printed.

## Step 2: Initialize Your Project

The easiest way to get started is using the `init` command to scaffold a new project:

```bash
metamorphic-guard init --project-dir my-evaluation
```

This creates a project structure with:
- `metamorphic.toml` - Configuration file
- `baseline.py` - Baseline implementation
- `candidate.py` - Candidate implementation
- `README.md` - Project documentation
- `.github/workflows/` - CI/CD workflow template

Alternatively, use a template for a specific use case:

```bash
# For LLM evaluation
metamorphic-guard init --template llm --path llm-config.toml

# For sequential testing
metamorphic-guard init --template sequential --path seq-config.toml

# For distributed execution
metamorphic-guard init --template distributed --path dist-config.toml
```

## Step 3: Create Your Implementations

If you didn't use `--project-dir`, create your baseline and candidate implementations manually.

### Baseline Implementation

Create `baseline.py`:

```python
def solve(L, k):
    """Baseline implementation: simple sorting approach."""
    if not L or k <= 0:
        return []
    sorted_L = sorted(L, reverse=True)
    return sorted_L[:min(k, len(L))]
```

### Candidate Implementation

Create `candidate.py` with your improved version:

```python
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

Both implementations solve the "top-k" problem but use different algorithms.

## Step 4: Run Your First Evaluation

Run a basic evaluation:

```bash
metamorphic-guard evaluate \
  --task top_k \
  --baseline baseline.py \
  --candidate candidate.py \
  --n 100
```

### Using Configuration Files

If you created a config file with `init`, you can use it:

```bash
metamorphic-guard evaluate --config metamorphic.toml
```

### Using Presets

For common evaluation patterns, use presets:

```bash
# Minimal evaluation (fast, fewer samples)
metamorphic-guard evaluate \
  --task top_k \
  --baseline baseline.py \
  --candidate candidate.py \
  --preset minimal

# Standard evaluation (balanced)
metamorphic-guard evaluate \
  --task top_k \
  --baseline baseline.py \
  --candidate candidate.py \
  --preset standard

# Sequential testing (for CI/CD)
metamorphic-guard evaluate \
  --task top_k \
  --baseline baseline.py \
  --candidate candidate.py \
  --preset sequential
```

## Step 5: Understanding the Output

After running an evaluation, you'll see output like this:

### Accepted Candidate

```
Candidate     candidate.py
Adopt?        ✅ Yes
Reason        meets_gate
Δ Pass Rate   0.0125
Δ 95% CI      [0.0040, 0.0210]
CI Method     bootstrap
Power (target 0.80) 0.86
Suggested n   520
Policy        policy-v1
Report        reports/report_2025-01-15T12-00-00.json
```

**What this means:**
- **Adopt? ✅ Yes**: The candidate passed all gate checks
- **Δ Pass Rate**: The improvement in pass rate (1.25% better)
- **Δ 95% CI**: Confidence interval showing the improvement is statistically significant
- **Power**: Statistical power achieved (0.86 > target 0.80)
- **Report**: Location of the detailed JSON report

### Rejected Candidate

```
Candidate     candidate.py
Adopt?        ❌ No
Reason        Improvement insufficient: CI lower bound -0.0050 < 0.02
Δ Pass Rate   -0.0025
Δ 95% CI      [-0.0100, 0.0050]
Policy        policy-v1
Report        reports/report_2025-01-15T12-00-00.json
```

**What this means:**
- **Adopt? ❌ No**: The candidate did not meet the adoption criteria
- **Reason**: Specific reason for rejection (insufficient improvement)
- **Δ 95% CI**: The confidence interval includes negative values, meaning the candidate might be worse

## Step 6: Generate HTML Reports

Generate a visual HTML report:

```bash
metamorphic-guard evaluate \
  --task top_k \
  --baseline baseline.py \
  --candidate candidate.py \
  --n 100 \
  --html-report report.html
```

Or generate from an existing JSON report:

```bash
metamorphic-guard report reports/report_2025-01-15T12-00-00.json \
  --output report.html \
  --theme default
```

### Report Themes

Choose from different visual themes:

```bash
# Default theme (modern, colorful)
metamorphic-guard report report.json --theme default

# Dark theme (for dark mode users)
metamorphic-guard report report.json --theme dark

# Minimal theme (simple, clean)
metamorphic-guard report report.json --theme minimal
```

### Customizing Reports

```bash
# Custom title
metamorphic-guard report report.json --title "Q1 2025 Evaluation"

# Hide configuration section
metamorphic-guard report report.json --no-config

# Hide metadata section
metamorphic-guard report report.json --no-metadata
```

## Step 7: Using Policies

Policies define your adoption criteria. Use a policy template:

```bash
# Copy a policy template
cp templates/policies/moderate.toml policies/my-policy.toml

# Use the policy in evaluation
metamorphic-guard evaluate \
  --task top_k \
  --baseline baseline.py \
  --candidate candidate.py \
  --policy policies/my-policy.toml
```

Available policy templates:
- `strict.toml` - High-risk deployments (requires 5% improvement)
- `moderate.toml` - Balanced requirements (requires 2% improvement)
- `lenient.toml` - Low-risk changes (allows non-inferiority)
- `llm-focused.toml` - LLM evaluations (accounts for variability)

## Step 8: Viewing Results

### JSON Reports

JSON reports contain complete evaluation data:

```bash
# View report location
cat reports/report_2025-01-15T12-00-00.json | jq '.decision'
```

Key sections in JSON reports:
- `decision` - Adoption decision and reason
- `baseline` - Baseline metrics and violations
- `candidate` - Candidate metrics and violations
- `delta_pass_rate` - Improvement in pass rate
- `delta_ci` - Confidence interval for improvement
- `config` - Evaluation configuration
- `job_metadata` - Run metadata (timestamp, version, etc.)

### HTML Reports

Open the HTML report in your browser:

```bash
# On macOS
open report.html

# On Linux
xdg-open report.html

# On Windows
start report.html
```

The HTML report includes:
- Visual charts for pass rates and metrics
- Violation details
- Monitor summaries
- Configuration and metadata
- Policy information

## Step 9: Next Steps

### Learn More

- **[Task Specifications](concepts/task-specifications.md)**: Define custom tasks and properties
- **[LLM Evaluation](user-guide/llm-evaluation.md)**: Evaluate Large Language Models
- **[Configuration Guide](user-guide/configuration.md)**: Advanced configuration options
- **[Policies](user-guide/policies.md)**: Define adoption criteria

### Advanced Features

- **[Adaptive Sampling](user-guide/advanced-features.md#adaptive-sampling)**: Automatically adjust sample size
- **[Sequential Testing](user-guide/advanced-features.md#sequential-testing)**: Stop early when results are clear
- **[Distributed Execution](cookbook/distributed-deployment.md)**: Scale evaluations across workers
- **[Monitors](cookbook/monitors.md)**: Track fairness, latency, and resource usage

### Integration

- **[CI/CD Integration](cookbook/cicd-integration.md)**: Add to your pipeline
- **[GitHub Actions](examples/github-actions.md)**: Automated PR gates
- **[Reference Projects](../ranking_guard_project/README.md)**: Real-world examples

## Troubleshooting

### Common Issues

**Issue**: `ModuleNotFoundError: No module named 'metamorphic_guard'`
- **Solution**: Ensure Metamorphic Guard is installed: `pip install metamorphic-guard`

**Issue**: `Task 'top_k' not found`
- **Solution**: The `top_k` task is built-in. For custom tasks, see [Task Specifications](concepts/task-specifications.md)

**Issue**: Evaluation takes too long
- **Solution**: Reduce sample size with `--n 50` or use `--preset minimal`

**Issue**: Candidate always rejected
- **Solution**: Check your policy requirements with `--policy` or adjust `--min-delta`

### Getting Help

- Check the [API Reference](api/reference.md) for detailed documentation
- Review [Examples](examples/basic.md) for common patterns
- Open an issue on [GitHub](https://github.com/duhboto/MetamorphicGuard/issues)

## Summary

You've learned how to:
1. ✅ Install Metamorphic Guard
2. ✅ Initialize a project or create implementations manually
3. ✅ Run evaluations with CLI or config files
4. ✅ Understand evaluation results
5. ✅ Generate and customize HTML reports
6. ✅ Use policies to define adoption criteria
7. ✅ View and interpret results

Ready to dive deeper? Check out the [User Guide](user-guide/basic-usage.md) for advanced features and patterns.
