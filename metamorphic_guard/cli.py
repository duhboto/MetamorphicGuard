"""
Command-line interface for Metamorphic Guard.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import click

import tomllib

from .gate import decide_adopt
from .harness import run_eval
from .specs import list_tasks
from .util import write_report
from .reporting import render_html_report
from .monitoring import resolve_monitors


class DefaultCommandGroup(click.Group):
    """Group that falls back to a default command when none is supplied."""

    def __init__(self, *args: Any, default_command: str | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.default_command = default_command

    def parse_args(self, ctx: click.Context, args: List[str]) -> List[str]:
        if self.default_command:
            if not args:
                args.insert(0, self.default_command)
            elif args[0].startswith("-"):
                args.insert(0, self.default_command)
        return super().parse_args(ctx, args)


def _load_config_defaults(ctx: click.Context, param: click.Parameter, value: Optional[Path]) -> None:
    if value is None:
        return
    if not value.exists():
        raise click.ClickException(f"Config file not found: {value}")
    try:
        data = tomllib.loads(value.read_text(encoding="utf-8"))
    except Exception as exc:
        raise click.ClickException(f"Failed to parse config {value}: {exc}") from exc

    if not isinstance(data, dict):
        raise click.ClickException("Config file must contain a TOML table of key/value pairs.")

    config_block: Dict[str, Any]
    if "metamorphic_guard" in data:
        block = data["metamorphic_guard"]
        if not isinstance(block, dict):
            raise click.ClickException("Table 'metamorphic_guard' must contain key/value pairs.")
        config_block = block
    else:
        config_block = data

    normalized: Dict[str, Any] = dict(config_block)
    if "executor_config" in normalized and isinstance(normalized["executor_config"], dict):
        normalized["executor_config"] = json.dumps(normalized["executor_config"])

    default_map: Dict[str, Any] = ctx.default_map or {}
    default_map.update(normalized)
    ctx.default_map = default_map


def _write_violation_report(path: Path, result: Dict[str, Any]) -> None:
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


EVALUATE_OPTIONS = [
    click.option(
        "--config",
        type=click.Path(exists=True, dir_okay=False, path_type=Path),
        callback=_load_config_defaults,
        expose_value=False,
        is_eager=True,
        help="Path to a TOML file with default option values.",
    ),
    click.option("--task", required=True, help="Task name to evaluate"),
    click.option("--baseline", required=True, help="Path to baseline implementation"),
    click.option("--candidate", required=True, help="Path to candidate implementation"),
    click.option("--n", default=400, show_default=True, help="Number of test cases to generate"),
    click.option("--seed", default=42, show_default=True, help="Random seed for generators"),
    click.option("--timeout-s", default=2.0, show_default=True, help="Timeout per test (seconds)"),
    click.option("--mem-mb", default=512, show_default=True, help="Memory limit per test (MB)"),
    click.option("--alpha", default=0.05, show_default=True, help="Significance level for bootstrap CI"),
    click.option(
        "--improve-delta",
        default=0.02,
        show_default=True,
        help="Minimum improvement threshold for adoption",
    ),
    click.option("--violation-cap", default=25, show_default=True, help="Maximum violations to record"),
    click.option(
        "--parallel",
        type=int,
        default=1,
        show_default=True,
        help="Number of concurrent workers for sandbox execution",
    ),
    click.option(
        "--bootstrap-samples",
        type=int,
        default=1000,
        show_default=True,
        help="Bootstrap resamples for confidence interval estimation",
    ),
    click.option(
        "--ci-method",
        type=click.Choice(["bootstrap", "newcombe", "wilson"], case_sensitive=False),
        default="bootstrap",
        show_default=True,
        help="Method for the pass-rate delta confidence interval",
    ),
    click.option(
        "--rr-ci-method",
        type=click.Choice(["log"], case_sensitive=False),
        default="log",
        show_default=True,
        help="Method for relative risk confidence interval",
    ),
    click.option(
        "--report-dir",
        type=click.Path(file_okay=False, writable=True, path_type=Path),
        default=None,
        help="Directory where the JSON report should be written.",
    ),
    click.option(
        "--dispatcher",
        type=click.Choice(["local", "queue"]),
        default="local",
        show_default=True,
        help="Execution dispatcher (local threads or experimental queue).",
    ),
    click.option(
        "--executor",
        type=str,
        default=None,
        help="Sandbox executor to use (e.g. 'docker' or 'package.module:callable').",
    ),
    click.option(
        "--executor-config",
        type=str,
        default=None,
        help="JSON string with executor-specific configuration.",
    ),
    click.option(
        "--export-violations",
        type=click.Path(dir_okay=False, writable=True, path_type=Path),
        default=None,
        help="Optional destination for a JSON file summarizing property and MR violations.",
    ),
    click.option(
        "--html-report",
        type=click.Path(dir_okay=False, writable=True, path_type=Path),
        default=None,
        help="Optional destination for an HTML summary report.",
    ),
    click.option(
        "--queue-config",
        type=str,
        default=None,
        help="JSON configuration for the queue dispatcher (experimental).",
    ),
    click.option(
        "--monitor",
        "monitor_names",
        multiple=True,
        help="Enable built-in monitors (e.g., 'latency').",
    ),
]


def _apply_evaluate_options(func):
    for decorator in reversed(EVALUATE_OPTIONS):
        func = decorator(func)
    return func


@click.group(cls=DefaultCommandGroup, default_command="evaluate")
def main() -> None:
    """Metamorphic Guard command group."""
    pass


@main.command("evaluate")
@_apply_evaluate_options
def evaluate_command(
    task: str,
    baseline: str,
    candidate: str,
    n: int,
    seed: int,
    timeout_s: float,
    mem_mb: int,
    alpha: float,
    improve_delta: float,
    violation_cap: int,
    parallel: int,
    bootstrap_samples: int,
    ci_method: str,
    rr_ci_method: str,
    report_dir: Path | None,
    dispatcher: str,
    executor: str | None,
    executor_config: str | None,
    export_violations: Path | None,
    html_report: Path | None,
    queue_config: str | None,
    monitor_names: Sequence[str],
) -> None:
    """Compare baseline and candidate implementations using metamorphic testing."""

    available_tasks = list_tasks()
    if task not in available_tasks:
        click.echo(
            f"Error: Task '{task}' not found. Available tasks: {available_tasks}",
            err=True,
        )
        sys.exit(1)

    try:
        click.echo(f"Running evaluation: {task}")
        click.echo(f"Baseline: {baseline}")
        click.echo(f"Candidate: {candidate}")
        click.echo(f"Test cases: {n}, Seed: {seed}")
        click.echo(f"Parallel workers: {parallel}")
        click.echo(f"CI method: {ci_method}")
        click.echo(f"RR CI method: {rr_ci_method}")

        parsed_executor_config = None
        if executor_config:
            try:
                parsed_executor_config = json.loads(executor_config)
                if not isinstance(parsed_executor_config, dict):
                    raise ValueError("Executor config must decode to a JSON object.")
            except Exception as exc:
                click.echo(f"Error: Invalid executor config ({exc})", err=True)
                sys.exit(1)

        queue_cfg = None
        if queue_config:
            try:
                queue_cfg = json.loads(queue_config)
                if not isinstance(queue_cfg, dict):
                    raise ValueError("Queue config must decode to a JSON object.")
            except Exception as exc:
                click.echo(f"Error: Invalid queue config ({exc})", err=True)
                sys.exit(1)

        monitor_objects = []
        if monitor_names:
            try:
                monitor_objects = resolve_monitors(monitor_names)
            except ValueError as exc:
                click.echo(f"Error: {exc}", err=True)
                sys.exit(1)

        result = run_eval(
            task_name=task,
            baseline_path=baseline,
            candidate_path=candidate,
            n=n,
            seed=seed,
            timeout_s=timeout_s,
            mem_mb=mem_mb,
            alpha=alpha,
            violation_cap=violation_cap,
            parallel=parallel,
            improve_delta=improve_delta,
            bootstrap_samples=bootstrap_samples,
            ci_method=ci_method,
            rr_ci_method=rr_ci_method,
            executor=executor,
            executor_config=parsed_executor_config,
            dispatcher=dispatcher,
            queue_config=queue_cfg,
            monitors=monitor_objects,
        )

        decision = decide_adopt(result, improve_delta)
        result["decision"] = decision

        report_path = write_report(result, directory=report_dir)

        if export_violations is not None:
            _write_violation_report(export_violations, result)

        if html_report is not None:
            render_html_report(result, html_report)

        click.echo("\n" + "=" * 60)
        click.echo("EVALUATION SUMMARY")
        click.echo("=" * 60)
        click.echo(f"Task: {result['task']}")
        click.echo(f"Test cases: {result['n']}")
        click.echo(f"Seed: {result['seed']}")
        click.echo()
        click.echo("BASELINE:")
        click.echo(
            f"  Pass rate: {result['baseline']['pass_rate']:.3f} "
            f"({result['baseline']['passes']}/{result['baseline']['total']})"
        )
        click.echo()
        click.echo("CANDIDATE:")
        click.echo(
            f"  Pass rate: {result['candidate']['pass_rate']:.3f} "
            f"({result['candidate']['passes']}/{result['candidate']['total']})"
        )
        click.echo(f"  Property violations: {len(result['candidate']['prop_violations'])}")
        click.echo(f"  MR violations: {len(result['candidate']['mr_violations'])}")
        click.echo()
        click.echo("IMPROVEMENT:")
        click.echo(f"  Delta: {result['delta_pass_rate']:.3f}")
        click.echo(f"  95% CI: [{result['delta_ci'][0]:.3f}, {result['delta_ci'][1]:.3f}]")
        click.echo(f"  Relative risk: {result['relative_risk']:.3f}")
        rr_ci = result["relative_risk_ci"]
        click.echo(f"  RR 95% CI: [{rr_ci[0]:.3f}, {rr_ci[1]:.3f}]")
        click.echo()
        click.echo("DECISION:")
        click.echo(f"  Adopt: {decision['adopt']}")
        click.echo(f"  Reason: {decision['reason']}")
        click.echo()
        click.echo(f"Report saved to: {report_path}")

        if decision["adopt"]:
            click.echo("✅ Candidate accepted!")
            sys.exit(0)

        click.echo("❌ Candidate rejected!")
        sys.exit(1)

    except KeyboardInterrupt:  # pragma: no cover - defensive surface
        click.echo("Evaluation interrupted by user.", err=True)
        sys.exit(1)

    except Exception as exc:  # pragma: no cover - defensive surface
        click.echo(f"Error during evaluation: {exc}", err=True)
        sys.exit(1)


@main.command("init")
@click.option(
    "--path",
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    default=Path("metamorphic_guard.toml"),
    show_default=True,
    help="Configuration file to create.",
)
@click.option("--task", default="top_k", show_default=True)
@click.option("--baseline", default="baseline.py", show_default=True)
@click.option("--candidate", default="candidate.py", show_default=True)
@click.option("--distributed/--no-distributed", default=False, show_default=True)
@click.option("--monitor", "monitor_names", multiple=True, help="Monitors to enable by default.")
def init_command(
    path: Path,
    task: str,
    baseline: str,
    candidate: str,
    distributed: bool,
    monitor_names: Sequence[str],
) -> None:
    """Create a starter TOML configuration file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["[metamorphic_guard]"]
    lines.append(f'task = "{task}"')
    lines.append(f'baseline = "{baseline}"')
    lines.append(f'candidate = "{candidate}"')
    if monitor_names:
        monitors = ", ".join(f'"{name}"' for name in monitor_names)
        lines.append(f"monitors = [{monitors}]")
    if distributed:
        lines.append("")
        lines.append("[metamorphic_guard.queue]")
        lines.append('dispatcher = "queue"')
        lines.append('queue_config = { backend = "redis", url = "redis://localhost:6379/0" }')

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    click.echo(f"Wrote configuration to {path}")


if __name__ == "__main__":
    main()
