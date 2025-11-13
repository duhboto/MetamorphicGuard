"""
Shared utilities for CLI commands.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import click

from ..config import ConfigLoadError, load_config
from ..policy import PolicyLoadError, PolicyParseError, resolve_policy_option as _resolve_policy_option


def flatten_dict(value: Any, prefix: str = "") -> Dict[str, Any]:
    """Flatten a nested dictionary."""
    items: Dict[str, Any] = {}
    if isinstance(value, dict):
        for key, val in value.items():
            key_str = str(key)
            new_prefix = f"{prefix}.{key_str}" if prefix else key_str
            items.update(flatten_dict(val, new_prefix))
    elif isinstance(value, list):
        for idx, val in enumerate(value):
            new_prefix = f"{prefix}[{idx}]" if prefix else f"[{idx}]"
            items.update(flatten_dict(val, new_prefix))
    else:
        items[prefix or ""] = value
    return items


def load_report(path: Path) -> Dict[str, Any]:
    """Load a JSON report file."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"Failed to parse report JSON ({exc})") from exc


def get_nested(data: Dict[str, Any], path: Sequence[str]) -> Any:
    """Get a nested value from a dictionary using a path."""
    current: Any = data
    for part in path:
        if not isinstance(current, dict):
            raise KeyError(".".join(path))
        if part not in current:
            raise KeyError(".".join(path))
        current = current[part]
    return current


def load_config_defaults(ctx: click.Context, param: click.Parameter, value: Optional[Path]) -> None:
    """Load configuration defaults from a TOML file."""
    if value is None:
        return
    if not value.exists():
        raise click.ClickException(f"Config file not found: {value}")

    try:
        config = load_config(value)
    except ConfigLoadError as exc:
        raise click.ClickException(str(exc)) from exc

    default_map: Dict[str, Any] = ctx.default_map or {}
    default_map.update(
        {
            "task": config.task,
            "baseline": config.baseline,
            "candidate": config.candidate,
            "n": config.n,
            "seed": config.seed,
            "timeout_s": config.timeout_s,
            "mem_mb": config.mem_mb,
            "alpha": config.alpha,
            "min_delta": config.min_delta,
            "min_pass_rate": config.min_pass_rate,
            "violation_cap": config.violation_cap,
            "parallel": config.parallel,
            "bootstrap_samples": config.bootstrap_samples,
            "ci_method": config.ci_method,
            "rr_ci_method": config.rr_ci_method,
            "monitor_names": config.monitors,
            "dispatcher": config.dispatcher,
            "executor": config.executor,
            "policy_version": config.policy_version,
            "alert_webhooks": config.alerts.webhooks,
            "log_json": config.log_json,
            "log_file": Path(config.log_file) if config.log_file else None,
            "metrics_enabled": config.metrics_enabled,
            "metrics_port": config.metrics_port,
            "metrics_host": config.metrics_host,
            "failed_artifact_limit": config.failed_artifact_limit,
            "failed_artifact_ttl_days": config.failed_artifact_ttl_days,
            "sandbox_plugins": config.sandbox_plugins,
            "power_target": config.power_target,
            "policy": str(config.policy) if config.policy else None,
            "stability": config.stability,
        }
    )

    if config.relation_correction == "holm":
        default_map["mr_fwer"] = True
    elif config.relation_correction == "fdr":
        default_map["mr_fdr"] = True

    if config.queue is not None:
        default_map["queue_config"] = json.dumps(config.queue.dict(exclude_none=True))
    if config.executor_config is not None:
        default_map["executor_config"] = json.dumps(config.executor_config)

    ctx.default_map = default_map


def resolve_policy_option(value: str) -> Dict[str, Any]:
    """Resolve a policy option string to a policy dictionary."""
    try:
        return _resolve_policy_option(value)
    except (PolicyLoadError, PolicyParseError) as exc:
        raise click.ClickException(str(exc)) from exc


def write_violation_report(path: Path, result: Dict[str, Any]) -> None:
    """Write a violation report to a JSON file."""
    payload = {
        "task": result.get("task"),
        "baseline": {
            "prop_violations": result.get("baseline", {}).get("prop_violations", []),
            "mr_violations": result.get("baseline", {}).get("mr_violations", []),
        },
        "candidate": {
            "prop_violations": result.get("candidate", {}).get("prop_violations", []),
            "mr_violations": result.get("candidate", {}).get("mr_violations", []),
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

