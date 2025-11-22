# Comprehensive Metamorphic Guard Tutorial

This tutorial walks you through using Metamorphic Guard to evaluate a recommendation system, demonstrating the full feature set.

## Table of Contents

1. [Setup](#setup)
2. [Understanding the Task](#understanding-the-task)
3. [Basic Evaluation](#basic-evaluation)
4. [Advanced Features](#advanced-features)
5. [LLM Evaluation](#llm-evaluation)
6. [Distributed Execution](#distributed-execution)
7. [Observability](#observability)
8. [CI/CD Integration](#cicd-integration)

## Setup

### Install Dependencies

```bash
# Install Metamorphic Guard with all features
pip install metamorphic-guard[all]

# Verify installation
metamorphic-guard --version
```

### Project Structure

The demo project includes:
- **Implementations**: Baseline and candidate recommendation systems
- **Task Specification**: Defines properties and metamorphic relations
- **Configurations**: Various evaluation configurations
- **Scripts**: Helper scripts for running evaluations

## Understanding the Task

### The Recommendation Problem

Our task is to evaluate a **product recommendation system** that:
- Takes user preferences (dict) and product catalog (list) as input
- Returns a ranked list of recommended product IDs
- Must satisfy quality, diversity, and fairness requirements

### Task Specification

The task specification (`src/comprehensive_demo/task_spec.py`) defines:

1. **Input Generation**: Creates test cases with users and products
2. **Properties**: Hard and soft invariants
3. **Metamorphic Relations**: Transformation-based tests
4. **Equivalence**: How to compare outputs

### Properties

**Hard Properties** (must always pass):
- Output is a list
- All IDs are valid (exist in catalog)
- No duplicates
- List length matches requested count

**Soft Properties** (tolerance allowed):
- Diversity score > 0.5
- Relevance score > 0.7
- Response time < 100ms

### Metamorphic Relations

1. **Permutation**: Shuffling user preferences → same results
2. **Monotonicity**: Increasing preference score → better ranking
3. **Fairness**: Equal treatment across user groups
4. **Idempotence**: Running twice → same output

## Basic Evaluation

### Step 1: Run Basic Evaluation

```bash
metamorphic-guard evaluate \
  --config configs/basic.toml \
  --html-report reports/basic_report.html
```

### Step 2: Interpret Results

The CLI output shows:
```
Candidate     implementations/candidate_improved.py
Adopt?        ✅ Yes
Reason        meets_gate
Δ Pass Rate   0.0450
Δ 95% CI      [0.0320, 0.0580]
```

**Key Metrics:**
- **Δ Pass Rate**: Improvement in pass rate (4.5%)
- **Δ 95% CI**: Confidence interval (statistically significant)
- **Power**: Statistical power achieved
- **Report**: Location of detailed JSON report

### Step 3: View HTML Report

```bash
open reports/basic_report.html
```

The HTML report includes:
- Visual charts for pass rates
- Violation details
- Monitor summaries
- Configuration and metadata

### Step 4: Examine Violations

If a candidate fails, check the violations:

```bash
# View violations in JSON report
cat reports/report_*.json | jq '.candidate.prop_violations'

# Or use the CLI
metamorphic-guard debug inspect-violation reports/report_*.json --violation-id 0
```

## Advanced Features

### Monitors

Monitors track higher-order statistical invariants:

```bash
metamorphic-guard evaluate \
  --config configs/basic.toml \
  --monitor latency \
  --monitor fairness \
  --monitor resource:metric=cpu_ms,alert_ratio=1.3
```

**Available Monitors:**
- `latency`: Response time distributions
- `fairness`: Group disparity tracking
- `resource`: CPU/memory usage
- `llm_cost`: LLM API costs (for LLM evaluations)

### Policies

Policies define adoption criteria:

```bash
# Use a policy file
metamorphic-guard evaluate \
  --config configs/basic.toml \
  --policy configs/policy-strict.toml

# Or use inline preset
metamorphic-guard evaluate \
  --config configs/basic.toml \
  --policy "superiority:margin=0.05"
```

**Policy Options:**
- `strict`: High bar (5% improvement required)
- `moderate`: Balanced (2% improvement)
- `lenient`: Non-inferiority (no regression)

### Adaptive Sampling

Automatically adjust sample size based on results:

```bash
metamorphic-guard evaluate \
  --config configs/basic.toml \
  --adaptive-sampling \
  --min-n 100 \
  --max-n 1000
```

### Sequential Testing

Stop early when results are clear:

```bash
metamorphic-guard evaluate \
  --config configs/basic.toml \
  --sequential-testing \
  --alpha 0.05 \
  --power 0.80
```

### Multi-Objective Optimization

Compare candidates across multiple objectives:

```python
from metamorphic_guard import run, TaskSpec, Implementation
from metamorphic_guard.multi_objective import analyze_trade_offs

# Run evaluation
result = run(
    task=task_spec,
    baseline=Implementation(path="implementations/baseline_recommender.py"),
    candidate=Implementation(path="implementations/candidate_improved.py"),
    config=EvaluationConfig(n=500),
)

# Analyze trade-offs
trade_offs = analyze_trade_offs(
    candidates=[result],
    objectives=["pass_rate", "latency", "cost"],
)
```

## LLM Evaluation

### Step 1: Set API Keys

```bash
export OPENAI_API_KEY="your-key-here"
export ANTHROPIC_API_KEY="your-key-here"
```

### Step 2: Estimate Costs

Before running, estimate costs:

```python
from metamorphic_guard.cost_estimation import estimate_llm_cost

cost = estimate_llm_cost(
    task=task_spec,
    n=1000,
    executor="openai",
    model="gpt-4",
)
print(f"Estimated cost: ${cost:.2f}")
```

### Step 3: Run LLM Evaluation

```bash
metamorphic-guard evaluate \
  --config configs/llm.toml \
  --html-report reports/llm_report.html
```

### Step 4: Review LLM Metrics

The report includes:
- **Cost**: Total API cost
- **Tokens**: Input/output token counts
- **Latency**: Response times
- **Retries**: Failed request retries

### LLM-as-Judge

Use an LLM to judge output quality:

```python
from metamorphic_guard.judges.llm_as_judge import LLMAsJudge

judge = LLMAsJudge(
    model="gpt-4",
    prompt_template="Rate this recommendation on a scale of 1-10: {output}",
)
```

## Distributed Execution

### Step 1: Start Redis

```bash
# Using Docker
docker run -d -p 6379:6379 redis:7-alpine

# Or use the setup script
./scripts/setup_redis.sh
```

### Step 2: Start Workers

In separate terminals:

```bash
# Terminal 1: Worker 1
metamorphic-guard-worker \
  --backend redis \
  --queue-config '{"url":"redis://localhost:6379/0"}'

# Terminal 2: Worker 2
metamorphic-guard-worker \
  --backend redis \
  --queue-config '{"url":"redis://localhost:6379/0"}'
```

### Step 3: Run Distributed Evaluation

```bash
metamorphic-guard evaluate \
  --config configs/distributed.toml \
  --html-report reports/distributed_report.html
```

### Step 4: Monitor Progress

Workers stream progress updates. You can also check:
- Queue length
- Worker status
- Throughput metrics

## Observability

### Prometheus Metrics

Enable Prometheus metrics:

```bash
metamorphic-guard evaluate \
  --config configs/basic.toml \
  --metrics \
  --metrics-port 9090
```

Access metrics at `http://localhost:9090/metrics`

### OpenTelemetry Tracing

Export traces to OpenTelemetry:

```bash
metamorphic-guard evaluate \
  --config configs/basic.toml \
  --otlp-endpoint http://localhost:4317
```

### Structured Logging

Enable JSON logging:

```bash
export METAMORPHIC_GUARD_LOG_JSON=1
metamorphic-guard evaluate --config configs/basic.toml
```

Or use CLI flag:

```bash
metamorphic-guard evaluate \
  --config configs/basic.toml \
  --log-json \
  --log-file logs/evaluation.jsonl
```

### HTML Reports

Generate interactive HTML reports:

```bash
# During evaluation
metamorphic-guard evaluate \
  --config configs/basic.toml \
  --html-report reports/report.html

# From existing JSON report
metamorphic-guard report reports/report_*.json \
  --output reports/report.html \
  --theme default
```

## CI/CD Integration

### GitHub Actions

Create `.github/workflows/metamorphic-guard.yml`:

```yaml
name: Metamorphic Guard Evaluation

on:
  pull_request:
    branches: [main]

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install metamorphic-guard[all]
      - run: |
          metamorphic-guard evaluate \
            --config comprehensive_demo_project/configs/basic.toml \
            --junit-report test-results.xml \
            --html-report report.html
      - uses: actions/upload-artifact@v4
        with:
          name: evaluation-report
          path: report.html
```

### GitLab CI

Create `.gitlab-ci.yml`:

```yaml
metamorphic-guard:
  image: python:3.11
  script:
    - pip install metamorphic-guard[all]
    - metamorphic-guard evaluate --config configs/basic.toml --junit-report junit.xml
  artifacts:
    reports:
      junit: junit.xml
```

## Next Steps

1. **Customize**: Modify the task specification for your use case
2. **Extend**: Add custom monitors, relations, or judges
3. **Scale**: Set up distributed execution for large evaluations
4. **Monitor**: Integrate Prometheus/Grafana for production monitoring

## Troubleshooting

### Common Issues

**Issue**: `ModuleNotFoundError: No module named 'metamorphic_guard'`
- **Solution**: Install with `pip install metamorphic-guard[all]`

**Issue**: Evaluation takes too long
- **Solution**: Reduce `n` or use `--preset minimal`

**Issue**: Candidate always rejected
- **Solution**: Check policy requirements or adjust `--min-delta`

**Issue**: LLM evaluation fails
- **Solution**: Verify API keys and check rate limits

### Getting Help

- **Documentation**: [docs/](../../docs/)
- **Issues**: https://github.com/duhboto/MetamorphicGuard/issues
- **Discussions**: https://github.com/duhboto/MetamorphicGuard/discussions







