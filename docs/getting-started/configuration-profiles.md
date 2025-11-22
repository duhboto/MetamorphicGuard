# Configuration Profiles

Metamorphic Guard is highly configurable. To help you get started, we provide three standard profiles: **Safe Defaults**, **Fast Checks**, and **Research Mode**.

Choose the profile that best matches your current stage of development.

---

## 1. Safe Defaults (Recommended for CI/CD)
**Goal**: Reliability and low false positives. Use this for release gates and blocking PR merges.

```toml
# policy-safe.toml

[evaluation]
n = 400                 # High sample size for statistical significance
alpha = 0.05            # Standard 95% confidence level
bootstrap_samples = 5000 # Accurate confidence intervals

[dispatcher]
kind = "local"          # Simple, robust execution
workers = 4             # Conservative parallelism (adjust to CPU count)
sandbox = true          # Isolate execution

[gate]
method = "bootstrap"    # Robust CI calculation
threshold = 0.0         # Candidate must be strictly better or equal (non-inferiority)
allow_flaky = false     # Fail if results are unstable
```

---

## 2. Fast Checks (Local Development)
**Goal**: Quick feedback loop during coding. Accept lower precision for speed.

```toml
# policy-fast.toml

[evaluation]
n = 50                  # Small sample size for speed
alpha = 0.10            # Looser 90% confidence (higher risk of noise)
bootstrap_samples = 1000 # Faster computation

[dispatcher]
kind = "local"
workers = 8             # Aggressive parallelism
sandbox = false         # Skip sandbox overhead (TRUSTED CODE ONLY)

[gate]
method = "wilson"       # Faster analytical approximation (no bootstrap)
threshold = -0.05       # Allow 5% regression (soft gate)
```

---

## 3. Research Mode (Deep Analysis)
**Goal**: Thorough investigation of model behavior, edge cases, and fairness.

```toml
# policy-research.toml

[evaluation]
n = 1000                # Very high sample size
alpha = 0.01            # Strict 99% confidence
bootstrap_samples = 10000
hierarchical = true     # Use hierarchical bayesian priors

[dispatcher]
kind = "queue"          # Distributed execution (Redis/SQS)
workers = 50            # Massive parallelism across cluster
backend = "redis"

[monitors]
list = [
    "profiler",         # Latency & Cost
    "fairness",         # Group-based disparity
    "trend",            # Detect drift over time
    "toxicity"          # Safety checks (if LLM)
]

[gate]
method = "bayesian"     # Full posterior analysis
threshold = 0.02        # Require 2% improvement (superiority)
```


