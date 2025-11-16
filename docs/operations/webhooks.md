# Webhook Alerts Guide

Metamorphic Guard can send webhook alerts when monitors detect issues during evaluation. This guide covers webhook configuration, payload formats, and integration with popular notification systems.

## Overview

Webhook alerts are triggered when monitors detect:
- **Property violations**: Candidate fails properties that baseline passes
- **Metamorphic relation violations**: Candidate violates metamorphic relations
- **Performance regressions**: Latency, memory, or other metrics exceed thresholds
- **Safety violations**: Toxicity, bias, or PII detection
- **Compliance failures**: Regulatory or policy violations

Alerts are sent as HTTP POST requests with JSON payloads containing alert details and evaluation metadata.

## Quick Start

### Basic Configuration

```bash
# Send alerts to a webhook URL
metamorphic-guard evaluate \
    --task my_task \
    --baseline old.py \
    --candidate new.py \
    --alert-webhook https://hooks.example.com/alerts \
    --monitor latency
```

### Multiple Webhooks

```bash
# Send to multiple webhook endpoints
metamorphic-guard evaluate \
    --task my_task \
    --baseline old.py \
    --candidate new.py \
    --alert-webhook https://hooks.slack.com/services/... \
    --alert-webhook https://hooks.pagerduty.com/... \
    --monitor latency
```

## Alert Payload Structure

### Standard Webhook Payload

All webhook alerts use this structure:

```json
{
  "alerts": [
    {
      "monitor": "LatencyMonitor",
      "type": "latency_regression",
      "severity": "warning",
      "message": "Candidate latency exceeds baseline by 50%",
      "baseline_value": 100.5,
      "candidate_value": 150.2,
      "threshold": 120.0
    }
  ],
  "metadata": {
    "task": "my_task",
    "decision": {
      "adopt": false,
      "reason": "regression_detected"
    },
    "run_id": "run-2024-01-15-12345",
    "policy_version": "v1.2.3",
    "sandbox_plugins": true
  }
}
```

### Alert Fields

Each alert in the `alerts` array contains:

- `monitor` (str): Monitor identifier (e.g., `"LatencyMonitor"`, `"BiasMonitor"`)
- `type` (str): Alert type (e.g., `"latency_regression"`, `"bias_detected"`)
- `severity` (str): Alert severity (`"info"`, `"warning"`, `"error"`, `"critical"`)
- `message` (str): Human-readable alert message
- Additional monitor-specific fields (e.g., `baseline_value`, `candidate_value`, `threshold`)

### Metadata Fields

The `metadata` object contains evaluation context:

- `task` (str): Task name
- `decision` (dict): Adoption decision with `adopt` (bool) and `reason` (str)
- `run_id` (str): Unique run identifier
- `policy_version` (str, optional): Policy version applied
- `sandbox_plugins` (bool): Whether sandboxing was enabled

## Monitor Alert Types

### Latency Monitor

```json
{
  "monitor": "LatencyMonitor",
  "type": "latency_regression",
  "severity": "warning",
  "message": "Candidate latency exceeds baseline by 50%",
  "baseline_p50": 100.5,
  "candidate_p50": 150.2,
  "baseline_p95": 200.0,
  "candidate_p95": 300.0,
  "threshold": 120.0
}
```

### Bias Monitor

```json
{
  "monitor": "BiasMonitor",
  "type": "bias_detected",
  "severity": "error",
  "message": "Bias detected in candidate output",
  "protected_groups": ["gender", "race"],
  "bias_score": 0.75,
  "threshold": 0.5
}
```

### Toxicity Monitor

```json
{
  "monitor": "ToxicityMonitor",
  "type": "toxicity_detected",
  "severity": "error",
  "message": "Toxic content detected in candidate output",
  "toxicity_score": 0.85,
  "threshold": 0.7,
  "case_index": 42
}
```

### PII Monitor

```json
{
  "monitor": "PIIMonitor",
  "type": "pii_detected",
  "severity": "warning",
  "message": "PII detected in candidate output",
  "pii_types": ["email", "phone"],
  "case_index": 15
}
```

### Compliance Monitor

```json
{
  "monitor": "ComplianceMonitor",
  "type": "compliance_violation",
  "severity": "critical",
  "message": "GDPR compliance violation detected",
  "rule": "gdpr_data_retention",
  "violation_details": {
    "data_type": "personal_data",
    "retention_period": "exceeded"
  }
}
```

## Integration Examples

### Slack Integration

#### Using Slack Webhooks

```bash
# Get webhook URL from Slack: https://api.slack.com/messaging/webhooks
metamorphic-guard evaluate \
    --task my_task \
    --baseline old.py \
    --candidate new.py \
    --alert-webhook https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXX \
    --monitor latency
```

#### Custom Slack Handler

Create a webhook handler that formats alerts for Slack:

```python
from flask import Flask, request
import json

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def slack_webhook():
    payload = request.json
    alerts = payload.get('alerts', [])
    metadata = payload.get('metadata', {})
    
    # Format Slack message
    text = f"🚨 Metamorphic Guard Alert: {metadata.get('task', 'unknown')}"
    attachments = []
    
    for alert in alerts:
        color = {
            'info': '#36a64f',
            'warning': '#ffa500',
            'error': '#ff0000',
            'critical': '#8b0000'
        }.get(alert.get('severity', 'info'), '#36a64f')
        
        attachments.append({
            'color': color,
            'title': alert.get('type', 'Alert'),
            'text': alert.get('message', ''),
            'fields': [
                {'title': 'Monitor', 'value': alert.get('monitor', 'Unknown'), 'short': True},
                {'title': 'Severity', 'value': alert.get('severity', 'info'), 'short': True},
            ]
        })
    
    # Send to Slack
    slack_payload = {
        'text': text,
        'attachments': attachments
    }
    
    # Forward to Slack webhook
    import urllib.request
    slack_url = 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
    data = json.dumps(slack_payload).encode('utf-8')
    urllib.request.urlopen(
        urllib.request.Request(slack_url, data=data, headers={'Content-Type': 'application/json'})
    )
    
    return {'status': 'ok'}

if __name__ == '__main__':
    app.run(port=5000)
```

### PagerDuty Integration

#### Using PagerDuty Events API

```python
from metamorphic_guard.notifications import send_pagerduty_alert

# Send PagerDuty alert
send_pagerduty_alert(
    integration_key="YOUR_INTEGRATION_KEY",
    summary="Metamorphic Guard: Regression detected",
    source="metamorphic-guard",
    severity="warning",
    metadata={
        "task": "my_task",
        "decision": {"adopt": False, "reason": "regression_detected"},
        "run_id": "run-12345"
    }
)
```

#### Custom PagerDuty Webhook Handler

```python
from flask import Flask, request
import json
import urllib.request

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def pagerduty_webhook():
    payload = request.json
    alerts = payload.get('alerts', [])
    metadata = payload.get('metadata', {})
    
    # Determine severity from alerts
    severities = [a.get('severity', 'info') for a in alerts]
    max_severity = 'critical' if 'critical' in severities else \
                   'error' if 'error' in severities else \
                   'warning' if 'warning' in severities else 'info'
    
    # Send to PagerDuty
    pagerduty_payload = {
        'routing_key': 'YOUR_INTEGRATION_KEY',
        'event_action': 'trigger',
        'payload': {
            'summary': f"Metamorphic Guard: {len(alerts)} alert(s) for {metadata.get('task', 'unknown')}",
            'source': 'metamorphic-guard',
            'severity': max_severity,
            'custom_details': {
                'alerts': alerts,
                'metadata': metadata
            }
        }
    }
    
    data = json.dumps(pagerduty_payload).encode('utf-8')
    urllib.request.urlopen(
        urllib.request.Request(
            'https://events.pagerduty.com/v2/enqueue',
            data=data,
            headers={'Content-Type': 'application/json'}
        )
    )
    
    return {'status': 'ok'}

if __name__ == '__main__':
    app.run(port=5000)
```

### Datadog Integration

#### Using Datadog Events API

```python
from metamorphic_guard.notifications import publish_datadog_event

# Publish Datadog event
publish_datadog_event(
    api_key="YOUR_DATADOG_API_KEY",
    title="Metamorphic Guard: Regression Detected",
    text="Candidate failed evaluation with regression",
    tags=["metamorphic-guard", "regression", "my_task"]
)
```

#### Custom Datadog Webhook Handler

```python
from flask import Flask, request
import json
import urllib.request

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def datadog_webhook():
    payload = request.json
    alerts = payload.get('alerts', [])
    metadata = payload.get('metadata', {})
    
    # Create Datadog event
    datadog_payload = {
        'title': f"Metamorphic Guard: {len(alerts)} alert(s)",
        'text': json.dumps({'alerts': alerts, 'metadata': metadata}, indent=2),
        'tags': [
            'metamorphic-guard',
            metadata.get('task', 'unknown'),
            f"adopt:{metadata.get('decision', {}).get('adopt', False)}"
        ]
    }
    
    data = json.dumps(datadog_payload).encode('utf-8')
    urllib.request.urlopen(
        urllib.request.Request(
            'https://api.datadoghq.com/api/v1/events',
            data=data,
            headers={
                'Content-Type': 'application/json',
                'DD-API-KEY': 'YOUR_DATADOG_API_KEY'
            }
        )
    )
    
    return {'status': 'ok'}

if __name__ == '__main__':
    app.run(port=5000)
```

### Jira Integration

#### Using Jira REST API

```python
from metamorphic_guard.notifications import create_jira_issue

# Create Jira issue
create_jira_issue(
    config={
        'url': 'https://your-domain.atlassian.net',
        'user': 'your-email@example.com',
        'token': 'YOUR_API_TOKEN',
        'project': 'PROJ',
        'issue_type': 'Bug'
    },
    alert={
        'summary': 'Metamorphic Guard: Regression detected',
        'message': 'Candidate failed evaluation',
        'severity': 'warning'
    }
)
```

### Microsoft Teams Integration

```python
from flask import Flask, request
import json
import urllib.request

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def teams_webhook():
    payload = request.json
    alerts = payload.get('alerts', [])
    metadata = payload.get('metadata', {})
    
    # Format Teams message
    facts = []
    for alert in alerts:
        facts.append({'name': 'Monitor', 'value': alert.get('monitor', 'Unknown')})
        facts.append({'name': 'Type', 'value': alert.get('type', 'Unknown')})
        facts.append({'name': 'Severity', 'value': alert.get('severity', 'info')})
        facts.append({'name': 'Message', 'value': alert.get('message', '')})
    
    teams_payload = {
        '@type': 'MessageCard',
        '@context': 'https://schema.org/extensions',
        'summary': f"Metamorphic Guard: {len(alerts)} alert(s)",
        'themeColor': '0078D4',
        'title': f"Metamorphic Guard Alert: {metadata.get('task', 'unknown')}",
        'sections': [{
            'activityTitle': 'Evaluation Alert',
            'facts': facts,
            'markdown': True
        }]
    }
    
    data = json.dumps(teams_payload).encode('utf-8')
    urllib.request.urlopen(
        urllib.request.Request(
            'YOUR_TEAMS_WEBHOOK_URL',
            data=data,
            headers={'Content-Type': 'application/json'}
        )
    )
    
    return {'status': 'ok'}

if __name__ == '__main__':
    app.run(port=5000)
```

### Discord Integration

```python
from flask import Flask, request
import json
import urllib.request

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def discord_webhook():
    payload = request.json
    alerts = payload.get('alerts', [])
    metadata = payload.get('metadata', {})
    
    # Format Discord embed
    embeds = []
    for alert in alerts:
        color = {
            'info': 0x36a64f,
            'warning': 0xffa500,
            'error': 0xff0000,
            'critical': 0x8b0000
        }.get(alert.get('severity', 'info'), 0x36a64f)
        
        embeds.append({
            'title': alert.get('type', 'Alert'),
            'description': alert.get('message', ''),
            'color': color,
            'fields': [
                {'name': 'Monitor', 'value': alert.get('monitor', 'Unknown'), 'inline': True},
                {'name': 'Severity', 'value': alert.get('severity', 'info'), 'inline': True},
            ],
            'footer': {'text': f"Task: {metadata.get('task', 'unknown')}"}
        })
    
    discord_payload = {
        'content': f"🚨 **Metamorphic Guard Alert** ({len(alerts)} alert(s))",
        'embeds': embeds
    }
    
    data = json.dumps(discord_payload).encode('utf-8')
    urllib.request.urlopen(
        urllib.request.Request(
            'YOUR_DISCORD_WEBHOOK_URL',
            data=data,
            headers={'Content-Type': 'application/json'}
        )
    )
    
    return {'status': 'ok'}

if __name__ == '__main__':
    app.run(port=5000)
```

## Programmatic Usage

### Collecting Alerts

```python
from metamorphic_guard.notifications import collect_alerts

# Collect alerts from evaluation result
result = run_eval(...)
alerts = collect_alerts(result.get("monitors", {}))

# Process alerts
for alert in alerts:
    print(f"Alert: {alert['monitor']} - {alert['message']}")
```

### Sending Webhook Alerts

```python
from metamorphic_guard.notifications import send_webhook_alerts

# Send alerts to webhook
alerts = [
    {
        "monitor": "LatencyMonitor",
        "type": "latency_regression",
        "severity": "warning",
        "message": "Candidate latency exceeds baseline"
    }
]

metadata = {
    "task": "my_task",
    "decision": {"adopt": False, "reason": "regression_detected"},
    "run_id": "run-12345"
}

send_webhook_alerts(
    alerts=alerts,
    webhooks=["https://hooks.example.com/alerts"],
    metadata=metadata
)
```

## Configuration

### CLI Configuration

```bash
# Single webhook
--alert-webhook https://hooks.example.com/alerts

# Multiple webhooks
--alert-webhook https://hooks.slack.com/services/...
--alert-webhook https://hooks.pagerduty.com/...
```

### Config File

```toml
[alerts]
webhooks = [
    "https://hooks.slack.com/services/...",
    "https://hooks.pagerduty.com/..."
]
```

### Programmatic Configuration

```python
from metamorphic_guard import run_eval

result = run_eval(
    task_name="my_task",
    baseline_path="old.py",
    candidate_path="new.py",
    alert_webhooks=[
        "https://hooks.slack.com/services/...",
        "https://hooks.pagerduty.com/..."
    ],
    alert_metadata={
        "pipeline": "ci",
        "environment": "production",
        "team": "ml-platform"
    }
)
```

## Best Practices

### 1. Use Dedicated Webhook Handlers

Create dedicated webhook handlers that format alerts for your notification system:

```python
# webhook_handler.py
from flask import Flask, request
import json

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    payload = request.json
    # Format and forward to your notification system
    # ...
    return {'status': 'ok'}
```

### 2. Filter Alerts by Severity

Only send critical alerts to on-call systems:

```python
from flask import Flask, request
import json

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    payload = request.json
    alerts = payload.get('alerts', [])
    
    # Filter critical alerts
    critical_alerts = [a for a in alerts if a.get('severity') == 'critical']
    
    if critical_alerts:
        # Send to PagerDuty
        send_to_pagerduty(critical_alerts)
    
    # Send all alerts to Slack
    send_to_slack(alerts)
    
    return {'status': 'ok'}
```

### 3. Add Authentication

Secure webhook endpoints with authentication:

```python
from flask import Flask, request
import hmac
import hashlib

app = Flask(__name__)
WEBHOOK_SECRET = 'your-secret-key'

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    # Verify signature
    signature = request.headers.get('X-Signature')
    if not signature:
        return {'error': 'Missing signature'}, 401
    
    expected_signature = hmac.new(
        WEBHOOK_SECRET.encode(),
        request.data,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(signature, expected_signature):
        return {'error': 'Invalid signature'}, 401
    
    # Process webhook
    payload = request.json
    # ...
    return {'status': 'ok'}
```

### 4. Implement Retry Logic

Handle webhook failures gracefully:

```python
import time
import urllib.request
import urllib.error

def send_webhook_with_retry(url, payload, max_retries=3):
    for attempt in range(max_retries):
        try:
            data = json.dumps(payload).encode('utf-8')
            request = urllib.request.Request(
                url,
                data=data,
                headers={'Content-Type': 'application/json'}
            )
            urllib.request.urlopen(request, timeout=5)
            return True
        except (urllib.error.URLError, urllib.error.HTTPError) as exc:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                logger.error(f"Failed to send webhook after {max_retries} attempts: {exc}")
                return False
    return False
```

### 5. Rate Limiting

Implement rate limiting to prevent webhook spam:

```python
from collections import defaultdict
from datetime import datetime, timedelta

class RateLimiter:
    def __init__(self, max_calls=10, window_seconds=60):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self.calls = defaultdict(list)
    
    def is_allowed(self, key):
        now = datetime.now()
        window_start = now - timedelta(seconds=self.window_seconds)
        
        # Remove old calls
        self.calls[key] = [t for t in self.calls[key] if t > window_start]
        
        # Check limit
        if len(self.calls[key]) >= self.max_calls:
            return False
        
        # Record call
        self.calls[key].append(now)
        return True

rate_limiter = RateLimiter(max_calls=10, window_seconds=60)

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    task = request.json.get('metadata', {}).get('task', 'unknown')
    
    if not rate_limiter.is_allowed(task):
        return {'error': 'Rate limit exceeded'}, 429
    
    # Process webhook
    # ...
    return {'status': 'ok'}
```

## Troubleshooting

### Webhooks Not Sending

1. **Check webhook URL:**
   ```bash
   curl -X POST https://hooks.example.com/alerts \
       -H "Content-Type: application/json" \
       -d '{"test": true}'
   ```

2. **Check logs:**
   ```bash
   # Look for webhook errors in logs
   grep "Failed to send alert" logs/evaluation.jsonl
   ```

3. **Verify alerts exist:**
   ```python
   from metamorphic_guard.notifications import collect_alerts
   
   result = run_eval(...)
   alerts = collect_alerts(result.get("monitors", {}))
   print(f"Alerts: {len(alerts)}")
   ```

### Webhook Timeouts

If webhooks timeout:

1. **Increase timeout:**
   ```python
   import urllib.request
   
   request = urllib.request.Request(url, data=data, headers=headers)
   urllib.request.urlopen(request, timeout=30)  # 30 second timeout
   ```

2. **Use async webhooks:**
   ```python
   import asyncio
   import aiohttp
   
   async def send_webhook_async(url, payload):
       async with aiohttp.ClientSession() as session:
           async with session.post(url, json=payload, timeout=30) as response:
               return await response.json()
   ```

### Webhook Authentication

If webhook requires authentication:

```python
import urllib.request
import base64

# Basic auth
username = "user"
password = "pass"
credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Basic {credentials}"
}

# Bearer token
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {token}"
}

request = urllib.request.Request(url, data=data, headers=headers)
urllib.request.urlopen(request)
```

## See Also

- [Structured Logging Guide](logging.md) - Log webhook events
- [Prometheus Metrics Guide](prometheus.md) - Monitor webhook success rates
- [Deployment Guide](deployment.md) - Production webhook deployment


