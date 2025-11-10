from __future__ import annotations

import json
import logging
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
        except Exception as exc:  # pragma: no cover - network errors
            logger.warning("Failed to send alert to %s: %s", url, exc)
            continue

