# Prometheus Metrics Guide

Metamorphic Guard exposes Prometheus metrics for monitoring evaluation runs, queue operations, and LLM executor behavior. This guide covers setup, available metrics, and Grafana dashboard integration.

## Overview

Prometheus metrics provide:
- **Counters**: Cumulative metrics (e.g., total cases processed, total retries)
- **Gauges**: Point-in-time values (e.g., pending tasks, active workers)
- **Labels**: Dimensions for filtering and aggregation (e.g., role, status, provider)

Metrics are exposed via HTTP endpoint and can be scraped by Prometheus or integrated with existing monitoring infrastructure.

## Quick Start

### Enable Metrics via CLI

```bash
# Enable metrics and expose on port 9090
metamorphic-guard evaluate \
    --task my_task \
    --baseline old.py \
    --candidate new.py \
    --metrics \
    --metrics-port 9090

# Metrics will be available at http://localhost:9090/metrics
```

### Enable Metrics via Environment Variable

```bash
# Enable metrics
export METAMORPHIC_GUARD_PROMETHEUS=1

# Optionally set port (requires programmatic configuration)
metamorphic-guard evaluate --task my_task --baseline old.py --candidate new.py
```

### Enable Metrics Programmatically

```python
from metamorphic_guard.observability import configure_metrics

# Enable metrics and expose HTTP endpoint
configure_metrics(enabled=True, port=9090, host="0.0.0.0")

# Metrics endpoint: http://localhost:9090/metrics
```

## Installation

### Install Prometheus Client

```bash
# Install prometheus_client package
pip install prometheus_client

# Or install with observability extras
pip install metamorphic-guard[observability]
```

### Verify Installation

```python
from metamorphic_guard.observability import configure_metrics, metrics_enabled

configure_metrics(enabled=True)
assert metrics_enabled() == True
```

## Available Metrics

### Counters

#### `metamorphic_cases_total`

Total evaluation cases processed, labeled by role and status.

**Labels:**
- `role`: `"baseline"` or `"candidate"`
- `status`: `"success"`, `"failure"`, `"timeout"`, or `"error"`

**Example:**
```
metamorphic_cases_total{role="baseline",status="success"} 380
metamorphic_cases_total{role="candidate",status="success"} 395
metamorphic_cases_total{role="baseline",status="failure"} 20
metamorphic_cases_total{role="candidate",status="failure"} 5
```

**Usage:**
```promql
# Total cases processed
sum(metamorphic_cases_total)

# Success rate by role
sum(metamorphic_cases_total{status="success"}) by (role) / 
sum(metamorphic_cases_total) by (role)

# Failure rate
sum(metamorphic_cases_total{status="failure"}) / 
sum(metamorphic_cases_total)
```

#### `metamorphic_queue_cases_dispatched_total`

Total evaluation cases dispatched to the queue.

**Example:**
```
metamorphic_queue_cases_dispatched_total 1000
```

**Usage:**
```promql
# Dispatch rate
rate(metamorphic_queue_cases_dispatched_total[5m])

# Total dispatched
sum(metamorphic_queue_cases_dispatched_total)
```

#### `metamorphic_queue_cases_completed_total`

Total evaluation cases completed by workers.

**Example:**
```
metamorphic_queue_cases_completed_total 950
```

**Usage:**
```promql
# Completion rate
rate(metamorphic_queue_cases_completed_total[5m])

# Completion ratio
sum(metamorphic_queue_cases_completed_total) / 
sum(metamorphic_queue_cases_dispatched_total)
```

#### `metamorphic_queue_cases_requeued_total`

Total evaluation cases requeued after lease expiry or heartbeat timeout.

**Example:**
```
metamorphic_queue_cases_requeued_total 50
```

**Usage:**
```promql
# Requeue rate
rate(metamorphic_queue_cases_requeued_total[5m])

# Requeue ratio (indicates worker health)
sum(metamorphic_queue_cases_requeued_total) / 
sum(metamorphic_queue_cases_dispatched_total)
```

#### `metamorphic_llm_retries_total`

Total retry attempts performed by LLM executors, labeled by provider and role.

**Labels:**
- `provider`: LLM provider (e.g., `"openai"`, `"anthropic"`)
- `role`: `"baseline"` or `"candidate"`

**Example:**
```
metamorphic_llm_retries_total{provider="openai",role="baseline"} 10
metamorphic_llm_retries_total{provider="openai",role="candidate"} 15
```

**Usage:**
```promql
# Retry rate by provider
rate(metamorphic_llm_retries_total[5m]) by (provider)

# Retry rate by role
rate(metamorphic_llm_retries_total[5m]) by (role)
```

### Gauges

#### `metamorphic_queue_pending_tasks`

Number of queue tasks pending dispatch.

**Example:**
```
metamorphic_queue_pending_tasks 25
```

**Usage:**
```promql
# Current pending tasks
metamorphic_queue_pending_tasks

# Average pending tasks over time
avg_over_time(metamorphic_queue_pending_tasks[5m])
```

#### `metamorphic_queue_inflight_cases`

Number of evaluation cases currently in flight (dispatched but not completed).

**Example:**
```
metamorphic_queue_inflight_cases 50
```

**Usage:**
```promql
# Current in-flight cases
metamorphic_queue_inflight_cases

# Average in-flight cases
avg_over_time(metamorphic_queue_inflight_cases[5m])
```

#### `metamorphic_queue_active_workers`

Number of active workers recently seen via heartbeats.

**Example:**
```
metamorphic_queue_active_workers 5
```

**Usage:**
```promql
# Current active workers
metamorphic_queue_active_workers

# Worker availability
metamorphic_queue_active_workers > 0
```

## Configuration

### `configure_metrics()`

Configure Prometheus metrics collection and HTTP endpoint.

```python
from metamorphic_guard.observability import configure_metrics

# Enable metrics (no HTTP endpoint)
configure_metrics(enabled=True)

# Enable metrics and expose HTTP endpoint
configure_metrics(enabled=True, port=9090, host="0.0.0.0")

# Disable metrics
configure_metrics(enabled=False)
```

**Parameters:**
- `enabled` (Optional[bool]): Enable or disable metrics. If None, uses current state.
- `port` (Optional[int]): Port for HTTP metrics endpoint. If None, no endpoint is exposed.
- `host` (str): Host address for HTTP endpoint. Defaults to `"0.0.0.0"`.

### `prometheus_registry()`

Get the Prometheus registry for custom metric integration.

```python
from metamorphic_guard.observability import prometheus_registry, configure_metrics

configure_metrics(enabled=True)
registry = prometheus_registry()

# Use registry with custom metrics
from prometheus_client import Counter
custom_counter = Counter("my_custom_metric", "Description", registry=registry)
```

## Prometheus Setup

### Basic Prometheus Configuration

Add Metamorphic Guard to your `prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'metamorphic-guard'
    static_configs:
      - targets: ['localhost:9090']
        labels:
          service: 'metamorphic-guard'
          environment: 'production'
```

### Kubernetes Service Discovery

For Kubernetes deployments, use service discovery:

```yaml
scrape_configs:
  - job_name: 'metamorphic-guard'
    kubernetes_sd_configs:
      - role: pod
        namespaces:
          names:
            - default
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_label_app]
        regex: metamorphic-guard
        action: keep
      - source_labels: [__meta_kubernetes_pod_ip]
        target_label: __address__
        replacement: '${1}:9090'
```

### Docker Compose

For Docker Compose deployments:

```yaml
version: '3.8'
services:
  metamorphic-guard:
    image: my-registry/metamorphic-guard:latest
    ports:
      - "9090:9090"
    environment:
      - METAMORPHIC_GUARD_PROMETHEUS=1
    command: >
      metamorphic-guard evaluate
      --task my_task
      --baseline old.py
      --candidate new.py
      --metrics
      --metrics-port 9090

  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    ports:
      - "9091:9090"
    depends_on:
      - metamorphic-guard

volumes:
  prometheus-data:
```

## Grafana Dashboard

### Import Dashboard

A pre-configured Grafana dashboard is available at `docs/grafana/metamorphic-guard-dashboard.json`.

**Import Steps:**
1. Open Grafana → Dashboards → Import
2. Upload `docs/grafana/metamorphic-guard-dashboard.json`
3. Select Prometheus data source
4. Click "Import"

### Dashboard Panels

The dashboard includes:

1. **Evaluation Cases**: Total cases processed by role and status
2. **Case Throughput**: Rate of cases processed over time
3. **Queue Metrics**: Pending, in-flight, and completed cases
4. **Worker Health**: Active workers and requeue rate
5. **LLM Retries**: Retry attempts by provider and role
6. **Success Rates**: Pass rates for baseline and candidate

### Custom Queries

#### Case Success Rate

```promql
sum(rate(metamorphic_cases_total{status="success"}[5m])) by (role) /
sum(rate(metamorphic_cases_total[5m])) by (role)
```

#### Queue Efficiency

```promql
sum(rate(metamorphic_queue_cases_completed_total[5m])) /
sum(rate(metamorphic_queue_cases_dispatched_total[5m]))
```

#### Worker Utilization

```promql
sum(rate(metamorphic_queue_cases_completed_total[5m])) /
metamorphic_queue_active_workers
```

#### Requeue Rate (Health Indicator)

```promql
sum(rate(metamorphic_queue_cases_requeued_total[5m])) /
sum(rate(metamorphic_queue_cases_dispatched_total[5m]))
```

## Alerting Rules

### Pre-configured Alert Rules

A comprehensive set of alerting rules is available at `docs/grafana/alerting-rules.yml`. These rules cover:

**Critical Alerts:**
- No active workers
- Queue backend down

**Warning Alerts:**
- High requeue rate (>20%)
- Queue backlog (>1000 tasks)
- High failure rate (>10%)
- Low worker utilization
- High LLM retry rate
- Worker memory pressure
- Slow evaluation progress

**Info Alerts:**
- Evaluation started
- Worker scale events

### Installation

Copy the alert rules file to your Prometheus configuration directory:

```bash
# Copy alert rules
cp docs/grafana/alerting-rules.yml /etc/prometheus/rules/

# Update prometheus.yml to include rules
```

```yaml
# prometheus.yml
rule_files:
  - "/etc/prometheus/rules/*.yml"

scrape_configs:
  # ... existing scrape configs ...
```

### Custom Alert Rules

You can customize alert thresholds based on your needs:

```yaml
groups:
  - name: metamorphic_guard_custom
    interval: 30s
    rules:
      # Custom alert: High failure rate for your specific threshold
      - alert: HighCaseFailureRate
        expr: |
          sum(rate(metamorphic_cases_total{status="failure"}[5m])) /
          sum(rate(metamorphic_cases_total[5m])) > 0.05  # 5% threshold
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High case failure rate detected"
          description: "Failure rate is {{ $value | humanizePercentage }}"
```

See `docs/grafana/alerting-rules.yml` for the complete set of pre-configured rules.

### Alertmanager Configuration

Configure Alertmanager to route alerts:

```yaml
# alertmanager.yml
route:
  receiver: 'default'
  routes:
    - match:
        severity: critical
      receiver: 'pagerduty'
    - match:
        severity: warning
      receiver: 'slack'

receivers:
  - name: 'default'
    webhook_configs:
      - url: 'http://localhost:5001/webhook'

  - name: 'pagerduty'
    pagerduty_configs:
      - service_key: 'YOUR_PAGERDUTY_KEY'

  - name: 'slack'
    slack_configs:
      - api_url: 'YOUR_SLACK_WEBHOOK_URL'
        channel: '#alerts'
```

## Programmatic Usage

### Incrementing Metrics

```python
from metamorphic_guard.observability import (
    configure_metrics,
    increment_metric,
    increment_llm_retries,
)

# Configure metrics
configure_metrics(enabled=True, port=9090)

# Increment case counter
increment_metric(role="baseline", status="success")
increment_metric(role="candidate", status="failure")

# Increment LLM retry counter
increment_llm_retries(provider="openai", role="candidate", count=1)
```

### Observing Gauges

```python
from metamorphic_guard.observability import (
    configure_metrics,
    observe_queue_pending_tasks,
    observe_queue_inflight,
    observe_worker_count,
)

# Configure metrics
configure_metrics(enabled=True, port=9090)

# Update gauge values
observe_queue_pending_tasks(count=25)
observe_queue_inflight(count=50)
observe_worker_count(count=5)
```

### Queue Metrics

```python
from metamorphic_guard.observability import (
    configure_metrics,
    increment_queue_dispatched,
    increment_queue_completed,
    increment_queue_requeued,
)

configure_metrics(enabled=True, port=9090)

# Track queue operations
increment_queue_dispatched(count=10)
increment_queue_completed(count=8)
increment_queue_requeued(count=2)  # 2 cases requeued due to timeout
```

## Best Practices

### 1. Use Appropriate Scrape Intervals

Set scrape intervals based on evaluation duration:

```yaml
# For short evaluations (< 1 hour)
scrape_interval: 15s

# For long evaluations (> 1 hour)
scrape_interval: 1m
```

### 2. Label Aggregation

Use labels for filtering and aggregation:

```promql
# Filter by role
metamorphic_cases_total{role="baseline"}

# Aggregate by status
sum(metamorphic_cases_total) by (status)

# Multi-dimensional aggregation
sum(metamorphic_cases_total) by (role, status)
```

### 3. Rate Calculations

Use `rate()` for counters to get per-second rates:

```promql
# Cases per second
rate(metamorphic_cases_total[5m])

# Average rate over longer window
rate(metamorphic_cases_total[15m])
```

### 4. Metric Retention

Configure Prometheus retention for long-term analysis:

```yaml
# prometheus.yml
storage:
  tsdb:
    retention.time: 30d
    retention.size: 50GB
```

### 5. High Availability

For production deployments, use Prometheus HA:

- **Prometheus**: Run multiple Prometheus instances
- **Thanos**: Long-term storage and query federation
- **Cortex**: Horizontally scalable Prometheus

## Troubleshooting

### Metrics Not Appearing

1. **Check if metrics are enabled:**
   ```python
   from metamorphic_guard.observability import metrics_enabled
   assert metrics_enabled() == True
   ```

2. **Check HTTP endpoint:**
   ```bash
   curl http://localhost:9090/metrics
   ```

3. **Check Prometheus client installation:**
   ```bash
   pip list | grep prometheus-client
   ```

### Port Already in Use

If the metrics port is already in use:

```python
# Use a different port
configure_metrics(enabled=True, port=9091)

# Or disable HTTP endpoint and use registry directly
configure_metrics(enabled=True)  # No port = no HTTP endpoint
registry = prometheus_registry()
# Integrate with existing Prometheus setup
```

### Missing Metrics

Some metrics are only available in specific contexts:

- **Queue metrics**: Only available when using queue dispatcher
- **LLM retry metrics**: Only available when using LLM executors
- **Worker metrics**: Only available in distributed deployments

### Performance Impact

Metrics collection has minimal overhead, but for high-throughput scenarios:

1. **Use longer scrape intervals** to reduce Prometheus load
2. **Disable metrics** for non-production runs
3. **Use metric sampling** for very high-frequency events

## Integration Examples

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: metamorphic-guard
spec:
  replicas: 1
  template:
    metadata:
      labels:
        app: metamorphic-guard
    spec:
      containers:
      - name: evaluator
        image: my-registry/metamorphic-guard:latest
        ports:
        - containerPort: 9090
          name: metrics
        env:
        - name: METAMORPHIC_GUARD_PROMETHEUS
          value: "1"
        command:
        - metamorphic-guard
        - evaluate
        - --task
        - my_task
        - --baseline
        - old.py
        - --candidate
        - new.py
        - --metrics
        - --metrics-port
        - "9090"
---
apiVersion: v1
kind: Service
metadata:
  name: metamorphic-guard
  labels:
    app: metamorphic-guard
spec:
  ports:
  - port: 9090
    targetPort: 9090
    name: metrics
  selector:
    app: metamorphic-guard
```

### Docker Deployment

```dockerfile
FROM python:3.11
RUN pip install metamorphic-guard[observability]
ENV METAMORPHIC_GUARD_PROMETHEUS=1
EXPOSE 9090
CMD ["metamorphic-guard", "evaluate", "--task", "my_task", "--baseline", "old.py", "--candidate", "new.py", "--metrics", "--metrics-port", "9090"]
```

## See Also

- [Structured Logging Guide](logging.md) - JSON logging for event tracking
- [Queue Dispatch Guide](queue-dispatch.md) - Distributed execution metrics
- [Deployment Guide](deployment.md) - Production deployment considerations


