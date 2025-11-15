# Structured Logging Guide

Metamorphic Guard provides structured JSON logging for observability, debugging, and audit trails. This guide covers configuration, event types, and integration with log aggregation systems.

## Overview

Structured logging emits JSON-formatted events that include:
- **Timestamps**: Unix timestamps for precise event ordering
- **Event types**: Categorized event names (e.g., `run_eval_start`, `case_complete`)
- **Context**: Persistent context fields attached to all events
- **Payloads**: Event-specific data fields

Logs can be written to:
- **stdout**: For containerized deployments and log pipelines
- **File**: For persistent storage and local debugging
- **Custom stream**: For integration with custom handlers

## Quick Start

### Enable Logging via CLI

```bash
# Enable JSON logging to stdout
metamorphic-guard evaluate \
    --task my_task \
    --baseline old.py \
    --candidate new.py \
    --log-json

# Write logs to a file
metamorphic-guard evaluate \
    --task my_task \
    --baseline old.py \
    --candidate new.py \
    --log-file logs/evaluation.jsonl
```

### Enable Logging via Environment Variable

```bash
# Enable JSON logging to stdout
export METAMORPHIC_GUARD_LOG_JSON=1
metamorphic-guard evaluate --task my_task --baseline old.py --candidate new.py
```

### Enable Logging Programmatically

```python
from metamorphic_guard.observability import configure_logging, log_event, add_log_context

# Configure logging to file
configure_logging(enabled=True, path="logs/evaluation.jsonl")

# Add persistent context
add_log_context(
    command="evaluate",
    task="my_task",
    baseline="old.py",
    candidate="new.py",
    run_id="run-12345"
)

# Log events
log_event("run_eval_start", n=400, seed=42)
log_event("case_complete", case_index=0, role="baseline", success=True, duration_ms=125.5)
```

## Configuration

### `configure_logging()`

Configure structured logging behavior at runtime.

```python
from metamorphic_guard.observability import configure_logging

# Enable logging to stdout
configure_logging(enabled=True)

# Enable logging to file
configure_logging(enabled=True, path="logs/evaluation.jsonl")

# Enable logging to custom stream
import io
stream = io.StringIO()
configure_logging(enabled=True, stream=stream)

# Add context during configuration
configure_logging(
    enabled=True,
    path="logs/evaluation.jsonl",
    context={"environment": "production", "team": "ml-platform"}
)
```

**Parameters:**
- `enabled` (Optional[bool]): Enable or disable logging. If None, uses current state.
- `stream` (Optional[TextIO]): Custom stream to write logs to. Defaults to stdout.
- `path` (Optional[str | Path]): Path to log file. Creates parent directories if needed.
- `context` (Optional[Dict[str, Any]]): Initial context to attach to all events.

### `add_log_context()`

Attach persistent key-value pairs to all subsequent log events.

```python
from metamorphic_guard.observability import add_log_context

# Add context fields
add_log_context(
    command="evaluate",
    task="my_task",
    baseline="old.py",
    candidate="new.py",
    run_id="run-12345",
    user="alice",
    environment="staging"
)

# All subsequent log_event() calls will include these fields
log_event("case_start", case_index=0)  # Includes: command, task, baseline, etc.
```

### `clear_log_context()`

Clear all persistent log context.

```python
from metamorphic_guard.observability import clear_log_context

clear_log_context()  # Removes all context fields
```

### `close_logging()`

Close file handles and flush remaining logs. Call this at the end of your program.

```python
from metamorphic_guard.observability import close_logging

close_logging()  # Flushes and closes log file
```

## Event Types

### Evaluation Lifecycle Events

#### `run_eval_start`

Emitted when an evaluation run begins.

```json
{
  "timestamp": 1704067200.123,
  "event": "run_eval_start",
  "command": "evaluate",
  "task": "my_task",
  "n": 400,
  "seed": 42,
  "alpha": 0.05,
  "min_delta": 0.02
}
```

#### `run_eval_complete`

Emitted when an evaluation run completes.

```json
{
  "timestamp": 1704067300.456,
  "event": "run_eval_complete",
  "command": "evaluate",
  "task": "my_task",
  "n": 400,
  "duration_ms": 100333.0,
  "baseline_pass_rate": 0.95,
  "candidate_pass_rate": 0.97,
  "delta_pass_rate": 0.02,
  "decision": {"adopt": true, "reason": "improvement_detected"}
}
```

### Case Execution Events

#### `case_start`

Emitted when a test case execution begins.

```json
{
  "timestamp": 1704067201.234,
  "event": "case_start",
  "case_index": 0,
  "role": "baseline",
  "input": [1, 2, 3]
}
```

#### `case_complete`

Emitted when a test case execution completes.

```json
{
  "timestamp": 1704067201.359,
  "event": "case_complete",
  "case_index": 0,
  "role": "baseline",
  "success": true,
  "duration_ms": 125.5,
  "result": {"output": 6}
}
```

#### `case_failed`

Emitted when a test case execution fails.

```json
{
  "timestamp": 1704067202.567,
  "event": "case_failed",
  "case_index": 1,
  "role": "candidate",
  "error": "TimeoutError",
  "error_message": "Execution exceeded timeout of 2.0s",
  "duration_ms": 2000.0
}
```

### Adaptive Testing Events

#### `adaptive_check`

Emitted during adaptive testing when power is checked.

```json
{
  "timestamp": 1704067250.789,
  "event": "adaptive_check",
  "n": 100,
  "power": 0.87,
  "recommended_n": 150,
  "reason": "insufficient_power"
}
```

#### `early_stop`

Emitted when adaptive testing stops early.

```json
{
  "timestamp": 1704067260.012,
  "event": "early_stop",
  "n": 150,
  "reason": "sufficient_power",
  "confidence": 0.95
}
```

### Queue Events

#### `queue_dispatched`

Emitted when a task is dispatched to the queue.

```json
{
  "timestamp": 1704067203.456,
  "event": "queue_dispatched",
  "job_id": "job-123",
  "task_id": "task-456",
  "case_indices": [0, 1, 2],
  "worker": "worker-1"
}
```

#### `queue_completed`

Emitted when a queued task completes.

```json
{
  "timestamp": 1704067204.789,
  "event": "queue_completed",
  "job_id": "job-123",
  "task_id": "task-456",
  "worker": "worker-1",
  "duration_ms": 1500.0
}
```

#### `queue_requeued`

Emitted when a task is requeued (e.g., due to worker timeout).

```json
{
  "timestamp": 1704067205.123,
  "event": "queue_requeued",
  "job_id": "job-123",
  "task_id": "task-456",
  "reason": "heartbeat_timeout",
  "original_worker": "worker-1"
}
```

### LLM Events

#### `llm_retry`

Emitted when an LLM executor retries a request.

```json
{
  "timestamp": 1704067206.345,
  "event": "llm_retry",
  "provider": "openai",
  "model": "gpt-3.5-turbo",
  "role": "candidate",
  "attempt": 2,
  "error": "rate_limit",
  "error_message": "Rate limit exceeded"
}
```

## Log Format

All log events are JSON Lines (JSONL) format - one JSON object per line.

```jsonl
{"timestamp": 1704067200.123, "event": "run_eval_start", "command": "evaluate", "task": "my_task", "n": 400}
{"timestamp": 1704067201.234, "event": "case_start", "case_index": 0, "role": "baseline"}
{"timestamp": 1704067201.359, "event": "case_complete", "case_index": 0, "role": "baseline", "success": true, "duration_ms": 125.5}
{"timestamp": 1704067300.456, "event": "run_eval_complete", "command": "evaluate", "task": "my_task", "n": 400, "duration_ms": 100333.0}
```

## Integration with Log Aggregation Systems

### Docker / Kubernetes

Logs written to stdout are automatically captured by container orchestration systems.

```dockerfile
# Dockerfile
FROM python:3.11
RUN pip install metamorphic-guard
ENV METAMORPHIC_GUARD_LOG_JSON=1
CMD ["metamorphic-guard", "evaluate", "--task", "my_task", "--baseline", "old.py", "--candidate", "new.py"]
```

```yaml
# Kubernetes deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: metamorphic-guard
spec:
  template:
    spec:
      containers:
      - name: evaluator
        image: my-registry/metamorphic-guard:latest
        env:
        - name: METAMORPHIC_GUARD_LOG_JSON
          value: "1"
        # Logs are automatically collected by cluster logging
```

### File-based Log Collection

For file-based logging, use log rotation and collection tools.

```bash
# Configure logging to file
metamorphic-guard evaluate \
    --task my_task \
    --baseline old.py \
    --candidate new.py \
    --log-file /var/log/metamorphic-guard/evaluation.jsonl

# Use logrotate for rotation
# /etc/logrotate.d/metamorphic-guard
/var/log/metamorphic-guard/*.jsonl {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0644 app app
}
```

### ELK Stack (Elasticsearch, Logstash, Kibana)

Configure Logstash to parse JSONL logs:

```ruby
# logstash.conf
input {
  file {
    path => "/var/log/metamorphic-guard/*.jsonl"
    codec => "json_lines"
    start_position => "beginning"
  }
}

filter {
  json {
    source => "message"
  }
  
  date {
    match => ["timestamp", "UNIX"]
  }
  
  mutate {
    convert => {
      "timestamp" => "float"
    }
  }
}

output {
  elasticsearch {
    hosts => ["localhost:9200"]
    index => "metamorphic-guard-%{+YYYY.MM.dd}"
  }
}
```

### Splunk

Use Splunk's JSON parser for structured logs:

```properties
# props.conf
[metamorphic_guard]
SHOULD_LINEMERGE = false
KV_MODE = json
TRUNCATE = 0

# inputs.conf
[monitor:///var/log/metamorphic-guard/*.jsonl]
sourcetype = metamorphic_guard
index = metamorphic_guard
```

### Datadog

Datadog automatically parses JSON logs. Configure log collection:

```yaml
# datadog.yaml
logs_enabled: true
logs_config:
  container_collect_all: true

# Add service tag
logs_config:
  processing_rules:
    - type: exclude_at_match
      name: exclude_healthchecks
      pattern: healthcheck
```

### CloudWatch Logs (AWS)

For AWS deployments, use CloudWatch Logs agent:

```json
{
  "agent": {
    "metrics_collection_interval": 60
  },
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [
          {
            "file_path": "/var/log/metamorphic-guard/*.jsonl",
            "log_group_name": "/aws/metamorphic-guard/evaluations",
            "log_stream_name": "{instance_id}",
            "timestamp_format": "%Y-%m-%d %H:%M:%S"
          }
        ]
      }
    }
  }
}
```

## Querying Logs

### Using `jq`

Filter and query JSONL logs with `jq`:

```bash
# Count events by type
cat logs/evaluation.jsonl | jq -r '.event' | sort | uniq -c

# Find all failed cases
cat logs/evaluation.jsonl | jq 'select(.event == "case_failed")'

# Calculate average case duration
cat logs/evaluation.jsonl | jq 'select(.event == "case_complete") | .duration_ms' | awk '{sum+=$1; count++} END {print sum/count}'

# Filter by task
cat logs/evaluation.jsonl | jq 'select(.task == "my_task")'

# Extract evaluation summary
cat logs/evaluation.jsonl | jq 'select(.event == "run_eval_complete") | {task, n, duration_ms, decision}'
```

### Using Python

Parse and analyze logs programmatically:

```python
import json
from pathlib import Path
from collections import Counter

# Read log file
log_path = Path("logs/evaluation.jsonl")
events = []
with open(log_path) as f:
    for line in f:
        events.append(json.loads(line))

# Count events by type
event_counts = Counter(e["event"] for e in events)
print("Event counts:", event_counts)

# Find failed cases
failed_cases = [e for e in events if e.get("event") == "case_failed"]
print(f"Failed cases: {len(failed_cases)}")

# Calculate statistics
complete_events = [e for e in events if e.get("event") == "case_complete"]
durations = [e["duration_ms"] for e in complete_events if "duration_ms" in e]
if durations:
    avg_duration = sum(durations) / len(durations)
    print(f"Average case duration: {avg_duration:.2f}ms")
```

## Best Practices

### 1. Use Context for Correlation

Add context at the start of evaluations to correlate all events:

```python
from metamorphic_guard.observability import add_log_context

add_log_context(
    run_id="run-2024-01-15-12345",
    task="my_task",
    baseline="old.py",
    candidate="new.py",
    environment="production",
    team="ml-platform"
)
```

### 2. Log Rotation

Use log rotation to manage disk space:

```python
from pathlib import Path
from datetime import datetime
from metamorphic_guard.observability import configure_logging

# Use timestamped log files
log_path = Path(f"logs/evaluation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl")
configure_logging(enabled=True, path=log_path)
```

### 3. Structured Payloads

Always use structured data in log events:

```python
# Good: Structured data
log_event("case_complete", 
    case_index=0,
    role="baseline",
    success=True,
    duration_ms=125.5,
    metrics={"accuracy": 0.95, "latency": 125.5}
)

# Avoid: Unstructured strings
log_event("case_complete", message="Case 0 completed successfully in 125.5ms")
```

### 4. Error Logging

Include error details in failure events:

```python
try:
    result = execute_case(case)
    log_event("case_complete", case_index=0, success=True, result=result)
except Exception as exc:
    log_event("case_failed",
        case_index=0,
        error=type(exc).__name__,
        error_message=str(exc),
        traceback=traceback.format_exc()
    )
```

### 5. Performance Monitoring

Log timing information for performance analysis:

```python
import time

start_time = time.time()
# ... execute evaluation ...
duration_ms = (time.time() - start_time) * 1000

log_event("run_eval_complete",
    n=400,
    duration_ms=duration_ms,
    cases_per_second=400 / (duration_ms / 1000)
)
```

## Troubleshooting

### Logs Not Appearing

1. **Check if logging is enabled:**
   ```python
   from metamorphic_guard.observability import configure_logging
   configure_logging(enabled=True)  # Explicitly enable
   ```

2. **Check environment variable:**
   ```bash
   echo $METAMORPHIC_GUARD_LOG_JSON  # Should be "1"
   ```

3. **Check file permissions:**
   ```bash
   ls -la logs/evaluation.jsonl  # Ensure writable
   ```

### Log File Not Created

1. **Check parent directory exists:**
   ```python
   from pathlib import Path
   log_path = Path("logs/evaluation.jsonl")
   log_path.parent.mkdir(parents=True, exist_ok=True)  # Create if needed
   ```

2. **Check disk space:**
   ```bash
   df -h .  # Check available space
   ```

### Logs Are Empty

1. **Verify events are being logged:**
   ```python
   from metamorphic_guard.observability import log_event
   log_event("test_event", test=True)  # Should appear in logs
   ```

2. **Check stream flushing:**
   ```python
   from metamorphic_guard.observability import close_logging
   close_logging()  # Flush and close
   ```

## See Also

- [Prometheus Metrics Guide](prometheus.md) - Metrics collection and monitoring
- [Queue Dispatch Guide](queue-dispatch.md) - Distributed execution logging
- [Deployment Guide](deployment.md) - Production deployment considerations

