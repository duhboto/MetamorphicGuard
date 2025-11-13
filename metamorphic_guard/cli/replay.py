"""
Replay command for re-running evaluations from reports.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import click

from .evaluate import evaluate_command
from .utils import load_report


@click.command("replay")
@click.option("--from", "report_file", required=True, type=click.Path(exists=True, path_type=Path), help="JSON report file to replay")
@click.option("--baseline", type=str, default=None, help="Override baseline path (default: from report)")
@click.option("--candidate", type=str, default=None, help="Override candidate path (default: from report)")
@click.option("--execute/--no-execute", default=False, show_default=True, help="Execute the replay evaluation (default: print command only)")
@click.pass_context
def replay_command(
    ctx: click.Context,
    report_file: Path,
    baseline: str | None,
    candidate: str | None,
    execute: bool,
) -> None:
    """
    Replay an evaluation from a JSON report file.
    
    Extracts seed, test cases, and configuration from a previous evaluation report
    and either prints the replay command or executes it.
    
    Examples:
    
    \b
    # Print replay command
    metamorphic-guard replay --from reports/report_20240101_120000.json
    
    \b
    # Execute replay immediately
    metamorphic-guard replay --from reports/report_20240101_120000.json --execute
    """
    
    try:
        report_data = load_report(report_file)
    except Exception as e:
        click.echo(f"Error reading {report_file}: {e}", err=True)
        sys.exit(1)
    
    # Extract replay information
    replay_info = report_data.get("replay") or {}
    task_name = replay_info.get("task") or report_data.get("task")
    seed = replay_info.get("seed") or report_data.get("seed", 42)
    
    # Get baseline/candidate paths
    baseline_path = baseline
    candidate_path = candidate
    
    if not baseline_path:
        baseline_path = replay_info.get("baseline_path")
    if not candidate_path:
        candidate_path = replay_info.get("candidate_path")
    
    if not baseline_path or not candidate_path:
        click.echo("Error: Could not determine baseline/candidate paths from report", err=True)
        click.echo("  Use --baseline and --candidate to specify paths", err=True)
        sys.exit(1)
    
    # Get cases
    cases = report_data.get("cases", [])
    if not cases:
        click.echo("Error: No test cases found in report", err=True)
        sys.exit(1)
    
    # Create temporary cases file
    cases_file = Path(tempfile.mkdtemp()) / "replay_cases.json"
    cases_file.write_text(json.dumps(cases, indent=2), encoding="utf-8")
    
    # Get configuration from report
    config = report_data.get("config", {})
    min_delta = config.get("min_delta", 0.02)
    min_pass_rate = config.get("min_pass_rate", 0.80)
    ci_method = config.get("ci_method", "newcombe")
    alpha = config.get("alpha", 0.05)
    
    # Build replay command
    replay_cmd = [
        "metamorphic-guard",
        "evaluate",
        "--task", task_name,
        "--baseline", baseline_path,
        "--candidate", candidate_path,
        "--seed", str(seed),
        "--replay-input", str(cases_file),
        "--min-delta", str(min_delta),
        "--min-pass-rate", str(min_pass_rate),
        "--ci-method", ci_method,
        "--alpha", str(alpha),
    ]
    
    if execute:
        click.echo(f"Replaying evaluation from {report_file}")
        click.echo(f"Task: {task_name}, Seed: {seed}, Cases: {len(cases)}")
        click.echo("")
        
        # Invoke evaluate command
        try:
            # Import here to avoid circular dependency
            from .evaluate import apply_evaluate_options
            
            # Create a minimal evaluate command invocation
            # We'll need to pass all required parameters
            ctx.invoke(
                evaluate_command,
                task=task_name,
                baseline=baseline_path,
                candidate=candidate_path,
                n=len(cases),  # Will be overridden by replay-input
                seed=seed,
                timeout_s=config.get("timeout_s", 2.0),
                mem_mb=config.get("mem_mb", 512),
                alpha=alpha,
                sequential_method=config.get("sequential_method", "none"),
                max_looks=config.get("max_looks", 1),
                look_number=config.get("look_number", 1),
                min_delta=min_delta,
                min_pass_rate=min_pass_rate,
                violation_cap=config.get("violation_cap", 25),
                parallel=config.get("parallel", 1),
                bootstrap_samples=config.get("bootstrap_samples", 1000),
                ci_method=ci_method,
                rr_ci_method=config.get("rr_ci_method", "log"),
                report_dir=None,
                dispatcher=config.get("dispatcher", "local"),
                executor=None,
                executor_config=None,
                export_violations=None,
                html_report=None,
                junit_report=None,
                queue_config=None,
                monitor_names=[],
                mr_fwer=False,
                mr_fdr=False,
                alert_webhooks=[],
                sandbox_plugins=None,
                allow_unsafe_plugins=False,
                log_file=None,
                log_json=None,
                metrics_enabled=None,
                metrics_port=None,
                metrics_host="0.0.0.0",
                failed_artifact_limit=None,
                failed_artifact_ttl_days=None,
                policy_version=None,
                otlp_endpoint=None,
                replay_input=cases_file,
                policy=None,
                power_target=config.get("power_target", 0.8),
                stability=config.get("stability", 1),
                shrink_violations=config.get("shrink_violations", False),
            )
        except Exception as e:
            click.echo(f"Error during replay: {e}", err=True)
            sys.exit(1)
        finally:
            # Clean up temp file
            try:
                cases_file.unlink()
                cases_file.parent.rmdir()
            except Exception:
                pass
    else:
        click.echo("Replay command:")
        click.echo("  " + " ".join(replay_cmd))
        click.echo("")
        click.echo("To execute this replay, run:")
        click.echo(f"  metamorphic-guard replay --from {report_file} --execute")

