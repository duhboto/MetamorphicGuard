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
        result = runner.invoke(main, [
            '--task', 'top_k',
            '--baseline', baseline_file,
            '--candidate', candidate_file,
            '--n', '10',
            '--seed', '42',
            '--improve-delta', '0.0'
        ])

        # Should succeed (exit code 0 for acceptance)
        assert result.exit_code == 0
        assert "EVALUATION SUMMARY" in result.output
        assert "Report saved to:" in result.output

        match = re.search(r"Report saved to: (.+)", result.output)
        assert match, "Report path not found in CLI output"
        report_path = Path(match.group(1).strip())
        report_data = json.loads(Path(report_path).read_text())
        assert report_data["config"]["ci_method"] == "bootstrap"
        assert "spec_fingerprint" in report_data
        assert "environment" in report_data
        assert "relative_risk" in report_data
        assert "relative_risk_ci" in report_data

    finally:
        os.unlink(baseline_file)
        os.unlink(candidate_file)
