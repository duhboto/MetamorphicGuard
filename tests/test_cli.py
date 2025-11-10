"""Tests for CLI functionality."""

import json
import os
import re
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from metamorphic_guard.cli import main


def test_cli_help():
    """Test CLI help output."""
    runner = CliRunner()
    result = runner.invoke(main, ['--help'])
    
    assert result.exit_code == 0
    assert "Compare baseline and candidate implementations" in result.output


def test_cli_invalid_task():
    """Test CLI with invalid task name."""
    runner = CliRunner()
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py') as f:
        f.write('def solve(x): return x')
        baseline_file = f.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py') as f2:
            f2.write('def solve(x): return x')
            candidate_file = f2.name
            
            result = runner.invoke(main, [
                '--task', 'nonexistent_task',
                '--baseline', baseline_file,
                '--candidate', candidate_file,
                '--n', '10'
            ])
    
    assert result.exit_code != 0
    assert "not found" in result.output


def test_cli_missing_files():
    """Test CLI with missing files."""
    runner = CliRunner()
    
    result = runner.invoke(main, [
        '--task', 'top_k',
        '--baseline', 'nonexistent.py',
        '--candidate', 'nonexistent.py',
        '--n', '10'
    ])
    
    assert result.exit_code != 0


def test_cli_successful_run():
    """Test CLI with successful evaluation."""
    runner = CliRunner()
    
    # Create test files - make candidate slightly better
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('''
def solve(L, k):
    if not L or k <= 0:
        return []
    return sorted(L, reverse=True)[:min(k, len(L))]
''')
        baseline_file = f.name
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('''
def solve(L, k):
    if not L or k <= 0:
        return []
    # Slightly different implementation that should be equivalent
    if k >= len(L):
        return sorted(L, reverse=True)
    return sorted(L, reverse=True)[:k]
''')
        candidate_file = f.name
    
    try:
        with tempfile.TemporaryDirectory() as report_dir:
            result = runner.invoke(main, [
                '--task', 'top_k',
                '--baseline', baseline_file,
                '--candidate', candidate_file,
                '--n', '10',
                '--seed', '42',
                '--improve-delta', '0.0',
                '--report-dir', report_dir,
                '--executor-config', '{}',
                '--export-violations', str(Path(report_dir) / "violations.json"),
                '--html-report', str(Path(report_dir) / "report.html"),
            ])

            # Should succeed (exit code 0 for acceptance)
            assert result.exit_code == 0
            assert "EVALUATION SUMMARY" in result.output
            assert "Report saved to:" in result.output

            match = re.search(r"Report saved to: (.+)", result.output)
            assert match, "Report path not found in CLI output"
            report_path = Path(match.group(1).strip())
            assert report_path.parent == Path(report_dir)
            report_data = json.loads(Path(report_path).read_text())
            assert report_data["config"]["ci_method"] == "bootstrap"
            assert "spec_fingerprint" in report_data
            assert "environment" in report_data
            assert "relative_risk" in report_data
            assert "relative_risk_ci" in report_data
            violations_file = Path(report_dir) / "violations.json"
            assert violations_file.exists()
            violations_payload = json.loads(violations_file.read_text())
            assert violations_payload["baseline"]["prop_violations"] == []
            assert violations_payload["candidate"]["mr_violations"] == []

            html_report_path = Path(report_dir) / "report.html"
            assert html_report_path.exists()
            html_content = html_report_path.read_text()
            assert "<html" in html_content.lower()

    finally:
        os.unlink(baseline_file)
        os.unlink(candidate_file)


def test_cli_config_file(tmp_path):
    """Defaults can be provided via a TOML config file."""
    runner = CliRunner()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('def solve(L, k):\n    return sorted(L, reverse=True)[:min(len(L), k)]\n')
        baseline_file = f.name

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('def solve(L, k):\n    return sorted(L, reverse=True)[:min(len(L), k)]\n')
        candidate_file = f.name

    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join([
            f'task = "top_k"',
            f'baseline = "{baseline_file}"',
            f'candidate = "{candidate_file}"',
            "n = 8",
            "seed = 99",
            "improve_delta = 0.0",
        ]),
        encoding="utf-8",
    )

    try:
        with tempfile.TemporaryDirectory() as report_dir:
            result = runner.invoke(main, [
                '--config', str(config_path),
                '--report-dir', report_dir,
            ])

            assert result.exit_code == 0
            match = re.search(r"Report saved to: (.+)", result.output)
            assert match
            report_path = Path(match.group(1).strip())
            report_data = json.loads(report_path.read_text())
            assert report_data["n"] == 8
            assert report_data["seed"] == 99
    finally:
        os.unlink(baseline_file)
        os.unlink(candidate_file)


def test_cli_config_override(tmp_path):
    """Explicit CLI arguments override config defaults."""
    runner = CliRunner()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('def solve(L, k):\n    return sorted(L, reverse=True)[:min(len(L), k)]\n')
        baseline_file = f.name

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('def solve(L, k):\n    return sorted(L, reverse=True)[:min(len(L), k)]\n')
        candidate_file = f.name

    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join([
            f'task = "top_k"',
            f'baseline = "{baseline_file}"',
            f'candidate = "{candidate_file}"',
            "n = 12",
            "seed = 11",
            "improve_delta = 0.0",
        ]),
        encoding="utf-8",
    )

    try:
        with tempfile.TemporaryDirectory() as report_dir:
            result = runner.invoke(main, [
                '--config', str(config_path),
                '--n', '3',
                '--seed', '7',
                '--report-dir', report_dir,
            ])

            assert result.exit_code == 0
            match = re.search(r"Report saved to: (.+)", result.output)
            assert match
            report_path = Path(match.group(1).strip())
            report = json.loads(report_path.read_text())
            assert report["n"] == 3
            assert report["seed"] == 7
    finally:
        os.unlink(baseline_file)
        os.unlink(candidate_file)


def test_cli_init_command(tmp_path):
    runner = CliRunner()
    config_path = tmp_path / "metaguard.toml"

    result = runner.invoke(main, [
        "init",
        "--path",
        str(config_path),
        "--task",
        "top_k",
        "--baseline",
        "baseline.py",
        "--candidate",
        "candidate.py",
        "--monitor",
        "latency",
        "--distributed",
    ])

    assert result.exit_code == 0
    contents = config_path.read_text()
    assert "metamorphic_guard" in contents
    assert "dispatcher" in contents


def test_cli_invalid_executor_config():
    """Executor config must be valid JSON."""
    runner = CliRunner()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('def solve(x): return x')
        baseline_file = f.name

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('def solve(x): return x')
        candidate_file = f.name

    try:
        result = runner.invoke(main, [
            '--task', 'top_k',
            '--baseline', baseline_file,
            '--candidate', candidate_file,
            '--n', '1',
            '--executor-config', '{not-json',
        ])

        assert result.exit_code != 0
        assert "Invalid executor config" in result.output
    finally:
        os.unlink(baseline_file)
        os.unlink(candidate_file)


def test_cli_latency_monitor(tmp_path):
    runner = CliRunner()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('def solve(L, k):\n    return sorted(L, reverse=True)[:min(len(L), k)]\n')
        baseline_file = f.name

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('def solve(L, k):\n    return sorted(L, reverse=True)[:min(len(L), k)]\n')
        candidate_file = f.name

    try:
        with tempfile.TemporaryDirectory() as report_dir:
            result = runner.invoke(main, [
                '--task', 'top_k',
                '--baseline', baseline_file,
                '--candidate', candidate_file,
                '--n', '5',
                '--improve-delta', '0.0',
                '--monitor', 'latency',
                '--report-dir', report_dir,
            ])

            assert result.exit_code == 0
            match = re.search(r"Report saved to: (.+)", result.output)
            assert match
            report_path = Path(match.group(1).strip())
            data = json.loads(report_path.read_text())
            assert "monitors" in data
            assert "LatencyMonitor" in data["monitors"]
    finally:
        os.unlink(baseline_file)
        os.unlink(candidate_file)
