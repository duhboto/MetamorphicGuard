"""
Evaluate command - the main evaluation command.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional, Sequence

import click
from click import Command, Option, HelpFormatter

from ..config import load_config
from ..harness import run_eval
from ..notifications import collect_alerts, send_webhook_alerts
from ..observability import (
    add_log_context,
    close_logging,
    configure_logging,
    configure_metrics,
    log_event,
)
from ..reporting import render_html_report, render_junit_report
from ..specs import list_tasks
from ..util import write_report
from .utils import (
    load_config_defaults,
    resolve_policy_option,
    write_violation_report,
)


class GroupedCommand(Command):
    """Command that groups options in help output."""
    
    def __init__(self, *args: Any, option_groups: Optional[dict[str, list[str]]] = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.option_groups = option_groups or {}
    
    def format_options(self, ctx: click.Context, formatter: HelpFormatter) -> None:
        """Format options grouped by category."""
        if not self.option_groups:
            # Fallback to default formatting
            return super().format_options(ctx, formatter)
        
        # Get all options
        opts = []
        for param in self.get_params(ctx):
            if isinstance(param, Option) and not param.hidden:
                opts.append(param)
        
        # Group options
        grouped: dict[str, list[Option]] = {}
        ungrouped: list[Option] = []
        
        # Reverse mapping: option name -> group name
        option_to_group: dict[str, str] = {}
        for group_name, option_names in self.option_groups.items():
            for opt_name in option_names:
                option_to_group[opt_name] = group_name
        
        for opt in opts:
            # Find the option name (handle both --option and --option-name formats)
            opt_names = [name.lstrip('-').replace('-', '_') for name in opt.opts if name.startswith('--')]
            found_group = None
            for opt_name in opt_names:
                if opt_name in option_to_group:
                    found_group = option_to_group[opt_name]
                    break
            
            if found_group:
                grouped.setdefault(found_group, []).append(opt)
            else:
                ungrouped.append(opt)
        
        # Write grouped options
        for group_name in sorted(grouped.keys()):
            group_opts = grouped[group_name]
            if group_opts:
                with formatter.section(f"{group_name} Options"):
                    self._format_options_list(ctx, formatter, group_opts)
        
        # Write ungrouped options
        if ungrouped:
            with formatter.section("Other Options"):
                self._format_options_list(ctx, formatter, ungrouped)
    
    def _format_options_list(self, ctx: click.Context, formatter: HelpFormatter, opts: list[Option]) -> None:
        """Format a list of options."""
        for param in opts:
            self._format_option(ctx, formatter, param)
    
    def _format_option(self, ctx: click.Context, formatter: HelpFormatter, param: Option) -> None:
        """Format a single option."""
        # Get option help - returns tuple of (option_string, help_text)
        help_record = param.get_help_record(ctx)
        if help_record and isinstance(help_record, tuple) and len(help_record) >= 2:
            # write_dl expects a list of tuples, each with exactly 2 elements
            formatter.write_dl([help_record])
        elif help_record:
            # Fallback: just write the option string and help separately
            opt_str = help_record[0] if isinstance(help_record, tuple) else str(help_record)
            help_text = help_record[1] if isinstance(help_record, tuple) and len(help_record) > 1 else ""
            formatter.write_dl([(opt_str, help_text)])


# Option groups for help organization
OPTION_GROUPS = {
    "Configuration": [
        "config",
        "preset",
    ],
    "Core": [
        "task",
        "baseline",
        "candidate",
        "n",
        "seed",
        "timeout_s",
        "mem_mb",
        "alpha",
        "min_delta",
        "min_pass_rate",
        "violation_cap",
    ],
    "Statistical": [
        "bootstrap_samples",
        "ci_method",
        "rr_ci_method",
        "bayesian_samples",
        "bayesian_hierarchical",
        "bayesian_posterior_predictive",
        "power_target",
    ],
    "Sequential Testing": [
        "sequential_method",
        "max_looks",
        "look_number",
    ],
    "Adaptive Testing": [
        "adaptive_testing",
        "adaptive_min_sample_size",
        "adaptive_check_interval",
        "adaptive_power_threshold",
        "adaptive_max_sample_size",
        "adaptive_group_sequential",
        "adaptive_sequential_method",
        "adaptive_max_looks",
    ],
    "Execution": [
        "parallel",
        "dispatcher",
        "executor",
        "executor_config",
        "queue_config",
        "replay_input",
    ],
    "Reporting": [
        "report_dir",
        "html_report",
        "junit_report",
        "export_violations",
    ],
    "Advanced": [
        "policy",
        "monitor_names",
        "mr_fwer",
        "mr_hochberg",
        "mr_fdr",
        "no_mr_correction",
        "shrink_violations",
        "failed_artifact_limit",
        "failed_artifact_ttl_days",
        "policy_version",
        "stability",
        "estimate_cost",
        "budget_limit",
        "budget_warning",
        "budget_action",
    ],
    "Observability": [
        "log_file",
        "log_json",
        "metrics_enabled",
        "metrics_port",
        "metrics_host",
        "otlp_endpoint",
        "alert_webhooks",
    ],
    "Security": [
        "sandbox_plugins",
        "allow_unsafe_plugins",
    ],
}

# Evaluate command options - extracted from original cli.py
EVALUATE_OPTIONS = [
    click.option(
        "--config",
        type=click.Path(exists=True, dir_okay=False, path_type=Path),
        callback=load_config_defaults,
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
        "--sequential-method",
        type=click.Choice(["none", "pocock", "obrien-fleming", "sprt"], case_sensitive=False),
        default="none",
        show_default=True,
        help="Sequential testing method for iterative PR workflows (alpha-spending or SPRT).",
    ),
    click.option(
        "--adaptive",
        "adaptive_testing",
        is_flag=True,
        default=False,
        help="Enable adaptive sample size determination based on interim power analysis.",
    ),
    click.option(
        "--adaptive-min-n",
        "adaptive_min_sample_size",
        type=int,
        default=50,
        help="Minimum sample size before first adaptive check (default: 50).",
    ),
    click.option(
        "--adaptive-interval",
        "adaptive_check_interval",
        type=int,
        default=50,
        help="Check power every N samples (default: 50).",
    ),
    click.option(
        "--adaptive-power-threshold",
        "adaptive_power_threshold",
        type=float,
        default=0.95,
        help="Stop early if power exceeds this threshold (default: 0.95).",
    ),
    click.option(
        "--adaptive-max-n",
        "adaptive_max_sample_size",
        type=int,
        default=None,
        help="Maximum sample size for adaptive testing (no limit if not set).",
    ),
    click.option(
        "--adaptive-group-sequential",
        "adaptive_group_sequential",
        is_flag=True,
        default=False,
        help="Use group sequential design with pre-specified boundaries (alternative to adaptive power-based stopping).",
    ),
    click.option(
        "--adaptive-sequential-method",
        "adaptive_sequential_method",
        type=click.Choice(["pocock", "obrien-fleming"], case_sensitive=False),
        default="pocock",
        help="Sequential boundary method for group sequential designs (default: pocock).",
    ),
    click.option(
        "--adaptive-max-looks",
        "adaptive_max_looks",
        type=int,
        default=5,
        help="Maximum number of looks for group sequential designs (default: 5).",
    ),
    click.option(
        "--max-looks",
        type=int,
        default=1,
        show_default=True,
        help="Maximum number of looks/interim analyses for sequential testing (default: 1 = no sequential testing).",
    ),
    click.option(
        "--look-number",
        type=int,
        default=1,
        show_default=True,
        help="Current look number for sequential testing (1-indexed).",
    ),
    click.option(
        "--min-delta",
        "--improve-delta",  # Deprecated alias
        default=0.02,
        show_default=True,
        help="Minimum improvement threshold for adoption (--improve-delta is deprecated, use --min-delta)",
    ),
    click.option(
        "--min-pass-rate",
        type=float,
        default=0.80,
        show_default=True,
        help="Minimum candidate pass rate required for adoption.",
    ),
    click.option(
        "--power-target",
        type=float,
        default=0.8,
        show_default=True,
        help="Desired statistical power for detecting improvements (used for guidance).",
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
        "--policy",
        type=str,
        default=None,
        help=(
            "Policy to apply. Provide a TOML path or use presets like "
            "'noninferiority:margin=0.00' or 'superiority:margin=0.02'."
        ),
    ),
    click.option(
        "--bootstrap-samples",
        type=int,
        default=1000,
        show_default=True,
        help="Bootstrap resamples for confidence interval estimation",
    ),
    click.option(
        "--bayesian-samples",
        type=int,
        default=5000,
        show_default=True,
        help="Monte Carlo samples when using Bayesian confidence intervals.",
    ),
    click.option(
        "--bayesian-hierarchical/--no-bayesian-hierarchical",
        default=False,
        help="Use a hierarchical Beta-Binomial prior when --ci-method=bayesian.",
    ),
    click.option(
        "--bayesian-posterior-predictive/--no-bayesian-posterior-predictive",
        default=False,
        help="Emit Bayesian posterior predictive diagnostics alongside the CI.",
    ),
    click.option(
        "--ci-method",
        type=click.Choice(
            [
                "bootstrap",
                "bootstrap-bca",
                "bootstrap-cluster",
                "bootstrap-cluster-bca",
                "newcombe",
                "wilson",
                "bayesian",
            ],
            case_sensitive=False,
        ),
        default="bootstrap",
        show_default=True,
        help="Method for the pass-rate delta confidence interval (bayesian uses Beta-Binomial prior)",
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
        "--junit-report",
        "--junit-xml",  # Deprecated alias
        type=click.Path(dir_okay=False, writable=True, path_type=Path),
        default=None,
        help="Optional destination for a JUnit XML report (for CI integration).",
    ),
    click.option(
        "--queue-config",
        type=str,
        default=None,
        help="JSON configuration for the queue dispatcher (experimental).",
    ),
    click.option(
        "--replay-input",
        type=click.Path(exists=True, dir_okay=False, path_type=Path),
        default=None,
        help="Replay explicit test case inputs from a JSON file.",
    ),
    click.option(
        "--monitor",
        "monitor_names",
        multiple=True,
        help="Enable built-in monitors (e.g., 'latency').",
    ),
    click.option(
        "--mr-fwer",
        is_flag=True,
        default=False,
        help="Apply Holm-Bonferroni correction to metamorphic relation p-values (default: enabled).",
    ),
    click.option(
        "--mr-hochberg",
        is_flag=True,
        default=False,
        help="Apply Hochberg step-down correction to metamorphic relation p-values (more powerful than Holm).",
    ),
    click.option(
        "--mr-fdr",
        is_flag=True,
        default=False,
        help="Apply Benjamini-Hochberg FDR correction to metamorphic relation p-values (alternative to FWER).",
    ),
    click.option(
        "--no-mr-correction",
        is_flag=True,
        default=False,
        help="Disable multiple comparisons correction for metamorphic relations (not recommended).",
    ),
    click.option(
        "--alert-webhook",
        "alert_webhooks",
        multiple=True,
        help="POST monitor alerts to the provided webhook URL (can be repeated).",
    ),
    click.option(
        "--sandbox-plugins/--no-sandbox-plugins",
        default=True,
        show_default=True,
        help="Execute third-party plugins in isolated subprocesses (default: enabled for security).",
    ),
    click.option(
        "--allow-unsafe-plugins",
        is_flag=True,
        default=False,
        help="Allow plugins to run without sandboxing (security risk). Equivalent to --no-sandbox-plugins.",
    ),
    click.option(
        "--log-file",
        type=click.Path(dir_okay=False, writable=True, path_type=Path),
        default=None,
        help="Append structured JSON logs to the specified file.",
    ),
    click.option(
        "--log-json/--no-log-json",
        default=None,
        help="Emit structured JSON logs to stdout during evaluation.",
    ),
    click.option(
        "--metrics/--no-metrics",
        "metrics_enabled",
        default=None,
        help="Toggle Prometheus metrics collection for this run.",
    ),
    click.option(
        "--metrics-port",
        type=int,
        default=None,
        help="Expose Prometheus metrics on the provided port.",
    ),
    click.option(
        "--metrics-host",
        type=str,
        default="0.0.0.0",
        show_default=True,
        help="Bind address when serving Prometheus metrics.",
    ),
    click.option(
        "--failed-artifact-limit",
        type=int,
        default=None,
        help="Maximum number of failed-case artifacts to retain (per directory).",
    ),
    click.option(
        "--failed-artifact-ttl-days",
        type=int,
        default=None,
        help="Remove failed-case artifacts older than the specified number of days.",
    ),
    click.option(
        "--policy-version",
        type=str,
        default=None,
        help="Optional policy version identifier recorded in evaluation reports.",
    ),
    click.option(
        "--otlp-endpoint",
        type=str,
        default=None,
        help="OpenTelemetry OTLP endpoint URL (e.g., 'http://localhost:4317') for trace export.",
    ),
    click.option(
        "--stability",
        type=int,
        default=1,
        show_default=True,
        help="Run evaluation N times and require consistent decisions (consensus). Reports flakiness if decisions differ.",
    ),
    click.option(
        "--shrink-violations/--no-shrink-violations",
        default=False,
        show_default=True,
        help="Shrink failing test cases to minimal counterexamples for easier debugging.",
    ),
    click.option(
        "--estimate-cost",
        is_flag=True,
        default=False,
        help="Estimate cost before running evaluation (LLM executors only).",
    ),
    click.option(
        "--budget-limit",
        type=float,
        default=None,
        help="Hard budget limit in USD. Aborts evaluation if estimated cost exceeds this limit.",
    ),
    click.option(
        "--budget-warning",
        type=float,
        default=None,
        help="Warning threshold in USD. Warns user if estimated cost exceeds this threshold.",
    ),
    click.option(
        "--budget-action",
        type=click.Choice(["allow", "warn", "abort"], case_sensitive=False),
        default="warn",
        show_default=True,
        help="Action to take when budget warning threshold is exceeded: 'allow' (no action), 'warn' (show warning), 'abort' (abort execution).",
    ),
]


def apply_evaluate_options(func):
    """Apply all evaluate command options to a function."""
    for decorator in reversed(EVALUATE_OPTIONS):
        func = decorator(func)
    return func


@click.command("evaluate", cls=GroupedCommand, option_groups=OPTION_GROUPS)
@apply_evaluate_options
def evaluate_command(
    task: str,
    baseline: str,
    candidate: str,
    n: int,
    seed: int,
    timeout_s: float,
    mem_mb: int,
    alpha: float,
    sequential_method: str,
    max_looks: int,
    look_number: int,
    min_delta: float,
    min_pass_rate: float,
    violation_cap: int,
    parallel: int,
    bootstrap_samples: int,
    bayesian_samples: int,
    bayesian_hierarchical: bool,
    bayesian_posterior_predictive: bool,
    ci_method: str,
    rr_ci_method: str,
    report_dir: Path | None,
    dispatcher: str,
    executor: str | None,
    executor_config: str | None,
    export_violations: Path | None,
    html_report: Path | None,
    junit_report: Path | None,
    queue_config: str | None,
    monitor_names: Sequence[str],
    mr_fwer: bool,
    mr_hochberg: bool,
    mr_fdr: bool,
    no_mr_correction: bool,
    alert_webhooks: Sequence[str],
    sandbox_plugins: Optional[bool],
    allow_unsafe_plugins: bool,
    log_file: Optional[Path],
    log_json: Optional[bool],
    metrics_enabled: Optional[bool],
    metrics_port: Optional[int],
    metrics_host: str,
    failed_artifact_limit: Optional[int],
    failed_artifact_ttl_days: Optional[int],
    policy_version: Optional[str],
    otlp_endpoint: Optional[str],
    replay_input: Path | None,
    policy: str | None,
    power_target: float,
    stability: int,
    shrink_violations: bool,
    estimate_cost: bool,
    budget_limit: Optional[float],
    budget_warning: Optional[float],
    budget_action: str,
    adaptive_testing: bool,
    adaptive_min_sample_size: int,
    adaptive_check_interval: int,
    adaptive_power_threshold: float,
    adaptive_max_sample_size: Optional[int],
    adaptive_group_sequential: bool,
    adaptive_sequential_method: str,
    adaptive_max_looks: int,
) -> None:
    """Compare baseline and candidate implementations using metamorphic testing."""

    available_tasks = list_tasks()
    if task not in available_tasks:
        from .progress import echo_error, format_error_message
        
        error_msg = f"Task '{task}' not found"
        suggestions = [
            f"Available tasks: {', '.join(available_tasks)}",
            "Register your task with @task decorator",
            "See: metamorphic-guard plugin list",
        ]
        
        click.echo(format_error_message(ValueError(error_msg), {"suggestions": suggestions}), err=True)
        sys.exit(1)

    try:
        enable_logging = log_json if log_json is not None else (True if log_file else None)
        configure_logging(enable_logging, path=log_file)
        add_log_context(command="evaluate", task=task, baseline=baseline, candidate=candidate)

        if metrics_enabled is not None or metrics_port is not None:
            try:
                configure_metrics(
                    enabled=(metrics_enabled if metrics_enabled is not None else True),
                    port=metrics_port,
                    host=metrics_host,
                )
            except RuntimeError as exc:
                raise click.ClickException(str(exc)) from exc
        
        # Configure OpenTelemetry if endpoint provided
        if otlp_endpoint:
            try:
                from ..telemetry import configure_telemetry
                from .. import __version__
                
                configured = configure_telemetry(
                    endpoint=otlp_endpoint,
                    service_name="metamorphic-guard",
                    service_version=__version__,
                    enabled=True,
                )
                if configured:
                    click.echo(f"OpenTelemetry tracing enabled: {otlp_endpoint}", err=True)
                else:
                    click.echo(
                        "Warning: OpenTelemetry not available. Install with: pip install metamorphic-guard[otel]",
                        err=True,
                    )
            except ImportError:
                click.echo(
                    "Warning: OpenTelemetry not available. Install with: pip install metamorphic-guard[otel]",
                    err=True,
                )

        explicit_inputs = None
        if replay_input is not None:
            try:
                payload = json.loads(replay_input.read_text(encoding="utf-8"))
            except Exception as exc:
                raise click.ClickException(f"Failed to read replay input JSON: {exc}") from exc

            if isinstance(payload, dict) and "cases" in payload:
                cases_payload = payload["cases"]
            else:
                cases_payload = payload

            if not isinstance(cases_payload, list):
                raise click.ClickException("Replay input JSON must be a list or an object with a 'cases' list.")

            explicit_inputs = []
            for entry in cases_payload:
                if isinstance(entry, dict) and "input" in entry:
                    raw_args = entry["input"]
                else:
                    raw_args = entry

                if not isinstance(raw_args, (list, tuple)):
                    raise click.ClickException("Each replayed case must be a sequence (list/tuple) of arguments.")

                explicit_inputs.append(tuple(raw_args))

        effective_n = len(explicit_inputs) if explicit_inputs is not None else n

        policy_payload = None
        if policy is not None:
            try:
                policy_payload = resolve_policy_option(policy)
            except Exception as exc:
                raise click.ClickException(str(exc)) from exc

            gating_cfg = policy_payload.get("gating", {})

            def _maybe_float(value: Any, label: str) -> float:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    raise click.ClickException(f"Policy value '{label}' must be numeric.")

            if "min_delta" in gating_cfg:
                min_delta = _maybe_float(gating_cfg["min_delta"], "min_delta")
            if "min_pass_rate" in gating_cfg:
                min_pass_rate = _maybe_float(gating_cfg["min_pass_rate"], "min_pass_rate")
            if "alpha" in gating_cfg:
                alpha = _maybe_float(gating_cfg["alpha"], "alpha")
            if "power_target" in gating_cfg:
                power_target = _maybe_float(gating_cfg["power_target"], "power_target")
            if "violation_cap" in gating_cfg:
                try:
                    violation_cap = int(gating_cfg["violation_cap"])
                except (TypeError, ValueError):
                    raise click.ClickException("Policy value 'violation_cap' must be an integer.")

            descriptor = policy_payload.get("descriptor", {})
            if policy_payload.get("source") == "preset":
                label = descriptor.get("label") or policy_payload.get("name") or policy
                click.echo(f"Using policy preset: {label}")
            else:
                click.echo(f"Using policy file: {descriptor.get('path', policy)}")

            if not policy_version:
                derived_version = descriptor.get("name") or descriptor.get("label") or policy_payload.get("name")
                if isinstance(derived_version, str):
                    policy_version = derived_version

        # Cost estimation (if requested and executor is LLM)
        if (estimate_cost or budget_limit is not None or budget_warning is not None) and executor:
            try:
                from ..cost_estimation import (
                    BudgetAction,
                    BudgetExceededError,
                    estimate_and_check_budget,
                )
                from ..specs import get_task
                
                spec = get_task(task)
                # Generate sample inputs from spec for cost estimation
                # Use a small sample to estimate average prompt length
                system_prompt = None
                user_prompts: list[str] = []
                
                try:
                    # Generate a small sample of test inputs to estimate prompt sizes
                    sample_size = min(5, effective_n)
                    sample_inputs = spec.gen_inputs(sample_size, seed)
                    
                    # Format inputs as strings (prompts for LLM executors)
                    for test_input in sample_inputs:
                        if spec.fmt_in:
                            formatted = spec.fmt_in(test_input)
                            if isinstance(formatted, str) and formatted.strip():
                                user_prompts.append(formatted)
                    
                    # If no prompts generated, use a default
                    if not user_prompts:
                        user_prompts = ["Example test case input"]
                except Exception:
                    # Fallback if spec doesn't support input generation
                    user_prompts = ["Example test case input"]
                
                # Get executor config
                executor_cfg = {}
                if executor_config:
                    try:
                        executor_cfg = json.loads(executor_config) if isinstance(executor_config, str) else executor_config
                    except (json.JSONDecodeError, TypeError):
                        executor_cfg = {}
                
                # Convert budget_action string to enum
                action_map = {
                    "allow": BudgetAction.ALLOW,
                    "warn": BudgetAction.WARN,
                    "abort": BudgetAction.ABORT,
                }
                budget_action_enum = action_map.get(budget_action.lower(), BudgetAction.WARN)
                
                try:
                    result = estimate_and_check_budget(
                        executor_name=executor,
                        executor_config=executor_cfg,
                        n=effective_n,
                        budget_limit=budget_limit,
                        warning_threshold=budget_warning,
                        action=budget_action_enum,
                        system_prompt=system_prompt,
                        user_prompts=user_prompts,
                        max_tokens=512,  # Default, could be from config
                    )
                    estimate = result
                    budget_check = result.get("budget_check", {})
                except BudgetExceededError as e:
                    click.echo("\n" + "=" * 60, err=True)
                    click.echo("BUDGET EXCEEDED", err=True)
                    click.echo("=" * 60, err=True)
                    click.echo(f"❌ {str(e)}", err=True)
                    click.echo("\nEvaluation aborted to prevent exceeding budget.", err=True)
                    sys.exit(1)
                
                if estimate_cost:
                    click.echo("\n" + "=" * 60)
                    click.echo("COST ESTIMATION")
                    click.echo("=" * 60)
                    click.echo(f"Estimated total cost: ${estimate['total_cost_usd']:.4f}")
                    click.echo(f"  Baseline: ${estimate['baseline_cost_usd']:.4f}")
                    click.echo(f"  Candidate: ${estimate['candidate_cost_usd']:.4f}")
                    if estimate['judge_cost_usd'] > 0:
                        click.echo(f"  Judge: ${estimate['judge_cost_usd']:.4f}")
                    click.echo(f"\nTest cases: {effective_n}")
                    click.echo(f"  Baseline calls: {estimate['breakdown']['baseline_calls']}")
                    click.echo(f"  Candidate calls: {estimate['breakdown']['candidate_calls']}")
                
                # Show budget check results
                if budget_check:
                    click.echo("\n" + "=" * 60)
                    click.echo("BUDGET CHECK")
                    click.echo("=" * 60)
                    message = budget_check.get("message", "")
                    action_taken = budget_check.get("action_taken", "none")
                    
                    if action_taken == "warn":
                        click.echo(f"⚠️  {message}", err=True)
                    elif action_taken == "abort":
                        click.echo(f"❌ {message}", err=True)
                        sys.exit(1)
                    else:
                        click.echo(f"✓ {message}")
                
                if estimate_cost:
                    if estimate['breakdown']['judge_calls'] > 0:
                        click.echo(f"  Judge calls: {estimate['breakdown']['judge_calls']}")
                    click.echo(f"\nEstimated tokens:")
                    click.echo(f"  Baseline: {estimate['estimated_tokens']['baseline']['total']:,} tokens")
                    click.echo(f"  Candidate: {estimate['estimated_tokens']['candidate']['total']:,} tokens")
                    if estimate['estimated_tokens']['judge']['total'] > 0:
                        click.echo(f"  Judge: {estimate['estimated_tokens']['judge']['total']:,} tokens")
                    click.echo("=" * 60 + "\n")
                
                # Ask for confirmation if cost is significant
                if estimate['total_cost_usd'] > 1.0:
                    if not click.confirm(f"Estimated cost is ${estimate['total_cost_usd']:.2f}. Continue?"):
                        click.echo("Evaluation cancelled.")
                        sys.exit(0)
            except Exception as exc:
                click.echo(f"Warning: Could not estimate cost: {exc}", err=True)

        click.echo(f"Running evaluation: {task}")
        click.echo(f"Baseline: {baseline}")
        click.echo(f"Candidate: {candidate}")
        click.echo(f"Test cases: {effective_n}, Seed: {seed}")
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

        # Handle sandboxing: default to True, allow opt-out via --allow-unsafe-plugins
        effective_sandbox = sandbox_plugins if sandbox_plugins is not None else True
        if allow_unsafe_plugins:
            effective_sandbox = False
            click.echo("⚠️  Warning: Unsafe plugins enabled (sandboxing disabled)", err=True)

        if sum([mr_fwer, mr_hochberg, mr_fdr]) > 1:
            raise click.ClickException("Cannot combine --mr-fwer, --mr-hochberg, and --mr-fdr. Choose one.")
        if no_mr_correction and (mr_fwer or mr_hochberg or mr_fdr):
            raise click.ClickException("Cannot use --no-mr-correction with --mr-fwer, --mr-hochberg, or --mr-fdr.")
        
        # Default to Holm correction unless explicitly disabled or another method requested
        relation_correction = None
        if no_mr_correction:
            relation_correction = None
        elif mr_fwer:
            relation_correction = "holm"
        elif mr_hochberg:
            relation_correction = "hochberg"
        elif mr_fdr:
            relation_correction = "fdr"
        else:
            # Default: apply Holm correction
            relation_correction = "holm"

        from ..monitoring import resolve_monitors
        monitor_objects = []
        if monitor_names:
            try:
                monitor_objects = resolve_monitors(
                    monitor_names,
                    sandbox_plugins=effective_sandbox,
                )
            except ValueError as exc:
                click.echo(f"Error: {exc}", err=True)
                sys.exit(1)

        # Stability runs: execute evaluation N times and check for consensus
        stability_runs: list[dict[str, Any]] = []
        decisions: list[bool] = []
        
        if stability > 1:
            click.echo(f"Running stability check: {stability} runs required for consensus")
        
        for run_idx in range(stability):
            if stability > 1:
                click.echo(f"Stability run {run_idx + 1}/{stability}...")
            
            # Use different seeds for each run to detect flakiness
            run_seed = seed + run_idx if stability > 1 else seed
            
            run_result = run_eval(
                task_name=task,
                baseline_path=baseline,
                candidate_path=candidate,
                n=n,
                seed=run_seed,
                timeout_s=timeout_s,
                mem_mb=mem_mb,
                alpha=alpha,
                violation_cap=violation_cap,
                parallel=parallel,
                min_delta=min_delta,
                bootstrap_samples=bootstrap_samples,
                bayesian_samples=bayesian_samples,
                bayesian_hierarchical=bayesian_hierarchical,
                bayesian_posterior_predictive=bayesian_posterior_predictive,
                ci_method=ci_method,
                rr_ci_method=rr_ci_method,
                executor=executor,
                executor_config=parsed_executor_config,
                dispatcher=dispatcher,
                queue_config=queue_cfg,
                monitors=monitor_objects,
                failed_artifact_limit=failed_artifact_limit,
                failed_artifact_ttl_days=failed_artifact_ttl_days,
                policy_version=policy_version,
                explicit_inputs=explicit_inputs,
                min_pass_rate=min_pass_rate,
                power_target=power_target,
                policy_config=policy_payload,
                shrink_violations=shrink_violations,
                sequential_method=sequential_method,
                max_looks=max_looks,
                look_number=look_number,
                relation_correction=relation_correction,
                adaptive_testing=adaptive_testing,
                adaptive_min_sample_size=adaptive_min_sample_size,
                adaptive_check_interval=adaptive_check_interval,
                adaptive_power_threshold=adaptive_power_threshold,
                adaptive_max_sample_size=adaptive_max_sample_size,
                adaptive_group_sequential=adaptive_group_sequential,
                adaptive_sequential_method=adaptive_sequential_method,
                adaptive_max_looks=adaptive_max_looks,
            )
            
            run_decision = run_result.get("decision", {})
            run_adopt = run_decision.get("adopt", False)
            decisions.append(run_adopt)
            stability_runs.append({
                "run": run_idx + 1,
                "seed": run_seed,
                "decision": run_adopt,
                "reason": run_decision.get("reason"),
                "delta_pass_rate": run_result.get("delta_pass_rate"),
                "delta_ci": run_result.get("delta_ci"),
            })
        
        # Use the last run's result as the primary result
        result = run_result
        
        # Check for consensus
        all_adopt = all(decisions)
        all_reject = not any(decisions)
        consensus = all_adopt or all_reject
        
        if stability > 1:
            adopt_count = sum(decisions)
            click.echo(f"\nStability results: {adopt_count}/{stability} runs adopted")
            if not consensus:
                click.echo(
                    f"⚠️  FLAKY: Decisions inconsistent across {stability} runs. "
                    f"Adopt: {adopt_count}, Reject: {stability - adopt_count}",
                    err=True,
                )
                # Override decision to reject on flakiness
                result["decision"] = {
                    "adopt": False,
                    "reason": f"flaky: inconsistent decisions across {stability} runs ({adopt_count} adopt, {stability - adopt_count} reject)",
                }
            else:
                click.echo(f"✓ Consensus: All {stability} runs {'adopted' if all_adopt else 'rejected'}")
        
        # Add stability metadata to result
        if stability > 1:
            result["stability"] = {
                "runs": stability,
                "consensus": consensus,
                "adopt_count": sum(decisions),
                "reject_count": stability - sum(decisions),
                "run_details": stability_runs,
            }

        decision = result.get("decision", {})
        result.setdefault("config", {})["sandbox_plugins"] = effective_sandbox
        if relation_correction:
            result["config"]["relation_correction"] = relation_correction
        stats = result.get("statistics") or {}
        if stats:
            click.echo(
                f"Power estimate (Δ ≥ {stats.get('min_delta')}): "
                f"{stats.get('power_estimate', 0.0):.3f} "
                f"(target {stats.get('power_target', 0.8):.2f})"
            )
            if stats.get("recommended_n"):
                click.echo(f"Suggested n for target power: {stats['recommended_n']}")
            paired_stats = stats.get("paired")
            if paired_stats:
                click.echo(
                    "Discordant (baseline>candidate / candidate>baseline): "
                    f"{paired_stats.get('baseline_only', 0)}/"
                    f"{paired_stats.get('candidate_only', 0)} "
                    f"(McNemar p={paired_stats.get('mcnemar_p', 1.0):.3f})"
                )

        relation_coverage = result.get("relation_coverage") or {}
        categories = relation_coverage.get("categories") or {}
        if categories:
            correction_info = relation_coverage.get("correction")
            if correction_info:
                click.echo(
                    f"Relation correction: {correction_info.get('method')} "
                    f"(alpha={correction_info.get('alpha')})"
                )
            click.echo("Relation coverage (candidate pass rate):")
            for category, cat_stats in categories.items():
                candidate_total = cat_stats.get("candidate_total", 0)
                candidate_failures = cat_stats.get("candidate_failures", 0)
                candidate_pass_rate = cat_stats.get("candidate_pass_rate")
                if candidate_pass_rate is None:
                    rate_str = "n/a"
                else:
                    rate_str = f"{candidate_pass_rate:.3f}"
                click.echo(
                    f"  {category}: {rate_str} "
                    f"(failures {candidate_failures}/{candidate_total})"
                )

        if ci_method.lower() == "bootstrap":
            baseline_rate = result["baseline"]["pass_rate"]
            candidate_rate = result["candidate"]["pass_rate"]
            if effective_n < 100 or min(baseline_rate, candidate_rate) < 0.05 or max(baseline_rate, candidate_rate) > 0.95:
                click.echo(
                    "Warning: Bootstrap intervals can be unstable for small samples or extreme pass rates. "
                    "Consider using --ci-method=newcombe.",
                    err=True,
                )

        report_path = Path(write_report(result, directory=report_dir))

        if export_violations is not None:
            write_violation_report(export_violations, result)

        if html_report is not None:
            # Get report customization options from result config if available
            _cfg = result.get("config", {}) if isinstance(result, dict) else {}
            report_theme = _cfg.get("report_theme", "default") if isinstance(_cfg, dict) else "default"
            report_title = _cfg.get("report_title") if isinstance(_cfg, dict) else None
            show_config = _cfg.get("report_show_config", True) if isinstance(_cfg, dict) else True
            show_metadata = _cfg.get("report_show_metadata", True) if isinstance(_cfg, dict) else True
            
            render_html_report(
                result,
                html_report,
                theme=report_theme,
                title=report_title,
                show_config=show_config,
                show_metadata=show_metadata,
            )

        replay_info = result.get("replay") or {}
        cases_path = None
        if report_dir:
            cases_path = report_path.with_name(report_path.stem + "_cases.json")
            cases_path.write_text(json.dumps(result.get("cases", []), indent=2), encoding="utf-8")
            click.echo(f"Replay cases saved to: {cases_path}")

        if replay_info and cases_path is not None:
            replay_cmd = [
                "metamorphic-guard",
                "--task",
                replay_info.get("task", task),
                "--baseline",
                baseline,
                "--candidate",
                candidate,
                "--replay-input",
                str(cases_path),
                "--min-delta",
                str(min_delta),
                "--min-pass-rate",
                str(min_pass_rate),
                "--ci-method",
                ci_method,
            ]
            click.echo("Replay command:")
            click.echo("  " + " ".join(replay_cmd))

        if junit_report is not None:
            render_junit_report(result, junit_report)
            click.echo(f"JUnit report written to {junit_report}")

        monitor_alerts = collect_alerts(result.get("monitors", {}))
        if alert_webhooks:
            try:
                send_webhook_alerts(
                    monitor_alerts,
                    alert_webhooks,
                    metadata={
                        "task": task,
                        "decision": decision,
                        "run_id": result.get("job_metadata", {}).get("run_id"),
                        "policy_version": policy_version,
                        "sandbox_plugins": effective_sandbox,
                    },
                )
            except Exception as exc:
                click.echo(f"Warning: failed to dispatch alert webhooks: {exc}", err=True)

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

        log_event(
            "run_eval_decision",
            adopt=decision["adopt"],
            reason=decision["reason"],
            delta=result["delta_pass_rate"],
            candidate_pass_rate=result["candidate"]["pass_rate"],
            baseline_pass_rate=result["baseline"]["pass_rate"],
            run_id=result.get("job_metadata", {}).get("run_id"),
            policy_version=policy_version,
            sandbox_plugins=effective_sandbox,
        )

        # Export trace to OpenTelemetry if enabled
        if otlp_endpoint:
            try:
                from ..telemetry import trace_evaluation
                trace_evaluation(
                    task_name=task,
                    baseline_path=baseline,
                    candidate_path=candidate,
                    n=n,
                    result=result,
                )
            except Exception:
                # Silently fail if telemetry export fails
                pass

        from .progress import echo_success, echo_error
        
        if decision["adopt"]:
            echo_success("Candidate accepted!")
            sys.exit(0)

        echo_error("Candidate rejected!")
        sys.exit(1)

    except KeyboardInterrupt:  # pragma: no cover - defensive surface
        from .progress import echo_warning
        echo_warning("Evaluation interrupted by user.")
        sys.exit(1)

    except Exception as exc:  # pragma: no cover - defensive surface
        from .progress import echo_error
        echo_error("Error during evaluation", error=exc)
        sys.exit(1)
    finally:
        close_logging()

