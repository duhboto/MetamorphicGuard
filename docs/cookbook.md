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

Tune via `--queue-config`:
- `"adaptive_batching": true` (default) adjusts batch sizes based on worker latency.
- `"initial_batch_size": 2`, `"max_batch_size": 16` limit the adaptive window.
- `"adaptive_compress": true` toggles automatic gzip negotiation; pair with `"compression_threshold_bytes"` for precise cut-overs.
- `"inflight_factor": 3` increases/decreases how many cases stay in flight per worker.

## Advanced Monitors

Enable latency and success-rate tracking with alerts:
```bash
metamorphic-guard \
  --monitor latency:percentile=0.99,alert_ratio=1.2 \
  --monitor success_rate \
  ...
```
HTML reports and JSON output now include monitor summaries.

## Metrics, Provenance & Dashboards

1. **Run with metrics + provenance**
   ```bash
   metamorphic-guard \
     --task top_k \
     --baseline examples/top_k_baseline.py \
     --candidate examples/top_k_improved.py \
     --metrics --metrics-port 9093 --log-json \
     --report-dir reports/ \
     --metric value_mean --metric total_cost
   ```
   - Prometheus endpoint: `http://localhost:9093/metrics`
   - JSON report: `reports/report_<timestamp>.json`
   - `result["metrics"]`: baseline/candidate summaries, bootstrap CIs, paired deltas
   - `provenance.sandbox`: executor fingerprints, runtime metadata, command hashes

2. **Inspect outputs**
   ```bash
   jq '.metrics' reports/report_*.json
   metamorphic-guard provenance-diff reports/report_old.json reports/report_new.json
   ```
   Use the diff command to flag sandbox changes (image digests, capabilities, run state).

3. **Wire into Prometheus / Grafana**
   - Export env vars for long-lived services:
     ```bash
     export METAMORPHIC_GUARD_PROMETHEUS=1
     export METAMORPHIC_GUARD_LOG_JSON=1
     ```
   - Expose the registry via your HTTP exporter: `metamorphic_guard.observability.prometheus_registry()`.
   - Import `docs/grafana/metamorphic-guard-dashboard.json` and add panels for:
     - `metamorphic_queue_pending_tasks`
     - `metamorphic_queue_inflight_cases`
     - `metamorphic_queue_cases_completed_total`
     - Custom metrics derived from `Spec.metrics`.

4. **Reference telemetry metrics**
   - Gauges: `metamorphic_queue_pending_tasks`, `metamorphic_queue_inflight_cases`, `metamorphic_queue_active_workers`
   - Counters: `metamorphic_queue_cases_dispatched_total`, `metamorphic_queue_cases_completed_total`, `metamorphic_queue_cases_requeued_total`, `metamorphic_queue_heartbeats_total`

5. **Operational tips**
   - Append JSON logs via `--log-file observability/run.jsonl` for ingestion.
   - Tune simulation validation strictness with `MG_CI_RUNS`, `MG_CI_TOLERANCE`, `MG_CI_MIN_COVERAGE`.
   - Preserve report JSONs as CI artifacts for downstream auditing and diffing.

## Advanced Monitors & Alerts

- Latency percentiles: `--monitor latency:percentile=0.99,alert_ratio=1.25`
- Fairness gaps: `--monitor fairness:max_gap=0.05` assumes each sandbox result provides a
  `result["group"]` label and raises when the baseline vs candidate success rate gap exceeds the threshold.
- Resource budgets: `--monitor resource:metric=cpu_ms,alert_ratio=1.4` consumes values from
  `result["resource_usage"]["cpu_ms"]` (or top-level keys) and alerts when the candidate mean exceeds the
  baseline by the configured ratio.

Send alert summaries to downstream systems via `--alert-webhook https://hooks.internal.dev/metaguard`.
The webhook receives JSON containing flattened monitor alerts plus run metadata, making it easy to plug into
Slack, PagerDuty, or custom automation.

## Security Hardening & Redaction

- Mask secrets in sandbox output by setting `METAMORPHIC_GUARD_REDACT="(?i)password\s*=\s*\w+"` or by providing `redact_patterns` inside `--executor-config`. Patterns are regular expressions and redact to `[REDACTED]`.
- Structured error fields (`error_type`, `error_code`) identify failure modes like `SANDBOX_TIMEOUT`; key off these when triaging flakes.
- To run workers inside containers, review `deploy/docker-compose.worker.yml`. It provisions Redis plus a read-only worker container that uses the Docker executor for an additional isolation boundary.

## Interactive Init & Plugin Scaffolds

- `metamorphic-guard init --interactive` opens a guided wizard for task name, baseline/candidate paths, distributed mode, and default monitors.
- Create a monitor or dispatcher skeleton via `metamorphic-guard scaffold-plugin --kind monitor --name CustomMonitor --path plugins/custom_monitor.py` and register it through Python entry points.
- Discover and audit extensions with `metamorphic-guard plugin list` (append `--json` for automation) and inspect metadata using `metamorphic-guard plugin info <name>`.
- Add `PLUGIN_METADATA = {"name": "My Monitor", "version": "0.1", "sandbox": True}` to request automatic sandboxing; Coordinators run plugin monitors in isolated subprocesses whenever `--sandbox-plugins` (or metadata `sandbox = true`) is set.

## CI/CD Integration (GitHub Actions)

```