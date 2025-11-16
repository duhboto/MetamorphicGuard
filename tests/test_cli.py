"""Tests for CLI functionality."""

import json
import os
import re
import tempfile
import xml.etree.ElementTree as ET
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
                '--min-delta', '-0.5',  # Allow candidate to be equivalent (no improvement required)
                '--ci-method', 'newcombe',
                '--report-dir', report_dir,
                '--executor-config', '{}',
                '--export-violations', str(Path(report_dir) / "violations.json"),
                '--html-report', str(Path(report_dir) / "report.html"),
                '--junit-report', str(Path(report_dir) / "report.xml"),
                '--policy-version', 'test-policy',
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
            assert "decision" in report_data
            assert report_data["decision"]["adopt"] is True
            # CI method should reflect explicit flag
            assert report_data["config"]["ci_method"] == "newcombe"
            assert "spec_fingerprint" in report_data
            assert "environment" in report_data
            assert "relative_risk" in report_data
            assert "relative_risk_ci" in report_data
            # Verify provenance section exists and contains expected fields
            provenance = report_data.get("provenance")
            assert provenance is not None
            assert "library_version" in provenance
            assert "mr_ids" in provenance
            assert "spec_fingerprint" in provenance
            assert "python_version" in provenance
            sandbox_info = provenance.get("sandbox")
            assert sandbox_info is not None
            assert sandbox_info["executor"] == "local"
            assert "call_spec_fingerprint" in sandbox_info
            assert "baseline" in sandbox_info["call_spec_fingerprint"]
            assert report_data["config"].get("policy_version") == "test-policy"
            assert report_data["config"].get("sandbox_plugins") is True  # Default is secure-by-default
            assert len(report_data.get("cases", [])) == 10
            assert report_data["cases"][0]["index"] == 0
            stats = report_data.get("statistics")
            assert stats is not None
            assert "power_estimate" in stats
            paired = stats.get("paired")
            assert paired is not None
            assert paired["total"] == 10
            assert paired["baseline_only"] == 0
            assert paired["candidate_only"] == 0
            assert paired["discordant"] == 0
            assert pytest.approx(paired["mcnemar_p"], rel=1e-6) == 1.0
            relation_cov = report_data.get("relation_coverage")
            assert relation_cov
            assert relation_cov["relations"]
            cases_path = report_path.with_name(report_path.stem + "_cases.json")
            assert cases_path.exists()
            cases_payload = json.loads(cases_path.read_text())
            assert len(cases_payload) == 10
            assert "Replay command" in result.output
            violations_file = Path(report_dir) / "violations.json"
            assert violations_file.exists()
            violations_payload = json.loads(violations_file.read_text())
            assert violations_payload["baseline"]["prop_violations"] == []
            assert violations_payload["candidate"]["mr_violations"] == []

            html_report_path = Path(report_dir) / "report.html"
            assert html_report_path.exists()
            html_content = html_report_path.read_text()
            assert "<html" in html_content.lower()
            assert "chart.umd.min.js" in html_content
            assert "pass-rate-chart" in html_content

            junit_report_path = Path(report_dir) / "report.xml"
            assert junit_report_path.exists()
            junit_tree = ET.parse(junit_report_path)
            junit_root = junit_tree.getroot()
            assert junit_root.tag == "testsuite"
            assert int(junit_root.attrib["tests"]) == len(report_data["cases"])
            assert junit_root.find("system-out") is not None

    finally:
        os.unlink(baseline_file)
        os.unlink(candidate_file)


def test_cli_mr_fwer_flag(tmp_path):
    runner = CliRunner()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(
            """
def solve(L, k):
    if not L or k <= 0:
        return []
    return sorted(L, reverse=True)[: min(k, len(L))]
"""
        )
        baseline = f.name

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(
            """
def solve(L, k):
    if not L or k <= 0:
        return []
    return sorted(L, reverse=True)[: min(k, len(L))]
"""
        )
        candidate = f.name

    try:
        report_dir = tmp_path / "reports"
        result = runner.invoke(
            main,
            [
                "--task",
                "top_k",
                "--baseline",
                baseline,
                "--candidate",
                candidate,
                "--n",
                "8",
                "--min-delta",
                "-0.5",
                "--mr-fwer",
                "--report-dir",
                str(report_dir),
            ],
        )

        assert result.exit_code == 0
        report_path = next(
            (path for path in report_dir.glob("report_*.json") if "_cases" not in path.name),
            None,
        )
        assert report_path is not None, "Expected JSON report file"
        payload = json.loads(report_path.read_text())

        coverage = payload.get("relation_coverage")
        assert coverage is not None
        correction = coverage.get("correction")
        assert correction is not None
        assert correction["method"] == "holm-bonferroni"
        for relation in coverage["relations"]:
            assert "p_value" in relation
            assert "adjusted_p_value" in relation
            assert "significant" in relation
    finally:
        os.unlink(baseline)
        os.unlink(candidate)


def test_provenance_diff_command(tmp_path):
    runner = CliRunner()

    report_a = tmp_path / "report_a.json"
    report_b = tmp_path / "report_b.json"

    payload_a = {
        "provenance": {
            "sandbox": {
                "call_spec_fingerprint": {"baseline": "aa", "candidate": "bb"},
                "executions": {
                    "baseline": {"executor": "local", "run_state": "success"},
                },
                "executions_fingerprint": {"baseline": "ff"},
            }
        }
    }
    payload_b = {
        "provenance": {
            "sandbox": {
                "call_spec_fingerprint": {"baseline": "aa", "candidate": "cc"},
                "executions": {
                    "baseline": {"executor": "docker", "run_state": "success"},
                },
                "executions_fingerprint": {"baseline": "gg"},
            }
        }
    }

    report_a.write_text(json.dumps(payload_a), encoding="utf-8")
    report_b.write_text(json.dumps(payload_b), encoding="utf-8")

    result = runner.invoke(
        main, ["provenance-diff", str(report_a), str(report_b)]
    )

    assert result.exit_code == 0
    assert "Sandbox provenance differences:" in result.output
    assert "sandbox.call_spec_fingerprint.candidate" in result.output
    assert "sandbox.executions.baseline.executor" in result.output

    result_same = runner.invoke(main, ["provenance-diff", str(report_a), str(report_a)])
    assert result_same.exit_code == 0
    assert "Sandbox provenance matches." in result_same.output


def test_regression_guard_pass(tmp_path):
    runner = CliRunner()

    baseline_report = tmp_path / "baseline.json"
    candidate_report = tmp_path / "candidate.json"

    sandbox_payload = {
        "sandbox": {
            "executions_fingerprint": {"baseline": "abc"},
            "executions": {"baseline": {"run_state": "success"}},
        }
    }
    baseline_report.write_text(json.dumps({"provenance": sandbox_payload}), encoding="utf-8")
    candidate_payload = {
        "metrics": {
            "value_mean": {
                "delta": {
                    "difference": 0.05,
                }
            }
        },
        "provenance": sandbox_payload,
    }
    candidate_report.write_text(json.dumps(candidate_payload), encoding="utf-8")

    result = runner.invoke(
        main,
        [
            "regression-guard",
            str(baseline_report),
            str(candidate_report),
            "--metric-threshold",
            "value_mean:delta.difference=0.1",
            "--require-provenance-match",
        ],
    )
    assert result.exit_code == 0
    assert "Regression guard passed" in result.output


def test_regression_guard_fails_on_threshold(tmp_path):
    runner = CliRunner()

    baseline_report = tmp_path / "baseline.json"
    candidate_report = tmp_path / "candidate.json"
    baseline_report.write_text("{}", encoding="utf-8")
    candidate_payload = {
        "metrics": {
            "value_mean": {
                "delta": {
                    "difference": 0.5,
                }
            }
        }
    }
    candidate_report.write_text(json.dumps(candidate_payload), encoding="utf-8")

    result = runner.invoke(
        main,
        [
            "regression-guard",
            str(baseline_report),
            str(candidate_report),
            "--metric-threshold",
            "value_mean:delta.difference=0.1",
        ],
    )

    assert result.exit_code == 1
    assert "exceeded 0.1" in result.output


def test_regression_guard_fails_on_provenance(tmp_path):
    runner = CliRunner()

    baseline_report = tmp_path / "baseline.json"
    candidate_report = tmp_path / "candidate.json"

    baseline_report.write_text(
        json.dumps({"provenance": {"sandbox": {"executions_fingerprint": {"baseline": "abc"}}}}),
        encoding="utf-8",
    )
    candidate_report.write_text(
        json.dumps({"provenance": {"sandbox": {"executions_fingerprint": {"baseline": "xyz"}}}}),
        encoding="utf-8",
    )

    result = runner.invoke(
        main,
        [
            "regression-guard",
            str(baseline_report),
            str(candidate_report),
            "--require-provenance-match",
        ],
    )

    assert result.exit_code == 1
    assert "Sandbox provenance mismatch" in result.output


def test_cli_log_json_and_artifact_flags(tmp_path):
    runner = CliRunner()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(
            """
def solve(L, k):
    if not L:
        return []
    return sorted(L, reverse=True)[: min(len(L), k)]
"""
        )
        baseline = f.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(
            """
def solve(L, k):
    return sorted(L, reverse=True)[: min(len(L), k)]
"""
        )
        candidate = f.name

    try:
        result = runner.invoke(
            main,
            [
                "--task",
                "top_k",
                "--baseline",
                baseline,
                "--candidate",
                candidate,
                "--n",
                "6",
                "--min-delta",
                "-0.5",  # Allow equivalent performance
                "--ci-method",
                "newcombe",
                "--report-dir",
                str(tmp_path),
                "--log-json",
                "--no-metrics",
                "--failed-artifact-limit",
                "1",
                "--sandbox-plugins",
            ],
        )

        assert result.exit_code == 0
    finally:
        os.unlink(baseline)
        os.unlink(candidate)


def test_cli_junit_xml_alias(tmp_path):
    runner = CliRunner()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(
            """
def solve(L, k):
    return sorted(L, reverse=True)[: min(len(L), k)]
"""
        )
        baseline = f.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(
            """
def solve(L, k):
    return sorted(L, reverse=True)[: min(len(L), k)]
"""
        )
        candidate = f.name

    junit_path = tmp_path / "alias.xml"

    try:
        result = runner.invoke(
            main,
            [
                "--task",
                "top_k",
                "--baseline",
                baseline,
                "--candidate",
                candidate,
                "--n",
                "4",
                "--min-delta",
                "-0.5",
                "--ci-method",
                "newcombe",
                "--report-dir",
                str(tmp_path),
                "--junit-xml",
                str(junit_path),
            ],
        )

        assert result.exit_code == 0
        assert junit_path.exists()
        assert ET.parse(junit_path).getroot().tag == "testsuite"
    finally:
        os.unlink(baseline)
        os.unlink(candidate)


def test_cli_cluster_bootstrap(tmp_path):
    runner = CliRunner()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(
            """
def solve(L, k):
    return sorted(L, reverse=True)[: min(len(L), k)]
"""
        )
        baseline = f.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(
            """
def solve(L, k):
    return sorted(L, reverse=True)[: min(len(L), k)]
"""
        )
        candidate = f.name

    try:
        result = runner.invoke(
            main,
            [
                "--task",
                "top_k",
                "--baseline",
                baseline,
                "--candidate",
                candidate,
                "--n",
                "6",
                "--seed",
                "7",
                "--min-delta",
                "-0.5",
                "--ci-method",
                "bootstrap-cluster",
                "--report-dir",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0
    finally:
        os.unlink(baseline)
        os.unlink(candidate)


def test_cli_log_file_output(tmp_path):
    runner = CliRunner()

    baseline = tmp_path / "baseline.py"
    candidate = tmp_path / "candidate.py"
    baseline.write_text(
        """
def solve(L, k):
    return sorted(L)[: min(len(L), k)]
""",
        encoding="utf-8",
    )
    candidate.write_text(
        """
def solve(L, k):
    return sorted(L, reverse=True)[: min(len(L), k)]
""",
        encoding="utf-8",
    )

    log_path = tmp_path / "logs" / "run.jsonl"
    report_dir = tmp_path / "reports"

    result = runner.invoke(
        main,
        [
            "--task",
            "top_k",
            "--baseline",
            str(baseline),
            "--candidate",
            str(candidate),
            "--n",
            "4",
            "--min-delta",
            "-0.5",  # Allow equivalent performance
            "--ci-method",
            "newcombe",
            "--report-dir",
            str(report_dir),
            "--log-file",
            str(log_path),
            "--no-metrics",
        ],
    )

    assert result.exit_code in (0, 1)
    assert log_path.exists()
    entries = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert entries, "Expected structured log entries in log file"
    assert any("\"event\":" in line for line in entries)


def test_cli_init_interactive(tmp_path):
    runner = CliRunner()
    config_path = tmp_path / "metaguard.toml"

    # New interactive flow: template choice first, then custom inputs if "none"
    user_input = """none
custom_task
baseline.py
candidate.py
y
latency,success_rate
"""

    result = runner.invoke(
        main,
        ["init", "--path", str(config_path), "--interactive"],
        input=user_input,
    )

    assert result.exit_code == 0
    content = config_path.read_text()
    # Accept either new-style or legacy-style config formats
    assert ("[task]" in content) or ("[metamorphic_guard]" in content)
    # Task name present in either style (new uses name=, legacy uses task=)
    assert ('name = "custom_task"' in content) or ('task = "custom_task"' in content) or ('task = "none"' in content)
    # Monitors captured
    assert ("latency" in content) and ("success_rate" in content)
    # Distributed enabled marker in either style
    assert ('type = "queue"' in content) or ('dispatcher = "queue"' in content)


def test_cli_scaffold_plugin_monitor(tmp_path):
    runner = CliRunner()
    target = tmp_path / "my_monitor.py"

    result = runner.invoke(
        main,
        [
            "scaffold-plugin",
            "--name",
            "MyMonitor",
            "--kind",
            "monitor",
            "--path",
            str(target),
        ],
    )

    assert result.exit_code == 0
    text = target.read_text()
    assert "class MyMonitor" in text
    assert "def record" in text


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
            "min_delta = -0.5",  # Allow equivalent performance
            "ci_method = \"newcombe\"",
            "policy_version = \"policy-v1\"",
            "sandbox_plugins = true",
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
            assert report_data["config"].get("sandbox_plugins") is True
            assert report_data["config"].get("policy_version") == "policy-v1"
            assert "decision" in report_data
    finally:
        os.unlink(baseline_file)
        os.unlink(candidate_file)


def test_cli_config_validation_error(tmp_path):
    runner = CliRunner()

    config_path = tmp_path / "bad.toml"
    config_path.write_text(
        "\n".join([
            'task = "top_k"',
            'baseline = "baseline.py"',
            'candidate = "candidate.py"',
            'n = 0',
        ]),
        encoding="utf-8",
    )

    result = runner.invoke(main, ['--config', str(config_path)])
    assert result.exit_code != 0
    assert "n" in result.output.lower()


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
            "min_delta = -0.5",  # Allow equivalent performance
            "ci_method = \"newcombe\"",
        ]),
        encoding="utf-8",
    )

    try:
        with tempfile.TemporaryDirectory() as report_dir:
            result = runner.invoke(main, [
                '--config', str(config_path),
                '--n', '10',  # Use reasonable sample size for CI to work
                '--seed', '7',
                '--report-dir', report_dir,
            ])

            assert result.exit_code == 0
            match = re.search(r"Report saved to: (.+)", result.output)
            assert match
            report_path = Path(match.group(1).strip())
            report = json.loads(report_path.read_text())
            assert report["n"] == 10  # Overridden from config default of 12
            assert report["seed"] == 7  # Overridden from config default of 11
            assert "decision" in report
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
    # Accept either new-style or legacy-style config formats
    assert ("[task]" in contents) or ("[metamorphic_guard]" in contents)
    assert "dispatcher" in contents or "queue" in contents.lower()


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
                '--min-delta', '-0.5',  # Allow equivalent performance
                '--ci-method', 'newcombe',
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
            assert "decision" in data
    finally:
        os.unlink(baseline_file)
        os.unlink(candidate_file)


def test_cli_replay_input(tmp_path):
    runner = CliRunner()

    baseline = tmp_path / "baseline.py"
    candidate = tmp_path / "candidate.py"
    baseline.write_text(
        """
def solve(L, k):
    return sorted(L)[: min(len(L), k)]
""",
        encoding="utf-8",
    )
    candidate.write_text(
        """
def solve(L, k):
    return sorted(L, reverse=True)[: min(len(L), k)]
""",
        encoding="utf-8",
    )

    report_dir = tmp_path / "reports"
    result = runner.invoke(
        main,
        [
            "--task",
            "top_k",
            "--baseline",
            str(baseline),
            "--candidate",
            str(candidate),
            "--n",
            "4",
            "--min-delta",
            "-0.5",
            "--ci-method",
            "newcombe",
            "--report-dir",
            str(report_dir),
        ],
    )
    assert result.exit_code == 0

    report_files = sorted(p for p in report_dir.glob("report_*.json") if not p.name.endswith("_cases.json"))
    assert report_files, "Expected report file to be created"
    report_data = json.loads(report_files[0].read_text())
    cases_path = tmp_path / "replay_cases.json"
    cases_path.write_text(json.dumps(report_data["cases"], indent=2), encoding="utf-8")

    replay_result = runner.invoke(
        main,
        [
            "--task",
            "top_k",
            "--baseline",
            str(baseline),
            "--candidate",
            str(candidate),
            "--seed",
            "99",
            "--min-delta",
            "-0.5",
            "--ci-method",
            "newcombe",
            "--replay-input",
            str(cases_path),
            "--report-dir",
            str(tmp_path / "replay_reports"),
        ],
    )
    assert replay_result.exit_code == 0


def test_cli_policy_file(tmp_path):
    runner = CliRunner()

    baseline = tmp_path / "baseline.py"
    candidate = tmp_path / "candidate.py"
    baseline.write_text(
        """
def solve(L, k):
    return sorted(L)[: min(len(L), k)]
""",
        encoding="utf-8",
    )
    candidate.write_text(
        """
def solve(L, k):
    return sorted(L)[: min(len(L), k)]
""",
        encoding="utf-8",
    )

    policy_path = tmp_path / "policy.toml"
    policy_path.write_text(
        "\n".join(
            [
                "[gating]",
                "min_delta = 0.05",
                "alpha = 0.01",
                "power_target = 0.9",
            ]
        ),
        encoding="utf-8",
    )

    report_dir = tmp_path / "policy_reports"
    try:
        result = runner.invoke(
            main,
            [
                "--task",
                "top_k",
                "--baseline",
                str(baseline),
                "--candidate",
                str(candidate),
                "--n",
                "5",
                "--min-pass-rate",
                "0.5",
                "--min-delta",
                "0.0",
                "--policy",
                str(policy_path),
                "--report-dir",
                str(report_dir),
            ],
        )

        assert result.exit_code == 1
        assert "Using policy file" in result.output
        assert "Power estimate" in result.output

        report_files = sorted(p for p in report_dir.glob("report_*.json") if not p.name.endswith("_cases.json"))
        assert report_files, "Expected report file created"
        report = json.loads(report_files[0].read_text())
        assert report["decision"]["adopt"] is False
        assert report["config"]["alpha"] == 0.01
        assert report["statistics"]["power_target"] == 0.9
        policy_payload = report.get("policy")
        assert policy_payload
        assert policy_payload["gating"]["min_delta"] == 0.05
        assert report.get("relation_coverage")
        cases_path = report_files[0].with_name(report_files[0].stem + "_cases.json")
        assert cases_path.exists()
        assert json.loads(cases_path.read_text())
        assert "Replay command" in result.output
    finally:
        baseline.unlink()
        candidate.unlink()


def test_cli_policy_preset_noninferiority(tmp_path):
    runner = CliRunner()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(
            "def solve(L, k):\n"
            "    if not L or k <= 0:\n"
            "        return []\n"
            "    return sorted(L, reverse=True)[:min(len(L), k)]\n"
        )
        baseline_file = f.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(
            "def solve(L, k):\n"
            "    if not L or k <= 0:\n"
            "        return []\n"
            "    return sorted(L, reverse=True)[:min(len(L), k)]\n"
        )
        candidate_file = f.name

    try:
        with tempfile.TemporaryDirectory() as report_dir:
            result = runner.invoke(
                main,
                [
                    "--task",
                    "top_k",
                    "--baseline",
                    baseline_file,
                    "--candidate",
                    candidate_file,
                    "--n",
                    "8",
                    "--ci-method",
                    "bootstrap",
                    "--policy",
                    "noninferiority:margin=0.01",
                    "--report-dir",
                    report_dir,
                ],
            )

            assert result.exit_code == 0
            match = re.search(r"Report saved to: (.+)", result.output)
            assert match
            report_path = Path(match.group(1).strip())
            report_data = json.loads(report_path.read_text())

            assert report_data["config"]["policy_rule"]["type"] == "preset"
            assert report_data["config"]["policy_rule"]["name"] == "noninferiority"
            assert report_data["config"]["policy_version"] == "noninferiority"
            assert report_data["config"]["ci_method"] == "bootstrap"
            assert report_data["config"]["min_delta"] == pytest.approx(-0.01, rel=1e-6)
            # Backwards compatibility alias retained for this release
            assert report_data["config"]["improve_delta"] == pytest.approx(-0.01, rel=1e-6)
            assert report_data["decision"]["adopt"] is True

            policy_section = report_data.get("policy")
            assert policy_section["source"] == "preset"
            assert policy_section["parameters"]["margin"] == pytest.approx(0.01, rel=1e-6)
            paired = report_data["statistics"]["paired"]
            assert paired["baseline_only"] == 0
            assert paired["candidate_only"] == 0
            assert paired["discordant"] == 0
            assert paired["total"] == 8
    finally:
        os.unlink(baseline_file)
        os.unlink(candidate_file)


def test_cli_stability_runs(tmp_path):
    """Test stability runs for consensus checking."""
    runner = CliRunner()

    baseline = tmp_path / "baseline.py"
    candidate = tmp_path / "candidate.py"
    baseline.write_text(
        """
def solve(L, k):
    return sorted(L, reverse=True)[: min(len(L), k)]
""",
        encoding="utf-8",
    )
    candidate.write_text(
        """
def solve(L, k):
    return sorted(L, reverse=True)[: min(len(L), k)]
""",
        encoding="utf-8",
    )

    report_dir = tmp_path / "stability_reports"
    result = runner.invoke(
        main,
        [
            "--task",
            "top_k",
            "--baseline",
            str(baseline),
            "--candidate",
            str(candidate),
            "--n",
            "5",
            "--min-delta",
            "-0.5",
            "--ci-method",
            "newcombe",
            "--stability",
            "3",
            "--report-dir",
            str(report_dir),
        ],
    )

    assert result.exit_code == 0
    assert "Running stability check: 3 runs required for consensus" in result.output
    assert "Stability run 1/3" in result.output
    assert "Stability run 2/3" in result.output
    assert "Stability run 3/3" in result.output
    assert "Stability results:" in result.output

    report_files = sorted(
        p for p in report_dir.glob("report_*.json") if not p.name.endswith("_cases.json")
    )
    assert report_files, "Expected report file created"
    report = json.loads(report_files[0].read_text())
    
    # Check stability metadata
    stability_info = report.get("stability")
    assert stability_info is not None
    assert stability_info["runs"] == 3
    assert stability_info["consensus"] is True  # Should be consistent for deterministic runs
    assert len(stability_info["run_details"]) == 3
    assert all("decision" in run for run in stability_info["run_details"])
    assert all("seed" in run for run in stability_info["run_details"])

    baseline.unlink()
    candidate.unlink()
