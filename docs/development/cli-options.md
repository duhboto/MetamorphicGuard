# CLI Options Categorization

This document categorizes all CLI options for the `metamorphic-guard evaluate` command to guide preset creation and help organization.

## Core Options (Required for Basic Usage)

These options are essential for running any evaluation:

- `--task`: Task name to evaluate (required)
- `--baseline`: Path to baseline implementation (required)
- `--candidate`: Path to candidate implementation (required)
- `--n`: Number of test cases to generate (default: 400)
- `--seed`: Random seed for generators (default: 42)
- `--timeout-s`: Timeout per test (seconds) (default: 2.0)
- `--mem-mb`: Memory limit per test (MB) (default: 512)
- `--alpha`: Significance level for bootstrap CI (default: 0.05)
- `--min-delta`: Minimum improvement threshold for adoption (default: 0.02)
- `--min-pass-rate`: Minimum candidate pass rate required (default: 0.80)
- `--violation-cap`: Maximum violations to record (default: 25)
- `--report-dir`: Directory where the JSON report should be written

## Statistical Options

Options related to confidence intervals and statistical methods:

- `--bootstrap-samples`: Bootstrap resamples for CI estimation (default: 1000)
- `--ci-method`: Method for pass-rate delta CI (default: bootstrap)
  - Choices: bootstrap, bootstrap-bca, bootstrap-cluster, bootstrap-cluster-bca, newcombe, wilson, bayesian
- `--rr-ci-method`: Method for relative risk CI (default: log)
- `--bayesian-samples`: Monte Carlo samples for Bayesian CI (default: 5000)
- `--bayesian-hierarchical`: Use hierarchical Beta-Binomial prior
- `--bayesian-posterior-predictive`: Emit Bayesian posterior predictive diagnostics
- `--power-target`: Desired statistical power for detecting improvements (default: 0.8)

## Sequential Testing Options

Options for sequential testing and interim analyses:

- `--sequential-method`: Sequential testing method (default: none)
  - Choices: none, pocock, obrien-fleming, sprt
- `--max-looks`: Maximum number of looks/interim analyses (default: 1)
- `--look-number`: Current look number for sequential testing (default: 1)

## Adaptive Testing Options (Experimental)

Options for adaptive sample size determination:

- `--adaptive`: Enable adaptive sample size determination
- `--adaptive-min-n`: Minimum sample size before first adaptive check (default: 50)
- `--adaptive-interval`: Check power every N samples (default: 50)
- `--adaptive-power-threshold`: Stop early if power exceeds threshold (default: 0.95)
- `--adaptive-max-n`: Maximum sample size for adaptive testing
- `--adaptive-group-sequential`: Use group sequential design
- `--adaptive-sequential-method`: Sequential boundary method for group sequential (default: pocock)
- `--adaptive-max-looks`: Maximum number of looks for group sequential (default: 5)

## Execution Options

Options for controlling how tests are executed:

- `--parallel`: Number of concurrent workers (default: 1)
- `--dispatcher`: Execution dispatcher (default: local)
  - Choices: local, queue
- `--executor`: Sandbox executor to use
- `--executor-config`: JSON string with executor-specific configuration
- `--queue-config`: JSON configuration for queue dispatcher (experimental)
- `--replay-input`: Replay explicit test case inputs from JSON file

## Reporting Options

Options for generating different report formats:

- `--html-report`: Optional destination for HTML summary report
- `--junit-report`: Optional destination for JUnit XML report
- `--export-violations`: Optional destination for JSON violations summary

## Advanced Options

Options for power users and advanced configurations:

- `--config`: Path to TOML file with default option values
- `--policy`: Policy to apply (TOML path or preset)
- `--monitor`: Enable built-in monitors (can be specified multiple times)
- `--mr-fwer`: Apply Holm-Bonferroni correction to MR p-values
- `--mr-hochberg`: Apply Hochberg step-down correction to MR p-values
- `--mr-fdr`: Apply Benjamini-Hochberg FDR correction to MR p-values
- `--no-mr-correction`: Disable multiple comparisons correction for MRs
- `--relation-correction`: Multiple comparisons correction method for relations
- `--shrink-violations`: Enable input shrinking for violations
- `--failed-artifact-limit`: Maximum number of failed artifacts to store
- `--failed-artifact-ttl-days`: TTL in days for failed artifacts
- `--policy-version`: Version identifier for the policy being applied
- `--webhook`: Webhook URL for alerts (can be specified multiple times)
- `--webhook-metadata`: JSON metadata to include with webhook alerts
- `--log-path`: Path to JSON log file
- `--log-context`: JSON context to include in logs
- `--metrics-enabled`: Enable Prometheus metrics endpoint
- `--metrics-port`: Port for metrics endpoint (default: 9090)
- `--metrics-host`: Host for metrics endpoint (default: localhost)
- `--otlp-endpoint`: OpenTelemetry endpoint for trace export
- `--sandbox-plugins`: Enable sandbox plugins for monitoring

## Deprecated Options

Options that are deprecated and will be removed:

- `--improve-delta`: Deprecated alias for `--min-delta` (use `--min-delta` instead)
- `--junit-xml`: Deprecated alias for `--junit-report` (use `--junit-report` instead)

## Summary

- **Core Options**: 12 options (required for basic usage)
- **Statistical Options**: 7 options
- **Sequential Testing Options**: 3 options
- **Adaptive Testing Options**: 8 options (experimental)
- **Execution Options**: 6 options
- **Reporting Options**: 3 options
- **Advanced Options**: 20+ options
- **Deprecated Options**: 2 options

**Total**: ~64 options

## Preset Recommendations

Based on this categorization, the following presets are recommended:

1. **minimal**: Core options only (task, baseline, candidate, n)
2. **standard**: Core + basic statistical options (adds seed, timeout, alpha, min_delta, ci_method)
3. **sequential**: Standard + sequential testing options
4. **adaptive**: Standard + adaptive testing options
5. **full**: All options available (current behavior)



