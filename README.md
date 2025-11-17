# Metamorphic Guard

[![PyPI](https://img.shields.io/pypi/v/metamorphic-guard.svg)](https://pypi.org/project/metamorphic-guard/) [![Python](https://img.shields.io/pypi/pyversions/metamorphic-guard.svg?label=python)](https://pypi.org/project/metamorphic-guard/) [![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://opensource.org/licenses/MIT) [![Build](https://github.com/duhboto/MetamorphicGuard/actions/workflows/test.yml/badge.svg)](https://github.com/duhboto/MetamorphicGuard/actions/workflows/test.yml) [![Release](https://github.com/duhboto/MetamorphicGuard/actions/workflows/publish.yml/badge.svg)](https://github.com/duhboto/MetamorphicGuard/actions/workflows/publish.yml)

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

Sample CLI decisions:

**Accepted candidate:**
```bash
$ metamorphic-guard evaluate --task top_k --baseline baseline.py --candidate candidate.py
Candidate     candidate.py
Adopt?        ✅ Yes
Reason        meets_gate
Δ Pass Rate   0.0125
Δ 95% CI      [0.0040, 0.0210]
CI Method     bootstrap-cluster
Power (target 0.80) 0.86
Suggested n   520
Policy        policy-v1
Report        reports/report_2025-11-02T12-00-00.json
```

**Rejected candidate:**
```bash
$ metamorphic-guard evaluate --task top_k --baseline baseline.py --candidate candidate.py
Candidate     candidate.py
Adopt?        ❌ No
Reason        Improvement insufficient: CI lower bound -0.0050 < 0.02
Δ Pass Rate   -0.0025
Δ 95% CI      [-0.0100, 0.0050]
Policy        policy-v1
Report        reports/report_2025-11-02T12-00-00.json
```

## Overview

Metamorphic Guard evaluates candidate implementations against baseline versions by:

1. **Property Testing**: Verifying that outputs satisfy required properties
2. **Metamorphic Testing**: Checking that input transformations produce equivalent outputs
3. **Statistical Analysis**: Computing bootstrap confidence intervals on pass-rate differences
4. **Adoption Gating**: Making data-driven decisions about whether to adopt candidates

## Quick Start Tutorial

New to Metamorphic Guard? Check out our [First PR Gate Tutorial](docs/first-pr-gate-tutorial.md) for a complete walkthrough:
- Setting up your first evaluation
- Creating baseline and candidate implementations
- Integrating with GitHub Actions
- Generating reports and badges

**Getting Started:**
- **[Quick Start Guide](docs/getting-started/quickstart.md)** - Step-by-step walkthrough
- **[Onboarding Checklist](docs/getting-started/checklist.md)** - Ensure you have everything set up
- **[Installation Guide](docs/getting-started/installation.md)** - Installation options and profiles

**Architecture**: See [Architecture Documentation](docs/architecture.md) for details on component interfaces, execution system, worker liveness, and signal handling.

## Reference Projects in This Repository

Metamorphic Guard ships with four companion projects that demonstrate how teams can fold the library into their delivery workflows and produce auditable evidence:

- **Ranking Guard Project** (`ranking_guard_project/`): A realistic release gate for search ranking algorithms. It compares a production baseline to new candidates, enforces metamorphic relations, and surfaces adoption decisions that teams can wire into CI/CD or release dashboards. The bundled CLI (`ranking-guard evaluate ...`) saves JSON reports under `reports/` so stakeholders can review the statistical lift before promoting changes.
- **Fairness Guard Project** (`fairness_guard_project/`): A responsibility-focused workflow for credit approval models. It uses a fairness-aware task specification with parity checks and transformation invariants to catch regressions before they reach borrowers. The CLI (`fairness-guard evaluate ...`) exports JSON evidence, including observed fairness gaps and group approval rates, that can populate governance dashboards or compliance reviews.
- **Text Normalizer Guard** (`testguard_alpha/text_normalizer_guard_project/`): A domain-agnostic demonstration that proves Metamorphic Guard works beyond ML/LLM use cases. This project compares baseline and candidate text normalization implementations using properties (output validation) and metamorphic relations (whitespace padding, case flipping, whitespace bursting). The included `DEMONSTRATION.md` shows three experiments (healthy → broken → fixed) that prove the framework automatically catches regressions without hard-coded test cases, makes principled adoption decisions using statistical gates, and works for any pure function with testable invariants.
- **Minimal Demo** (`demo_project/`): A concise script that runs the same evaluation logic programmatically. It is ideal for teams who want to experiment in a notebook, wire Metamorphic Guard into existing automation, or share a lightweight proof-of-concept with stakeholders.

Together these examples highlight how the project supports the broader IT community: they provide reproducible workflows, confidence intervals that quantify risk, and machine-readable reports that serve as proof when auditing model or algorithm upgrades.

## Installation

### Standard Installation

```bash
pip install metamorphic-guard
```

For development:

```bash
pip install -e .
```

### One-off Usage (pipx)

For one-time evaluations without installing:

```bash
pipx run metamorphic-guard evaluate --task demo --baseline baseline.py --candidate candidate.py
```

This runs Metamorphic Guard in an isolated environment without modifying your system Python.

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
- `--stability`: Run evaluation N times and require consistent decisions (default: 1). When > 1, runs the evaluation multiple times with different seeds and reports flakiness if decisions differ. Useful for detecting non-deterministic behavior.
- `--shrink-violations`: Shrink failing test cases to minimal counterexamples for easier debugging. When enabled, violations include both original and shrunk inputs.
- `--timeout-s`: Timeout per test in seconds (default: 2.0)
- `--mem-mb`: Memory limit in MB (default: 512)
- `--min-delta`: Minimum improvement threshold (default: 0.02). `--improve-delta` is deprecated and will be removed in a future version.
- `--min-pass-rate`: Minimum candidate pass-rate required for adoption (default: 0.80).
- `--violation-cap`: Maximum violations to report (default: 25)
- `--parallel`: Number of worker processes used to drive the sandbox (default: 1)
- `--bootstrap-samples`: Resamples used for percentile bootstrap CI (default: 1000)
- `--ci-method`: Confidence interval method for pass-rate delta (`bootstrap`, `bootstrap-bca`, `bootstrap-cluster`, `bootstrap-cluster-bca`, `newcombe`, `wilson`). Default: `bootstrap`. See [Confidence Interval Methods](#confidence-interval-methods) for guidance.
- `--power-target`: Desired statistical power used when estimating recommended sample sizes (default: 0.8). The CLI prints the observed power and a suggested `n` for the current thresholds.
- `--rr-ci-method`: Confidence interval method for relative risk (`log`). Use when baseline pass-rate is near 0 or 1, or when you need a ratio-based comparison. The log method uses a log-normal approximation appropriate for ratio statistics.
- `--alpha`: Significance level for confidence intervals (default: 0.05)
- `--report-dir`: Destination directory for JSON reports (defaults to auto-discovery)
- `--executor`: Sandbox backend (`local`, `docker`, or `module:callable`)
- `--executor-config`: JSON object with executor-specific settings (e.g. CPU, image)
- `--config`: Path to a TOML file providing defaults for the above options
- `--export-violations`: Emit a JSON summary of property/MR failures to a given path
- `--otlp-endpoint`: OpenTelemetry OTLP endpoint URL for trace export (e.g., `http://localhost:4317`)
- `--html-report`: Write an interactive-ready HTML summary alongside the JSON report
- `--junit-report` / `--junit-xml`: Write JUnit XML output for CI integration (e.g., `--junit-report test-results.xml`)
- `--policy`: Policy to apply. Provide a path to a policy file (`.toml`/`.yaml`) or use presets like `noninferiority:margin=0.00` / `superiority:margin=0.02` (see [Policy as Code](#policy-as-code))
- `--dispatcher`: Execution dispatcher (`local` threads or `queue` for distributed execution)
- `--queue-config`: JSON configuration for queue-backed dispatchers (see [Queue Dispatch Documentation](docs/operations/queue-dispatch.md))
- `--monitor`: Enable built-in monitors such as `latency`
- `--mr-fwer`: Apply Holm-Bonferroni multiple-comparison correction across metamorphic relations.
- `--mr-fdr`: Apply Benjamini-Hochberg false-discovery-rate correction across metamorphic relations.

### Programmatic API

Prefer running evaluations from Python? Use the high-level helpers in `metamorphic_guard.api`:

```python
from metamorphic_guard import (
    TaskSpec,
    Property,
    Metric,
    Implementation,
    EvaluationConfig,
    run,
)

spec = TaskSpec(
    name="demo_task",
    gen_inputs=lambda n, seed: [(i,) for i in range(n)],
    properties=[
        Property(
            check=lambda output, x: isinstance(output, dict) and "value" in output,
            description="Outputs include a value field",
        )
    ],
    relations=[],
    equivalence=lambda a, b: a == b,
    metrics=[
        Metric(
            name="value_mean",
            extract=lambda output, _: float(output["value"]),
            kind="mean",
        )
    ],
)

result = run(
    task=spec,
    baseline=Implementation(path="baseline.py"),
    candidate=Implementation(path="candidate.py"),
    config=EvaluationConfig(n=100, seed=123, min_delta=0.0),
)

if result.adopt:
    print("Candidate passes:", result.reason)
else:
    print("Candidate rejected:", result.reason)
```

Prefer in-memory functions? Replace the file-backed implementations with callables:

```python
result = run(
    task=spec,
    baseline=Implementation.from_callable(baseline_callable),
    candidate=Implementation.from_callable(candidate_callable),
    config=EvaluationConfig(n=100, seed=123, min_delta=0.0),
)
```

Callables already packaged in modules can be referenced without importing them first:

```python
result = run(
    task=spec,
    baseline=Implementation.from_dotted("my_project.models:baseline"),
    candidate=Implementation.from_dotted("my_project.models:candidate"),
    config=EvaluationConfig(n=100, seed=123, min_delta=0.0),
)
```

Working from a TOML config file? Reuse the same spec and let Metamorphic Guard resolve the implementations for you:

```python
from metamorphic_guard import run_with_config

result = run_with_config("guard.toml", task=spec)
```

The helper understands both file paths and dotted callables (e.g., `"pkg.module:solve"`) specified in the config’s `baseline` and `candidate` fields. You can also pass an in-memory mapping (with an optional `[metamorphic_guard]` section) or an `EvaluatorConfig` instance when generating configs programmatically.

The `run` helper wraps the full harness: it registers your `TaskSpec`, executes both implementations with sandboxing and statistical analysis, and returns an `EvaluationResult` containing the adoption decision and the full JSON report.

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

**MR Library**: See the [Metamorphic Relation Library](docs/mr-library.md) for a curated catalog of MRs organized by category (permutation, monotonicity, fairness, RAG, etc.) with examples, rationale, and literature citations. Use this guide to select appropriate MRs for your domain and author new ones.

**Coverage Analysis**: Reports include `relation_coverage` showing per-relation and per-category pass rates. Use this to:
- Identify gaps in MR coverage (missing categories)
- Detect flaky MRs (inconsistent failures)
- Understand domain-specific failure patterns
- For LLM evaluations, the JSON and HTML reports expose aggregated **LLM Metrics** (cost, tokens, latency, retries) alongside the Prometheus counter `metamorphic_llm_retries_total`, making it easier to monitor API spend and resiliency.

Each report now includes hashes for the generator function, properties, metamorphic
relations, and formatter callables (`spec_fingerprint`). This makes it possible to
prove precisely which oracles were active during a run.

#### Cluster Keys

If your generator emits several test cases per seed (e.g., batched mutants or MR families), supply a `cluster_key` that maps each argument tuple to a bucket:

```python
Spec(
    gen_inputs=my_inputs,
    properties=[...],
    relations=[...],
    equivalence=multiset_equal,
    cluster_key=lambda args: args[0]["seed"],
)
```

- Cluster labels flow into reports (`cases[].cluster`) and allow `--ci-method bootstrap-cluster` to resample entire groups.
- Leave `cluster_key` unset (default) when trials are independent and identically distributed.

### Config Files

Store frequently used defaults in a TOML file and pass it via `--config`:

```toml
task = "top_k"
baseline = "examples/top_k_baseline.py"
candidate = "examples/top_k_improved.py"
n = 600
seed = 1337
executor = "docker"
executor_config = { image = "python:3.11-slim", cpus = 2, memory_mb = 1024 }
policy_version = "policy-2025-11-09"

[metamorphic_guard.queue]
backend = "redis"
url = "redis://localhost:6379/0"

[metamorphic_guard.alerts]
webhooks = ["https://hooks.example.dev/metaguard"]
```

Run with:

```bash
metamorphic-guard --config metaguard.toml --report-dir reports/
```

CLI arguments still override config values when provided.

Configuration files are validated via a Pydantic schema; malformed values (e.g.
negative `n`, unknown dispatchers) raise actionable CLI errors before a run starts.
The optional `policy_version` propagates into reports/metadata, making it easy to
track changes to guard rails across deployments.

### Monitors & Alerts

Monitors provide higher-order statistical invariants beyond per-test properties.
Enable them via `--monitor latency` to capture latency distributions and flag
regressions, add `--monitor fairness` to track per-group success deltas, or
`--monitor resource:metric=cpu_ms,alert_ratio=1.3` to watch resource budgets.
Monitor output is written under the `monitors` key in the JSON report and
surfaced in the optional HTML report. Combine monitors by repeating
`--monitor …` on the CLI or programmatically via the Python API.

Alerts can be pushed to downstream systems by wiring `--alert-webhook
https://hooks.example.dev/guard`. The payload contains the flattened monitor
alerts together with run metadata (task, decision, run_id) for correlation.

**Example alert payload:**
```json
{
  "alerts": [
    {
      "monitor": "latency",
      "message": "Latency regression detected",
      "baseline_p50_ms": 45.2,
      "candidate_p50_ms": 78.5,
      "ratio": 1.74
    }
  ],
  "metadata": {
    "task": "top_k",
    "decision": {"adopt": false, "reason": "latency_regression"},
    "run_id": "run_20250110_120000",
    "policy_version": "policy-v1"
  }
}
```

Alerts appear in the HTML report under each monitor's section when present.

### Environment Variables

Metamorphic Guard supports the following environment variables for configuration:

| Variable | Description | Default |
|----------|-------------|---------|
| `METAMORPHIC_GUARD_LOG_JSON` | Enable structured JSON logging (`1` to enable) | Disabled |
| `METAMORPHIC_GUARD_PROMETHEUS` | Enable Prometheus metrics (`1` to enable) | Disabled |
| `METAMORPHIC_GUARD_REPORT_DIR` | Directory for JSON reports | Auto-discovered |
| `METAMORPHIC_GUARD_FAILED_DIR` | Directory for failed-case artifacts | `reports/failed_cases/` |
| `METAMORPHIC_GUARD_EXECUTOR` | Sandbox executor (`local`, `docker`, or `module:callable`) | `local` |
| `METAMORPHIC_GUARD_EXECUTOR_CONFIG` | JSON string with executor-specific settings | None |
| `METAMORPHIC_GUARD_DOCKER_IMAGE` | Docker image for executor (overrides default) | `python:3.11-slim` |
| `METAMORPHIC_GUARD_REDACT` | Comma-separated regex patterns for secret redaction | Built-in patterns |
| `METAMORPHIC_GUARD_BANNED` | Comma-separated list of banned Python modules | None |

**Example:**
```bash
export METAMORPHIC_GUARD_LOG_JSON=1
export METAMORPHIC_GUARD_PROMETHEUS=1
export METAMORPHIC_GUARD_EXECUTOR=docker
export METAMORPHIC_GUARD_DOCKER_IMAGE=python:3.12-slim
metamorphic-guard evaluate --task top_k --baseline baseline.py --candidate candidate.py
```

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
- Structured failures: sandbox responses include `error_type` / `error_code` fields (e.g., `timeout`, `process_exit`) and diagnostics for easier automation.
- Secret redaction: configure `METAMORPHIC_GUARD_REDACT` or `executor_config.redact_patterns` to scrub sensitive values from stdout/stderr/results before they leave the sandbox. Default patterns catch common API keys and tokens.
- Optional executors: set `--executor` / `METAMORPHIC_GUARD_EXECUTOR` to run evaluations inside Docker (`docker`) or a custom plugin (`package.module:callable`). Pass JSON tunables via `--executor-config` / `METAMORPHIC_GUARD_EXECUTOR_CONFIG` and override the Docker image with `METAMORPHIC_GUARD_DOCKER_IMAGE`.

**Example Docker run:**

```bash
metamorphic-guard \
  --task top_k \
  --baseline examples/top_k_baseline.py \
  --candidate examples/top_k_improved.py \
  --executor docker \
  --executor-config '{"image":"python:3.11-slim","cpus":1.5,"memory_mb":768}'
```

**Security Hardening:**

> **⚠️ Security Disclaimer:** The built-in sandbox provides application-level isolation (network denial, subprocess blocking, FFI/multiprocessing guards) but does not provide kernel-level isolation. For untrusted code, always run evaluations inside OS-level containers or VMs with additional hardening.

When using the Docker executor, Metamorphic Guard applies the following security measures:

**Application-level (always enabled):**
- Network access disabled (`--network none` or `NO_NETWORK=1`)
- Subprocess creation blocked (`os.system`, `subprocess.Popen`, etc.)
- Native FFI blocked (`ctypes`, `cffi`)
- Multiprocessing forks blocked
- User site-packages disabled (`PYTHONNOUSERSITE=1`)
- Resource limits: CPU time, memory, process count

**Docker-level (configurable via `executor_config.security_opt`):**
- Seccomp profiles: restrict syscalls (e.g., `seccomp=unconfined` or custom profile)
- AppArmor profiles: restrict filesystem/network access
- Capabilities: drop privileges (e.g., `--cap-drop ALL`)
- Read-only filesystem: `--read-only` with tmpfs mounts
- No new privileges: `--security-opt no-new-privileges:true`
- User namespace: `--userns=host` or custom mapping

**Hardened deployment example:**

See `deploy/docker-compose.worker.yml` for a production-ready stack with:
- Read-only root filesystem
- Dropped capabilities
- Network isolation
- Resource limits
- Redis-backed queue

**Recommended for untrusted code:**
```bash
metamorphic-guard \
  --executor docker \
  --executor-config '{
    "image": "python:3.11-slim",
    "security_opt": [
      "no-new-privileges:true",
      "seccomp=./seccomp-profile.json"
    ],
    "read_only": true,
    "tmpfs": ["/tmp"],
    "cap_drop": ["ALL"]
  }'
```

### Distributed Execution

The queue dispatcher (`--dispatcher queue`) enables distributed execution. In-memory
queues are available for local experimentation, while a Redis-backed adapter lets
you scale out with remote workers:

```bash
metamorphic-guard --dispatcher queue \
  --queue-config '{"backend":"redis","url":"redis://localhost:6379/0"}' \
  --monitor latency \
  --task top_k --baseline baseline.py --candidate candidate.py --min-delta 0.0

# On worker machines
metamorphic-guard-worker --backend redis --queue-config '{"url":"redis://localhost:6379/0"}'
```

Workers fetch tasks, run sandboxed evaluations, and stream results back to the
coordinator. Memory backend workers remain in-process and are best suited for tests.

Adaptive queue controls:
- `adaptive_batching` (default `true`) grows/shrinks batch sizes based on observed
  duration and queue pressure. Override `initial_batch_size`, `max_batch_size`, or
  `adaptive_fast_threshold_ms` / `adaptive_slow_threshold_ms` to tune behaviour.
- `adaptive_compress` automatically avoids gzip when payloads are already tiny or
  compression fails to win over raw JSON, cutting CPU for short test cases.
- `inflight_factor` governs how many cases are kept in-flight (per worker) before
  backpressure kicks in; lower it for heavyweight candidates, raise it for latency-sensitive smoke tests.

### Confidence Interval Methods

Metamorphic Guard supports multiple methods for computing confidence intervals on pass-rate differences:

| Method | Description | When to Use |
|--------|-------------|-------------|
| `bootstrap` | Percentile bootstrap resampling | Default choice for IID trials. Works well for any sample size, accounts for correlation between baseline and candidate. |
| `bootstrap-bca` | Bootstrap with bias-corrected and accelerated (BCa) intervals | Use when you want percentile bootstrap coverage with bias/acceleration corrections. Especially helpful when delta distributions are skewed. |
| `bootstrap-cluster` | Bootstrap that resamples entire clusters determined by `Spec.cluster_key` | Use when multiple trials share a seed, MR family, or other grouping. Prevents optimistic CIs when tests are correlated. |
| `bootstrap-cluster-bca` | Cluster bootstrap with BCa adjustments | Combines cluster-aware resampling with BCa corrections. Use for correlated trials where skew/bias matters. |
| `newcombe` | Newcombe's hybrid score method | Good for small samples or when you need a closed-form solution. Based on Wilson score intervals. |
| `wilson` | Wilson score interval | Alternative closed-form method. Similar to Newcombe but uses a different approach. |

**Why Bootstrap?** Bootstrap resampling is the default because it:
- Makes no distributional assumptions about pass rates
- Handles small sample sizes gracefully
- Accounts for the correlation between baseline and candidate results (they're tested on the same inputs)
- Provides accurate coverage even when pass rates are near 0 or 1
- BCa variants (`bootstrap-bca`, `bootstrap-cluster-bca`) correct for bias and skew via jackknife acceleration, reducing under/over-coverage in asymmetric settings

For relative risk (candidate/baseline ratio), the `log` method uses a log-normal approximation, which is appropriate for ratio statistics.

#### Cluster Keys & Power Guidance

- Provide `Spec.cluster_key` when multiple trials belong to the same scenario (e.g., identical generator seed or MR bundle). When `--ci-method bootstrap-cluster` is selected, Metamorphic Guard resamples whole clusters instead of individual trials, preserving correlations.
- Reports now include `statistics.power_estimate` and `statistics.recommended_n`; the CLI mirrors these values so you can judge whether an evaluation was sufficiently powered for the current `--power-target`.
- Every JSON report ships with a replay bundle (`*_cases.json`) plus a copy-pastable CLI command, making it trivial to re-run or debug any evaluation.

#### Paired Analysis Diagnostics

- Because baseline and candidate run on the same cases, the report records paired contingency counts under `statistics.paired` (`baseline_only`, `candidate_only`, `discordant`, etc.).
- A McNemar test with continuity correction (`mcnemar_p`) is included to flag churn (many baseline-only vs candidate-only passes) even when the overall delta nets to zero.
- The CLI prints the discordant counts and McNemar p-value after each evaluation so reviewers can see whether improvements are concentrated or noisy.

### Policy as Code

Policies describe guard-rail thresholds (minimum delta, pass-rate floor, etc.) and live alongside code so changes are auditable. Metamorphic Guard accepts `.toml` or `.yaml` policy files via `--policy` or the `policy` key in config files. Example:

```bash
metamorphic-guard evaluate ... --policy noninferiority:margin=0.01
```

The inline preset above enforces a non-inferiority margin (CI lower bound may dip up to 1%). Swap to `superiority:margin=0.02` to require a 2% lift. Presets can also override `pass_rate`, `alpha`, `power`, and `violation_cap`. Provide a structured policy file when you need richer multi-dimensional gates (quality/cost/latency/trust), governance metadata, or team-specific thresholds.

```toml
name = "policy-v1"
description = "Baseline guardrail policy ensuring minimum lift and pass rate."

[gating]
min_delta = 0.02
min_pass_rate = 0.80
alpha = 0.05
power_target = 0.8
violation_cap = 25
```

Policies are stored under `policies/` for local development. Use `policy-v1.toml` as a starting point or opt into the stricter `policy-strict.toml`. Reports embed policy metadata (`config.policy_version`, `policy` block) so downstream systems know which guard rails were active.

### Plugin Ecosystem

Metamorphic Guard supports external extensions via Python entry points:

- `metamorphic_guard.monitors`: register additional monitor factories
- `metamorphic_guard.dispatchers`: provide custom dispatcher implementations
- Inspect installed plugins with `metamorphic-guard plugin list` (append `--json` for machine-readable output) and view rich metadata via `metamorphic-guard plugin info <name>`.
- Third-party packages should expose a `PLUGIN_METADATA` mapping (name, version, guard_min/guard_max, sandbox flag, etc.) so compatibility is surfaced in the registry.

Example `pyproject.toml` snippet:

```toml
[project.entry-points."metamorphic_guard.monitors"]
latency99 = "my_package.monitors:Latency99Monitor"
```

Once installed, the new monitor can be referenced on the CLI:

```bash
metamorphic-guard --monitor latency99
```

### Generating Reports

#### HTML Reports

Generate an HTML report from an existing JSON report:

```bash
metamorphic-guard report report_20250101_120000.json -o report.html
```

Or generate HTML during evaluation:

```bash
metamorphic-guard evaluate --task demo --baseline baseline.py --candidate candidate.py --html-report report.html
```

#### JUnit XML for CI

Generate JUnit XML output for CI dashboards:

```bash
metamorphic-guard evaluate --task demo --baseline baseline.py --candidate candidate.py --junit-report test-results.xml
```

This produces standard JUnit XML that can be consumed by Jenkins, GitHub Actions, GitLab CI, and other CI systems.

#### GitHub Actions Integration

Metamorphic Guard includes a ready-to-use GitHub Actions workflow template. See [GitHub Actions Documentation](docs/github-actions.md) for setup instructions.

The template workflow (`.github/workflows/metamorphic-guard-template.yml`) provides:
- Automatic evaluation on pull requests
- Report uploads (HTML, JSON, JUnit XML)
- PR comments with evaluation results and metrics
- Status badge generation
- Job failure on candidate rejection

Copy the template to your repository's `.github/workflows/` directory and customize as needed.

#### JSON Schema

Report and configuration files conform to JSON Schemas for validation and type checking:

- **Report Schema**: `schemas/report.schema.json` - Validates evaluation report JSON files
- **Config Schema**: `schemas/config.schema.json` - Validates TOML configuration files (when converted to JSON)

Reports include a `provenance` section with auditability metadata:
- Library version (`library_version`)
- Git commit SHA (`git_sha`) and dirty status (`git_dirty`)
- Python version and platform information (`python_version`, `platform`, `hostname`, `executable`)
- Metamorphic relation identifiers (`mr_ids`)
- Task specification fingerprint (`spec_fingerprint`)
- Runtime environment details (`environment`)
- Sandbox configuration details (`sandbox.executor`, time/memory limits, call-spec fingerprints, executor config hash)

This enables:
- Validation of report files
- Type checking in integrations
- IDE autocomplete for report consumers
- Automated schema validation in CI/CD pipelines
- Full auditability and reproducibility of evaluation runs

Validate a report against the schema:

```bash
# Using ajv-cli (npm install -g ajv-cli)
ajv validate -s schemas/report.schema.json -d report_20250101_120000.json
```

Schemas are automatically generated from Pydantic models and can be regenerated with:

```bash
python scripts/export_schemas.py
```

Programmatic APIs (`metamorphic_guard.monitoring.resolve_monitors`) also pick up
registered plugins, enabling teams to share bespoke invariants, dispatchers, and
workflows across services.
Pass `--sandbox-plugins` during evaluation (or set `sandbox_plugins = true` in config) to execute third-party monitors inside per-plugin subprocesses. Plugins can set `sandbox = true` in their metadata to request isolation by default.

### Observability & Artifacts

- Set `METAMORPHIC_GUARD_LOG_JSON=1` to stream structured JSON logs (start/complete events,
  worker task telemetry) to stdout for ingestion by log pipelines.
- Prefer the CLI toggles `--log-json` / `--no-log-json` and `--metrics` / `--no-metrics` for one-off runs; pair with `--metrics-port` to expose a Prometheus endpoint directly from the coordinator or worker.
- Capture structured logs to disk with `--log-file observability/run.jsonl`; the coordinator/worker
  will append JSON events and handle file lifecycle automatically.
- Enable Prometheus counters by exporting `METAMORPHIC_GUARD_PROMETHEUS=1` and register the
  exposed registry (`metamorphic_guard.observability.prometheus_registry()`) with your HTTP exporter.
- Persist failing case artifacts either by providing `METAMORPHIC_GUARD_FAILED_DIR` or letting the
  harness default to `reports/failed_cases/`; these JSON snapshots capture violations and config for debugging.
- Retention controls: `--failed-artifact-limit` caps how many snapshots are retained and
  `--failed-artifact-ttl-days` prunes entries older than the configured horizon.
- ### OpenTelemetry Integration

For distributed tracing and observability, Metamorphic Guard can export traces to OpenTelemetry:

```bash
metamorphic-guard evaluate \
  --task top_k \
  --baseline baseline.py \
  --candidate candidate.py \
  --otlp-endpoint http://localhost:4317
```

This exports traces containing:
- Evaluation metadata (task, baseline, candidate, n)
- Decision and reasoning
- Pass rates and deltas
- LLM metrics (cost, tokens) if applicable
- Trust scores if applicable
- Individual test case traces

Install OpenTelemetry dependencies:

```bash
pip install metamorphic-guard[otel]
```

Or manually:

```bash
pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-grpc
```

Traces can be visualized in Grafana, Jaeger, or any OTLP-compatible backend.

Queue telemetry ships out-of-the-box: `metamorphic_queue_pending_tasks` (tasks waiting),
  `metamorphic_queue_inflight_cases` (cases outstanding), and `metamorphic_queue_active_workers`
  (live heartbeat count) alongside throughput counters (`*_cases_dispatched_total`, `*_cases_completed_total`,
  `*_cases_requeued_total`).
- A starter Grafana dashboard lives at `docs/grafana/metamorphic-guard-dashboard.json` – import it
  into Grafana and point the Prometheus datasource at the Guard metrics endpoint for live telemetry.
- HTML reports embed Chart.js dashboards summarising pass rates, fairness gaps, and resource usage
  whenever the relevant monitors are enabled, making it easy to eyeball regressions without leaving the report.

### Quick Start Wizard & Cookbook

- Run `metamorphic-guard init` to scaffold a `metamorphic_guard.toml` configuration (supports distributed
  queue defaults and monitor presets).
- Prefer `metamorphic-guard init --interactive` for a guided wizard that prompts for baseline/candidate paths,
  distributed mode, and default monitors.
- Generate reusable plugin templates with `metamorphic-guard scaffold-plugin --kind monitor --name MyMonitor` and
  wire them into your project via entry points.
- Explore `docs/cookbook.md` for recipes covering distributed evaluations, advanced monitors, and CI pipelines.

### Benchmark Suites & Stability Audits

Metamorphic Guard includes benchmark regression suites (`tests/test_benchmarks.py`) that validate the statistics engine with known lifts (positive/negative). These suites ensure confidence intervals and adoption decisions are computed correctly.

**Stability Audit**: Use `stability-audit` command to detect flakiness:

```bash
metamorphic-guard stability-audit \
  --task top_k \
  --baseline baseline.py \
  --candidate candidate.py \
  --num-seeds 20 \
  --output audit.json
```

This runs evaluations across multiple seeds and reports:
- Consensus status (all runs agree)
- Flakiness detection (inconsistent decisions)
- Per-seed decisions and delta pass rates

**Governance**: See [Governance Documentation](docs/governance.md) for signed artifacts, reproducible bundles, and compliance use cases.

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
    "min_delta": 0.02,
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
  "job_metadata": {
    "hostname": "build-agent-01",
    "python_version": "3.11.8",
    "git_commit": "d1e5f8...",
    "git_dirty": false
  },
  "monitors": {
    "LatencyMonitor": {
      "id": "LatencyMonitor",
      "type": "latency",
      "percentile": 0.95,
      "summary": {
        "baseline": {"count": 400, "mean_ms": 1.21, "p95_ms": 1.89},
        "candidate": {"count": 400, "mean_ms": 1.05, "p95_ms": 1.61}
      },
      "alerts": []
    }
  },
  "environment": {
    "python_version": "3.11.8",
    "implementation": "CPython",
    "platform": "macOS-14-arm64-arm-64bit",
    "executable": "/usr/bin/python3"
  }
}
```