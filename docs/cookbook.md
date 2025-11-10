# Metamorphic Guard Cookbook

A few opinionated recipes for real-world adoption.

## Distributed Evaluations

1. Launch Redis (`docker run -p 6379:6379 redis`).
2. Start a worker fleet:
   ```bash
   metamorphic-guard-worker --backend redis --queue-config '{"url":"redis://localhost:6379/0"}'
   ```
3. Trigger an evaluation:
   ```bash
   metamorphic-guard \
     --dispatcher queue \
     --queue-config '{"backend":"redis","url":"redis://localhost:6379/0"}' \
     --task top_k --baseline prod.py --candidate new.py
   ```

## Advanced Monitors

Enable latency and success-rate tracking with alerts:
```bash
metamorphic-guard \
  --monitor latency:percentile=0.99,alert_ratio=1.2 \
  --monitor success_rate \
  ...
```
HTML reports and JSON output now include monitor summaries.

## Prometheus & Logging

```
export METAMORPHIC_GUARD_PROMETHEUS=1
export METAMORPHIC_GUARD_LOG_JSON=1
metamorphic-guard ...
```
Expose `metamorphic_guard.observability.prometheus_registry()` via your preferred HTTP exporter.

## CI/CD Integration (GitHub Actions)

```yaml
name: Metamorphic Guard

on: [pull_request]

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install .
      - run: metamorphic-guard init --distributed --monitor latency
      - run: metamorphic-guard --config metamorphic_guard.toml --report-dir reports/
```

Review generated reports in the `reports/` artifact and gate merges on the exit status.
