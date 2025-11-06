# Metamorphic Guard

[![PyPI](https://img.shields.io/pypi/v/metamorphic-guard.svg)](https://pypi.org/project/metamorphic-guard/) [![Python](https://img.shields.io/pypi/pyversions/metamorphic-guard.svg?label=python)](https://pypi.org/project/metamorphic-guard/) [![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://opensource.org/licenses/MIT) [![Build](https://github.com/duhboto/MetamorphicGuard/actions/workflows/test.yml/badge.svg)](https://github.com/duhboto/MetamorphicGuard/actions/workflows/test.yml)

A Python library that compares two program versions—*baseline* and *candidate*—by running property and metamorphic tests, computing confidence intervals on pass-rate differences, and deciding whether to adopt the candidate.

```
                 +-------------------+
 search queries  |  Property & MR    |  candidate results
  ─────────────▶ |  test harness     | ────────────────▶ adoption gate
                 +---------┬---------+
                           │
                           ▼
                 +-------------------+
                 |  Bootstrap stats  |
                 |  Δ pass-rate CI   |
                 +---------┬---------+
                           │
                           ▼
            ranking-guard evaluate --candidate implementations/candidate_heap.py
```

Sample CLI decision:

```bash
$ ranking-guard evaluate --candidate implementations/candidate_heap.py
Candidate     implementations/candidate_heap.py
Adopt?        ✅ Yes
Reason        meets_gate
Δ Pass Rate   0.0125
Δ 95% CI      [0.0040, 0.0210]
Report        reports/report_2025-11-02T12-00-00.json
```

## Overview

Metamorphic Guard evaluates candidate implementations against baseline versions by:

1. **Property Testing**: Verifying that outputs satisfy required properties
2. **Metamorphic Testing**: Checking that input transformations produce equivalent outputs
3. **Statistical Analysis**: Computing bootstrap confidence intervals on pass-rate differences
4. **Adoption Gating**: Making data-driven decisions about whether to adopt candidates

## Reference Projects in This Repository

Metamorphic Guard ships with three companion projects that demonstrate how teams can fold the library into their delivery workflows and produce auditable evidence:

- **Ranking Guard Project** (`ranking_guard_project/`): A realistic release gate for search ranking algorithms. It compares a production baseline to new candidates, enforces metamorphic relations, and surfaces adoption decisions that teams can wire into CI/CD or release dashboards. The bundled CLI (`ranking-guard evaluate ...`) saves JSON reports under `reports/` so stakeholders can review the statistical lift before promoting changes.
- **Fairness Guard Project** (`fairness_guard_project/`): A responsibility-focused workflow for credit approval models. It uses a fairness-aware task specification with parity checks and transformation invariants to catch regressions before they reach borrowers. The CLI (`fairness-guard evaluate ...`) exports JSON evidence, including observed fairness gaps and group approval rates, that can populate governance dashboards or compliance reviews.
- **Minimal Demo** (`demo_project/`): A concise script that runs the same evaluation logic programmatically. It is ideal for teams who want to experiment in a notebook, wire Metamorphic Guard into existing automation, or share a lightweight proof-of-concept with stakeholders.

Together these examples highlight how the project supports the broader IT community: they provide reproducible workflows, confidence intervals that quantify risk, and machine-readable reports that serve as proof when auditing model or algorithm upgrades.

## Installation

```bash
pip install -e .
```

## Quick Start

### Basic Usage

```bash
metamorphic-guard --task top_k \
  --baseline examples/top_k_baseline.py \
  --candidate examples/top_k_improved.py
```

> Tip: If the shorter `metamorphic-guard` alias collides with a system binary,
> use `python -m metamorphic_guard.cli` or the alternative console script
> `metaguard`.

### Command Line Options

```bash
metamorphic-guard --help
```

**Required Options:**
- `--task`: Task name to evaluate (e.g., "top_k")
- `--baseline`: Path to baseline implementation
- `--candidate`: Path to candidate implementation

**Optional Options:**
- `--n`: Number of test cases (default: 400)
- `--seed`: Random seed for reproducibility (default: 42)
- `--timeout-s`: Timeout per test in seconds (default: 2.0)
- `--mem-mb`: Memory limit in MB (default: 512)
- `--alpha`: Significance level for confidence intervals (default: 0.05)
- `--improve-delta`: Minimum improvement threshold (default: 0.02)
- `--violation-cap`: Maximum violations to report (default: 25)
- `--parallel`: Number of worker processes used to drive the sandbox (default: 1)
- `--bootstrap-samples`: Resamples used for percentile bootstrap CI (default: 1000)
- `--ci-method`: Confidence interval method for pass-rate delta (`bootstrap`, `newcombe`, `wilson`)
- `--rr-ci-method`: Confidence interval method for relative risk (`log`)
- `--ci-method`: Confidence interval method for pass-rate delta (`bootstrap` or `newcombe`)

## Example Implementations

The `examples/` directory contains sample implementations for the `top_k` task:

- **`top_k_baseline.py`**: Correct baseline implementation
- **`top_k_bad.py`**: Buggy implementation (should be rejected)
- **`top_k_improved.py`**: Improved implementation (should be accepted)

## Task Specification

### Top-K Task

The `top_k` task finds the k largest elements from a list:

**Input**: `(L: List[int], k: int)`
**Output**: `List[int]` - k largest elements, sorted in descending order

**Properties**:
1. Output length equals `min(k, len(L))`
2. Output is sorted in descending order
3. All output elements are from the input list

**Metamorphic Relations**:
1. **Permute Input**: Shuffling the input list should produce equivalent results
2. **Add Noise Below Min**: Adding small values below the minimum should not affect results

### Designing Effective Properties & Relations

Metamorphic Guard is only as strong as the properties and relations you write. When
modeling real ranking or pricing systems:

- **Separate invariants and tolerances** – keep hard invariants in `mode="hard"`
  properties and express tolerance-based expectations (e.g., floating point) as
  soft checks where near-misses are acceptable.
- **Explore symmetry & monotonicity** – swapping equivalent features, shuffling
  inputs, or scaling features by positive constants are high-signal relations for
  recommender systems.
- **Inject dominated noise** – append low-utility items to ensure the top results
  remain stable under additional clutter.
- **Idempotence & projection** – running the algorithm twice should yield the same
  output for deterministic tasks; encode this where appropriate.
- **Control randomness** – expose seed parameters and re-run stochastic algorithms
  with fixed seeds inside your relations for reproducibility.

Each report now includes hashes for the generator function, properties, metamorphic
relations, and formatter callables (`spec_fingerprint`). This makes it possible to
prove precisely which oracles were active during a run.

## Implementation Requirements

### Candidate Function Contract

Each candidate file must export a callable function:

```python
def solve(*args):
    """
    Your implementation here.
    Must handle the same input format as the task specification.
    """
    return result
```

### Sandbox Execution

- All candidate code runs in isolated subprocesses
- Resource limits: CPU time, memory usage
- Network access is disabled by stubbing socket primitives and import hooks
- Subprocess creation (`os.system`, `subprocess.Popen`, etc.) is denied inside the sandbox
- Native FFI (`ctypes`, `cffi`), multiprocessing forks, and user site-packages are blocked at import time
- Timeout enforcement per test case
- Deterministic execution with fixed seeds

> **Deployment tip:** For untrusted code, run the sandbox worker inside an OS-level
> container or VM (e.g., Docker with seccomp/AppArmor or Firejail) and drop Linux
> capabilities. The built-in guardrails reduce attack surface, but pairing them with
> kernel isolation provides a stronger security boundary.

## Output Format

The system generates JSON reports in `reports/report_<timestamp>.json`:

```json
{
  "task": "top_k",
  "n": 400,
  "seed": 42,
  "config": {
    "timeout_s": 2.0,
    "mem_mb": 512,
    "alpha": 0.05,
    "improve_delta": 0.02,
    "violation_cap": 25,
    "parallel": 1,
    "bootstrap_samples": 1000,
    "ci_method": "bootstrap",
    "rr_ci_method": "log"
  },
  "hashes": {
    "baseline": "sha256...",
    "candidate": "sha256..."
  },
  "spec_fingerprint": {
    "gen_inputs": "sha256...",
    "properties": [
      { "description": "Output length equals min(k, len(L))", "mode": "hard", "hash": "sha256..." }
    ],
    "relations": [
      { "name": "permute_input", "expect": "equal", "hash": "sha256..." }
    ],
    "equivalence": "sha256...",
    "formatters": { "fmt_in": "sha256...", "fmt_out": "sha256..." }
  },
  "baseline": {
    "passes": 388,
    "total": 400,
    "pass_rate": 0.97
  },
  "candidate": {
    "passes": 396,
    "total": 400,
    "pass_rate": 0.99,
    "prop_violations": [],
    "mr_violations": []
  },
  "delta_pass_rate": 0.02,
  "delta_ci": [0.015, 0.035],
  "relative_risk": 1.021,
  "relative_risk_ci": [0.998, 1.045],
  "decision": {
    "adopt": true,
    "reason": "meets_gate"
  },
  "environment": {
    "python_version": "3.11.8",
    "implementation": "CPython",
    "platform": "macOS-14-arm64-arm-64bit",
    "executable": "/usr/bin/python3"
  }
}
```

## Adoption Policy

A candidate is adopted if **all** conditions are met:

1. **No Property Violations**: All hard properties must pass
2. **No Metamorphic Relation Violations**: All relations must be satisfied
3. **Sufficient Improvement**: Lower bound of 95% CI > improvement threshold
4. **Minimum Pass Rate**: Candidate pass rate ≥ minimum threshold

## Testing

Install development dependencies first:

```bash
pip install -e .[dev]
# or
pip install -r requirements-dev.txt
```

Run the test suite:

```bash
pytest tests/
```

Run specific test categories:

```bash
pytest tests/test_sandbox.py    # Sandbox isolation tests
pytest tests/test_harness.py    # Evaluation tests
pytest tests/test_gate.py       # Adoption logic tests
```

## Contributing

We welcome contributions that extend Metamorphic Guard or its companion demos.

- Open issues or propose feature ideas via GitHub discussions or pull requests. Describe the use case and attach any relevant reports generated under `reports/`.
- Run `pytest tests/` locally before submitting a PR to ensure the gate, harness, and sandbox integrations stay green.
- Explore the reference projects for inspiration: scripts in `examples/` show minimal usage, `demo_project/src/run_demo.py` offers a scripted walkthrough, and `ranking_guard_project/` demonstrates a production-style release gate.
