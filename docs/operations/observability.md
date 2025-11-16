# Observability Defaults and Examples

Metamorphic Guard exposes simple toggles for structured logging and Prometheus metrics.

## Defaults

- Logging: disabled by default. Enable JSON logs with `--log-json` or `METAMORPHIC_GUARD_LOG_JSON=1`.
- Metrics: disabled by default. Enable with `--metrics` (optionally `--metrics-port 9102`).
- Workers inherit the same flags; logs/metrics are emitted per-process.

## Quick Start

```bash
metamorphic-guard evaluate \
  --task top_k \
  --baseline baseline.py \
  --candidate candidate.py \
  --log-json \
  --metrics --metrics-port 9102
```

## Prometheus Scrape Example

Prometheus `scrape_configs` snippet:

```yaml
scrape_configs:
  - job_name: metamorphic-guard
    static_configs:
      - targets: ["localhost:9102"]
```

## CI Tips

- Prefer `--no-log-json` and disable metrics for pure CI test runs to reduce noise.
- For distributed mode, expose the worker metrics ports and aggregate via your scraper.


