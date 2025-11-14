from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from metamorphic_guard.cli.main import main as cli_main


def test_policy_sign_and_verify(tmp_path, monkeypatch) -> None:
    policy_path = tmp_path / "policy.toml"
    policy_path.write_text("[gating]\nmin_delta = 0.05\n", encoding="utf-8")
    signature_path = tmp_path / "policy.sig"
    monkeypatch.setenv("METAMORPHIC_GUARD_AUDIT_KEY", "secret-key")

    runner = CliRunner()
    result = runner.invoke(
        cli_main,
        [
            "policy",
            "sign",
            str(policy_path),
            "--signature-path",
            str(signature_path),
        ],
    )
    assert result.exit_code == 0, result.output

    record = json.loads(signature_path.read_text(encoding="utf-8"))
    assert "sha256" in record and "hmac_sha256" in record

    verify_result = runner.invoke(
        cli_main,
        [
            "policy",
            "verify",
            str(policy_path),
            "--signature-path",
            str(signature_path),
        ],
    )
    assert verify_result.exit_code == 0, verify_result.output
    assert "verified" in verify_result.output.lower()

