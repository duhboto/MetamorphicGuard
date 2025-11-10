from __future__ import annotations

import json
import sys
import traceback
from typing import Any, Dict, Optional

import click

from .dispatch_queue import (
    InMemoryQueueAdapter,
    RedisQueueAdapter,
    QueueAdapter,
    _Result,
    _decode_payload,
)
from .sandbox import run_in_sandbox
from .observability import log_event


def _create_adapter(backend: str, config: Optional[Dict[str, Any]]) -> QueueAdapter:
    config = config or {}
    config["backend"] = backend
    if backend == "memory":
        return InMemoryQueueAdapter()
    if backend == "redis":
        return RedisQueueAdapter(config)
    raise click.ClickException(f"Unsupported backend '{backend}'.")


@click.command()
@click.option(
    "--backend",
    type=click.Choice(["memory", "redis"]),
    default="redis",
    show_default=True,
    help="Queue backend to consume tasks from.",
)
@click.option(
    "--queue-config",
    type=str,
    default=None,
    help="JSON configuration for the queue backend.",
)
@click.option("--poll-interval", type=float, default=1.0, show_default=True, help="Poll interval in seconds.")
@click.option("--default-timeout-s", type=float, default=2.0, show_default=True, help="Fallback timeout per task.")
@click.option("--default-mem-mb", type=int, default=512, show_default=True, help="Fallback memory limit per task.")
def main(
    backend: str,
    queue_config: Optional[str],
    poll_interval: float,
    default_timeout_s: float,
    default_mem_mb: int,
) -> None:
    """Run the Metamorphic Guard worker loop."""
    try:
        config = json.loads(queue_config) if queue_config else {}
        if not isinstance(config, dict):
            raise ValueError("queue-config must decode to a JSON object.")
    except Exception as exc:
        raise click.ClickException(f"Invalid queue-config: {exc}") from exc

    adapter = _create_adapter(backend, config)
    if isinstance(adapter, InMemoryQueueAdapter):
        raise click.ClickException(
            "The in-memory backend only supports in-process execution. "
            "Use '--backend redis' for distributed workers."
        )

    click.echo(
        f"Metamorphic Guard worker started (backend={backend}). Press Ctrl+C to stop.",
        err=True,
    )

    try:
        while True:
            task = adapter.consume_task(timeout=poll_interval)
            if task is None:
                continue
            if task.job_id == "__shutdown__":
                click.echo("Shutdown signal received.", err=True)
                break

            call_spec = task.call_spec or {}
            file_path = call_spec.get("file_path")
            func_name = call_spec.get("func_name", "solve")
            timeout_s = call_spec.get("timeout_s", default_timeout_s)
            mem_mb = call_spec.get("mem_mb", default_mem_mb)

            if not file_path:
                click.echo(
                    f"Skipping task {task.job_id} (missing file_path).",
                    err=True,
                )
                continue

            executor_name = call_spec.get("executor")
            executor_conf = call_spec.get("executor_config")
            if executor_conf is not None and not isinstance(executor_conf, dict):
                raise ValueError("executor_config must be a JSON object.")

            args_list = _decode_payload(task.payload, compress=task.compressed)
            for case_index, args in zip(task.case_indices, args_list):
                log_event(
                    "worker_task_start",
                    job_id=task.job_id,
                    case_index=case_index,
                    role=task.role,
                )
                try:
                    result = run_in_sandbox(
                        file_path=file_path,
                        func_name=func_name,
                        args=args,
                        timeout_s=timeout_s,
                        mem_mb=mem_mb,
                        executor=executor_name,
                        executor_config=executor_conf,
                    )
                except Exception as exc:  # pragma: no cover - defensive
                    click.echo(
                        f"Error executing task {task.job_id}:{case_index}: {exc}",
                        err=True,
                    )
                    traceback.print_exc()
                    result = {
                        "success": False,
                        "error": str(exc),
                        "stdout": "",
                        "stderr": "",
                        "duration_ms": 0.0,
                    }

                adapter.publish_result(
                    _Result(
                        job_id=task.job_id,
                        case_index=case_index,
                        role=task.role,
                        result=result,
                    )
                )
                log_event(
                    "worker_task_complete",
                    job_id=task.job_id,
                    case_index=case_index,
                    role=task.role,
                    success=result.get("success", False),
                )
    except KeyboardInterrupt:  # pragma: no cover - user initiated
        click.echo("Worker interrupted. Exiting.", err=True)
    finally:
        adapter.signal_shutdown()


if __name__ == "__main__":
    main()

