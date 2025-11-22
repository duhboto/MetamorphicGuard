# Comprehensive Metamorphic Guard Demo

This project demonstrates the **complete feature set** of Metamorphic Guard through a realistic use case: evaluating a **recommendation system** that suggests products to users based on their preferences.

## What This Demo Shows

This comprehensive tutorial showcases:

1. **Core Features**
   - Property testing with hard/soft invariants
   - Metamorphic relations (permutation, monotonicity, fairness)
   - Statistical analysis with bootstrap confidence intervals
   - Adoption gating with policies

2. **Advanced Features**
   - Monitors (latency, fairness, resource usage)
   - Cost estimation for LLM evaluations
   - Multi-objective optimization
   - Adaptive sampling

3. **LLM Integration**
   - Using LLM executors (OpenAI, Anthropic)
   - LLM-as-judge for quality assessment
   - Cost tracking and budget controls

4. **Distributed Execution**
   - Queue-based execution with Redis
   - Worker scaling
   - Progress tracking

5. **Observability**
   - Prometheus metrics
   - OpenTelemetry tracing
   - Structured logging
   - HTML reports with visualizations

6. **Enterprise Features**
   - Policy as code
   - Compliance checks
   - Audit trails

## Project Structure

```
comprehensive_demo_project/
├── README.md                    # This file
├── TUTORIAL.md                  # Step-by-step tutorial
├── implementations/
│   ├── baseline_recommender.py  # Baseline recommendation system
│   ├── candidate_improved.py    # Improved candidate (should pass)
│   ├── candidate_regression.py  # Regression candidate (should fail)
│   └── candidate_llm.py         # LLM-based candidate
├── src/comprehensive_demo/
│   ├── __init__.py
│   ├── task_spec.py             # Task specification
│   ├── properties.py            # Property definitions
│   ├── relations.py             # Metamorphic relations
│   └── monitors.py              # Custom monitors
├── configs/
│   ├── basic.toml              # Basic configuration
│   ├── llm.toml                 # LLM evaluation config
│   ├── distributed.toml         # Distributed execution config
│   └── policy-strict.toml       # Strict policy
├── scripts/
│   ├── run_basic.sh             # Basic evaluation script
│   ├── run_llm.sh               # LLM evaluation script
│   ├── run_distributed.sh       # Distributed evaluation script
│   └── setup_redis.sh           # Redis setup helper
└── reports/                     # Generated reports (gitignored)
```

## Quick Start

### Prerequisites

```bash
# Install Metamorphic Guard with all optional dependencies
pip install metamorphic-guard[all]

# Or install specific extras
pip install metamorphic-guard[llm,queue,otel]
```

### Basic Evaluation

```bash
# Run a basic evaluation
metamorphic-guard evaluate \
  --config configs/basic.toml \
  --html-report reports/basic_report.html

# View the report
open reports/basic_report.html
```

### LLM Evaluation

```bash
# Set your API keys
export OPENAI_API_KEY="your-key-here"
export ANTHROPIC_API_KEY="your-key-here"

# Run LLM evaluation with cost estimation
metamorphic-guard evaluate \
  --config configs/llm.toml \
  --html-report reports/llm_report.html
```

### Distributed Execution

```bash
# Start Redis (if not running)
./scripts/setup_redis.sh

# Run distributed evaluation
metamorphic-guard evaluate \
  --config configs/distributed.toml \
  --html-report reports/distributed_report.html

# In another terminal, start workers
metamorphic-guard-worker \
  --backend redis \
  --queue-config '{"url":"redis://localhost:6379/0"}'
```

## Use Case: Recommendation System

Our demo evaluates a **product recommendation system** that:
- Takes user preferences and product catalog as input
- Returns ranked list of recommended products
- Must satisfy properties (diversity, relevance, fairness)
- Must respect metamorphic relations (permutation, monotonicity)

### Baseline Implementation
- Simple collaborative filtering approach
- Basic ranking algorithm
- No fairness considerations

### Candidate Implementations
1. **Improved**: Enhanced algorithm with better diversity
2. **Regression**: Buggy version that violates fairness
3. **LLM-based**: Uses LLM to generate recommendations

## Tutorial

See [TUTORIAL.md](TUTORIAL.md) for a complete step-by-step walkthrough covering:
- Setting up the project
- Understanding task specifications
- Running evaluations
- Interpreting results
- Using advanced features
- Integrating into CI/CD

## Features Demonstrated

### 1. Property Testing
- **Hard Properties**: Output format, list length, valid IDs
- **Soft Properties**: Diversity score, relevance threshold

### 2. Metamorphic Relations
- **Permutation**: Shuffling user preferences → same results
- **Monotonicity**: Increasing preference score → better ranking
- **Fairness**: Equal treatment across user groups
- **Idempotence**: Running twice → same output

### 3. Statistical Analysis
- Bootstrap confidence intervals
- Power analysis
- Sequential testing
- Paired analysis (McNemar test)

### 4. Monitors
- **Latency Monitor**: Track response times
- **Fairness Monitor**: Monitor group disparities
- **Resource Monitor**: Track CPU/memory usage
- **Cost Monitor**: Track LLM API costs

### 5. Policies
- **Strict**: High bar for adoption (5% improvement)
- **Moderate**: Balanced requirements (2% improvement)
- **Lenient**: Non-inferiority (no regression)

### 6. Observability
- Prometheus metrics endpoint
- OpenTelemetry traces
- Structured JSON logging
- HTML reports with charts

## Example Output

### Accepted Candidate
```
Candidate     implementations/candidate_improved.py
Adopt?        ✅ Yes
Reason        meets_gate
Δ Pass Rate   0.0450
Δ 95% CI      [0.0320, 0.0580]
CI Method     bootstrap-cluster
Power         0.92
Policy        policy-strict
Report        reports/report_2025-01-16T10-30-00.json
```

### Rejected Candidate
```
Candidate     implementations/candidate_regression.py
Adopt?        ❌ No
Reason        Fairness violation: group disparity 0.15 > threshold 0.10
Δ Pass Rate   -0.0120
Δ 95% CI      [-0.0250, 0.0010]
Policy        policy-strict
Report        reports/report_2025-01-16T10-35-00.json
```

## Next Steps

1. **Read the Tutorial**: [TUTORIAL.md](TUTORIAL.md)
2. **Explore Configs**: Modify `configs/*.toml` to experiment
3. **Create Your Own**: Use this as a template for your use case
4. **Integrate CI/CD**: See [docs/cookbook/cicd-integration.md](../../docs/cookbook/cicd-integration.md)

## Resources

- **Main Documentation**: [docs/](../../docs/)
- **API Reference**: [docs/api/reference.md](../../docs/api/reference.md)
- **Cookbook**: [docs/cookbook.md](../../docs/cookbook.md)
- **GitHub**: https://github.com/duhboto/MetamorphicGuard

## Support

- **Issues**: https://github.com/duhboto/MetamorphicGuard/issues
- **Discussions**: https://github.com/duhboto/MetamorphicGuard/discussions







