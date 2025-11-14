"""
Agent trace recording and replay commands.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from ..agent_tracing import AgentTrace, AgentTraceRecorder, extract_trace_from_result, replay_trace
from ..plugins import executor_plugins


@click.group("trace")
def trace_group() -> None:
    """Agent trace recording and replay commands."""
    pass


@trace_group.command("extract")
@click.option(
    "--from",
    "report_file",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="JSON report file to extract traces from",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Output file for traces (default: <report_dir>/traces.json)",
)
@click.option(
    "--case-index",
    type=int,
    default=None,
    help="Extract trace for specific case index only",
)
@click.option(
    "--role",
    type=click.Choice(["baseline", "candidate", "both"]),
    default="both",
    help="Extract traces for baseline, candidate, or both",
)
def extract_traces_command(
    report_file: Path,
    output: Path | None,
    case_index: int | None,
    role: str,
) -> None:
    """Extract agent traces from an evaluation report."""
    try:
        with open(report_file, "r", encoding="utf-8") as f:
            report_data = json.load(f)
    except Exception as e:
        click.echo(f"Error reading {report_file}: {e}", err=True)
        sys.exit(1)
    
    # Extract traces from results
    traces: list[AgentTrace] = []
    
    # Get baseline and candidate results
    baseline_results = report_data.get("baseline", {}).get("results", [])
    candidate_results = report_data.get("candidate", {}).get("results", [])
    
    # Extract baseline traces
    if role in ("baseline", "both") and baseline_results:
        for idx, result in enumerate(baseline_results):
            if case_index is not None and idx != case_index:
                continue
            trace = extract_trace_from_result(result, idx, "baseline")
            traces.append(trace)
    
    # Extract candidate traces
    if role in ("candidate", "both") and candidate_results:
        for idx, result in enumerate(candidate_results):
            if case_index is not None and idx != case_index:
                continue
            trace = extract_trace_from_result(result, idx, "candidate")
            traces.append(trace)
    
    # Determine output file
    if output is None:
        output = report_file.parent / "traces.json"
    
    # Save traces
    traces_data = [trace.to_dict() for trace in traces]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(traces_data, indent=2), encoding="utf-8")
    
    click.echo(f"Extracted {len(traces)} trace(s) to {output}")


@trace_group.command("replay")
@click.option(
    "--from",
    "trace_file",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="JSON trace file to replay",
)
@click.option(
    "--case-index",
    type=int,
    default=None,
    help="Replay trace for specific case index (default: replay all)",
)
@click.option(
    "--executor",
    type=str,
    default="openai",
    help="Executor to use for replay (default: openai)",
)
@click.option(
    "--executor-config",
    type=str,
    default=None,
    help="JSON string with executor configuration",
)
def replay_traces_command(
    trace_file: Path,
    case_index: int | None,
    executor: str,
    executor_config: str | None,
) -> None:
    """Replay agent traces using an executor."""
    try:
        traces_data = json.loads(trace_file.read_text(encoding="utf-8"))
        traces = [AgentTrace.from_dict(td) for td in traces_data]
    except Exception as e:
        click.echo(f"Error reading {trace_file}: {e}", err=True)
        sys.exit(1)
    
    # Filter by case index if specified
    if case_index is not None:
        traces = [t for t in traces if t.case_index == case_index]
    
    if not traces:
        click.echo("No traces found", err=True)
        sys.exit(1)
    
    # Parse executor config
    parsed_config = {}
    if executor_config:
        try:
            parsed_config = json.loads(executor_config)
        except Exception as e:
            click.echo(f"Error parsing executor config: {e}", err=True)
            sys.exit(1)
    
    # Get executor
    executor_registry = executor_plugins()
    executor_def = executor_registry.get(executor)
    if executor_def is None:
        click.echo(f"Executor '{executor}' not found. Available: {list(executor_registry.keys())}", err=True)
        sys.exit(1)
    
    executor_instance = executor_def.factory(config=parsed_config)
    
    # Replay traces
    results = []
    for trace in traces:
        click.echo(f"Replaying trace {trace.case_index} ({trace.role})...")
        try:
            result = replay_trace(trace, executor_instance)
            results.append({
                "trace": trace.to_dict(),
                "result": result,
            })
        except Exception as e:
            click.echo(f"Error replaying trace {trace.case_index}: {e}", err=True)
            results.append({
                "trace": trace.to_dict(),
                "error": str(e),
            })
    
    # Output results
    output = trace_file.parent / f"replay_{trace_file.stem}.json"
    output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    click.echo(f"Replayed {len(results)} trace(s). Results saved to {output}")


@trace_group.command("inspect")
@click.option(
    "--from",
    "trace_file",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="JSON trace file to inspect",
)
@click.option(
    "--case-index",
    type=int,
    default=None,
    help="Inspect specific case index only",
)
def inspect_traces_command(
    trace_file: Path,
    case_index: int | None,
) -> None:
    """Inspect agent traces."""
    try:
        traces_data = json.loads(trace_file.read_text(encoding="utf-8"))
        traces = [AgentTrace.from_dict(td) for td in traces_data]
    except Exception as e:
        click.echo(f"Error reading {trace_file}: {e}", err=True)
        sys.exit(1)
    
    # Filter by case index if specified
    if case_index is not None:
        traces = [t for t in traces if t.case_index == case_index]
    
    if not traces:
        click.echo("No traces found", err=True)
        sys.exit(1)
    
    # Display traces
    for trace in traces:
        click.echo(f"\n{'='*60}")
        click.echo(f"Trace {trace.case_index} ({trace.role})")
        click.echo(f"Timestamp: {trace.timestamp}")
        click.echo(f"Conversation length: {len(trace.conversation_history)} messages")
        click.echo(f"Intermediate steps: {len(trace.intermediate_steps)}")
        click.echo(f"Tool calls: {len(trace.tool_calls)}")
        if trace.final_output:
            click.echo(f"Final output: {trace.final_output[:100]}...")
        if trace.metadata:
            click.echo(f"Metadata: {json.dumps(trace.metadata, indent=2)}")

