# Metamorphic Guard

A Python library that compares two program versions—*baseline* and *candidate*—by running property and metamorphic tests, computing confidence intervals on pass-rate differences, and deciding whether to adopt the candidate.

## Overview

Metamorphic Guard evaluates candidate implementations against baseline versions by:

1. **Property Testing**: Verifying that outputs satisfy required properties
2. **Metamorphic Testing**: Checking that input transformations produce equivalent outputs
3. **Statistical Analysis**: Computing bootstrap confidence intervals on pass-rate differences
4. **Adoption Gating**: Making data-driven decisions about whether to adopt candidates

## Quick Start

```bash
pip install metamorphic-guard
```

```bash
metamorphic-guard evaluate \
  --task top_k \
  --baseline baseline.py \
  --candidate candidate.py \
  --n 400
```

## Features

- ✅ **Statistical Rigor**: Bootstrap confidence intervals, power analysis, sequential testing
- ✅ **LLM Support**: Built-in executors for OpenAI, Anthropic, and vLLM
- ✅ **Plugin System**: Extensible architecture for executors, judges, mutants, and monitors
- ✅ **Distributed Execution**: Queue-based dispatcher with Redis support
- ✅ **Observability**: Prometheus metrics, OpenTelemetry, structured logging
- ✅ **Cost Estimation**: Pre-run cost estimation for LLM evaluations

## Documentation

- [Getting Started](getting-started/quickstart.md) - Install and run your first evaluation
- [User Guide](user-guide/basic-usage.md) - Learn how to use Metamorphic Guard
- [LLM Evaluation](user-guide/llm-evaluation.md) - Evaluate Large Language Models
- [API Reference](api/harness.md) - Complete API documentation
- [Examples](examples/basic.md) - Code examples and tutorials

## Example Output

**Accepted candidate:**
```
Candidate     candidate.py
Adopt?        ✅ Yes
Reason        meets_gate
Δ Pass Rate   0.0125
Δ 95% CI      [0.0040, 0.0210]
CI Method     bootstrap
Power (target 0.80) 0.86
```

## License

MIT License - see LICENSE file for details.

