from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any, Dict, Iterable, List, Mapping, Sequence

logger = logging.getLogger(__name__)


def collect_alerts(monitors: Mapping[str, Any] | Sequence[Any]) -> List[Dict[str, Any]]:
    """Flatten monitor alert payloads into a list."""

    if not monitors:
        return []

    if isinstance(monitors, Mapping):
        items = monitors.items()
    else:
        items = ((entry.get("id", f"monitor_{idx}"), entry) for idx, entry in enumerate(monitors))

    alerts: List[Dict[str, Any]] = []
    for monitor_id, data in items:
        monitor_alerts = data.get("alerts", []) if isinstance(data, Mapping) else []
        for alert in monitor_alerts:
            if isinstance(alert, Mapping):
                payload = {"monitor": monitor_id}
                payload.update(alert)
                alerts.append(payload)
    return alerts


def send_webhook_alerts(
    alerts: Sequence[Mapping[str, Any]],
    webhooks: Iterable[str],
    *,
    metadata: Mapping[str, Any] | None = None,
    opener=urllib.request.urlopen,
) -> None:
    """Dispatch alerts to configured webhook endpoints."""

    urls = [url for url in webhooks if url]
    if not urls or not alerts:
        return

    payload = {
        "alerts": list(alerts),
        "metadata": dict(metadata or {}),
    }
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    for url in urls:
        try:
            request = urllib.request.Request(url, data=data, headers=headers)
            opener(request)
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:  # pragma: no cover - network errors
            logger.warning("Failed to send alert to %s: %s", url, exc)
            continue


def send_slack_message(webhook_url: str, message: str, *, metadata: Mapping[str, Any] | None = None) -> None:
    """Send a simple Slack notification."""
    payload = {
        "text": message,
        "attachments": [
            {
                "color": "#4B8BF4",
                "fields": [{"title": key, "value": str(value), "short": True} for key, value in (metadata or {}).items()],
            }
        ]
        if metadata
        else None,
    }
    data = json.dumps({k: v for k, v in payload.items() if v is not None}).encode("utf-8")
    try:
        request = urllib.request.Request(webhook_url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(request)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:  # pragma: no cover - best effort
        logger.warning("Failed to send Slack message: %s", exc)


def create_jira_issue(config: Mapping[str, Any], alert: Mapping[str, Any]) -> None:
    """
    Create a Jira issue from an alert payload.

    This uses Jira's REST API if the configuration provides url/user/token;
    otherwise it logs a warning for manual follow-up.
    """
    url = config.get("url")
    auth_user = config.get("user")
    auth_token = config.get("token")
    project = config.get("project")
    if not (url and auth_user and auth_token and project):
        logger.warning("Jira configuration incomplete; skipping issue creation.")
        return

    issue_payload = {
        "fields": {
            "project": {"key": project},
            "summary": alert.get("summary", "Metamorphic Guard alert"),
            "description": json.dumps(alert, indent=2),
            "issuetype": {"name": config.get("issue_type", "Task")},
        }
    }
    data = json.dumps(issue_payload).encode("utf-8")
    request = urllib.request.Request(
        f"{url}/rest/api/2/issue",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Basic {base64_auth(auth_user, auth_token)}",
        },
    )
    try:
        urllib.request.urlopen(request)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:  # pragma: no cover
        logger.warning("Failed to create Jira issue: %s", exc)


def publish_datadog_event(api_key: str, title: str, text: str, *, tags: Sequence[str] | None = None) -> None:
    """Publish a Datadog event for observability dashboards."""
    payload = {
        "title": title,
        "text": text,
        "tags": tags or [],
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        "https://api.datadoghq.com/api/v1/events",
        data=data,
        headers={
            "Content-Type": "application/json",
            "DD-API-KEY": api_key,
        },
    )
    try:
        urllib.request.urlopen(request)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:  # pragma: no cover
        logger.warning("Failed to publish Datadog event: %s", exc)


def send_pagerduty_alert(
    integration_key: str,
    summary: str,
    source: str = "metamorphic-guard",
    severity: str = "warning",
    *,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    """
    Send a PagerDuty alert via Events API v2.
    
    Args:
        integration_key: PagerDuty integration key
        summary: Alert summary text
        source: Source identifier (default: "metamorphic-guard")
        severity: Alert severity (info, warning, error, critical)
        metadata: Additional metadata to include in the alert
    """
    payload = {
        "routing_key": integration_key,
        "event_action": "trigger",
        "payload": {
            "summary": summary,
            "source": source,
            "severity": severity,
            "custom_details": dict(metadata or {}),
        },
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        "https://events.pagerduty.com/v2/enqueue",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(request)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:  # pragma: no cover
        logger.warning("Failed to send PagerDuty alert: %s", exc)


def base64_auth(user: str, token: str) -> str:
    import base64

    raw = f"{user}:{token}".encode("utf-8")
    return base64.b64encode(raw).decode("utf-8")

