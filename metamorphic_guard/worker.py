from __future__ import annotations

import json
import sys
import threading
import traceback
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import click

from .queue_adapter import (
    InMemoryQueueAdapter,
    RedisQueueAdapter,
    QueueAdapter,
)
from .queue_serialization import decode_args as _decode_args
from .queue_adapter import QueueResult as _Result
from .sandbox import run_in_sandbox  # Import from refactored sandbox module
from .observability import add_log_context, close_logging, configure_logging, configure_metrics, log_event


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
@click.option(
    "--log-file",
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    default=None,
    help="Append structured JSON logs to the specified file.",
)
@click.option("--log-json/--no-log-json", default=None, help="Emit structured JSON logs to stdout.")
@click.option(
    "--metrics/--no-metrics",
    "metrics_enabled",
    default=None,
    help="Toggle Prometheus metrics collection for this worker.",
)
@click.option("--metrics-port", type=int, default=None, help="Expose Prometheus metrics on the provided port.")
@click.option("--metrics-host", type=str, default="0.0.0.0", show_default=True, help="Bind address for metrics server.")
def main(
    backend: str,
    queue_config: Optional[str],
    poll_interval: float,
    default_timeout_s: float,
    default_mem_mb: int,
    log_file: Optional[Path],
    log_json: Optional[bool],
    metrics_enabled: Optional[bool],
    metrics_port: Optional[int],
    metrics_host: str,
) -> None:
    """Run the Metamorphic Guard worker loop."""
    try:
        config = json.loads(queue_config) if queue_config else {}
        if not isinstance(config, dict):
            raise ValueError("queue-config must decode to a JSON object.")
    except Exception as exc:
        raise click.ClickException(f"Invalid queue-config: {exc}") from exc

    enable_logging = log_json if log_json is not None else (True if log_file else None)
    configure_logging(enable_logging, path=log_file)

    if metrics_enabled is not None or metrics_port is not None:
        try:
            configure_metrics(
                enabled=(metrics_enabled if metrics_enabled is not None else True),
                port=metrics_port,
                host=metrics_host,
            )
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc

    adapter = _create_adapter(backend, config)
    worker_id = str(uuid.uuid4())
    adapter.register_worker(worker_id)
    add_log_context(command="worker", worker_id=worker_id, backend=backend)

    heartbeat_interval = float(config.get("heartbeat_interval", 10.0))
    stop_event = threading.Event()

    def heartbeat_loop() -> None:
        while not stop_event.is_set():
            adapter.register_worker(worker_id)
            stop_event.wait(heartbeat_interval)

    hb_thread = threading.Thread(target=heartbeat_loop, daemon=True)
    hb_thread.start()

    click.echo(
        f"Metamorphic Guard worker started (backend={backend}). Press Ctrl+C to stop.",
        err=True,
    )

    try:
        while True:
            task = adapter.consume_task(worker_id, timeout=poll_interval)
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

            args_list = _decode_args(task.payload, compress=task.compressed)
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
                        task_id=task.task_id,
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
        stop_event.set()
        hb_thread.join(timeout=heartbeat_interval)
        adapter.signal_shutdown()
        close_logging()


if __name__ == "__main__":
    main()

