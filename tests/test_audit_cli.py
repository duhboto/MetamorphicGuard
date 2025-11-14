from __future__ import annotations

from click.testing import CliRunner

from metamorphic_guard.audit import write_audit_entry
from metamorphic_guard.cli.main import main as cli_main


def test_audit_tail_and_verify(tmp_path, monkeypatch) -> None:
    audit_log = tmp_path / "audit.log"
    monkeypatch.setenv("METAMORPHIC_GUARD_AUDIT_LOG", str(audit_log))
    monkeypatch.setenv("METAMORPHIC_GUARD_AUDIT_KEY", "audit-secret")

    write_audit_entry(
        {
            "task": "demo_task",
            "decision": "pass",
            "config": {"policy": "prod"},
            "hashes": {"report": "abc123"},
        }
    )

    runner = CliRunner()
    tail_result = runner.invoke(cli_main, ["audit", "tail", "--count", "1"])
    assert tail_result.exit_code == 0, tail_result.output
    assert "demo_task" in tail_result.output

    verify_result = runner.invoke(cli_main, ["audit", "verify"])
    assert verify_result.exit_code == 0, verify_result.output
    assert "verified" in verify_result.output.lower()

