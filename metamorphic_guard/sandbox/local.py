"""
Local subprocess sandbox execution.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional

from .utils import _result, _sanitize_config_payload
from ..sandbox_limits import make_preexec_fn
from ..sandbox_workspace import parse_success, prepare_workspace, write_bootstrap


def _run_local_sandbox(
    file_path: str,
    func_name: str,
    args: tuple,
    timeout_s: float = 2.0,
    mem_mb: int = 512,
    *,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Execute the requested function inside an isolated subprocess.

    Returns execution metadata along with either the parsed result (on success) or
    structured error information (on failure).
    """
    config = config or {}
    metadata_base: Dict[str, Any] = {
        "executor": "local",
        "timeout_s": timeout_s,
        "mem_mb": mem_mb,
        "python_version": sys.version,
    }
    sanitized_config = _sanitize_config_payload(config)
    if sanitized_config:
        metadata_base["config"] = sanitized_config
        metadata_base["config_fingerprint"] = hashlib.sha256(
            json.dumps(sanitized_config, sort_keys=True).encode("utf-8")
        ).hexdigest()

    def _metadata_with_state(state: str) -> Dict[str, Any]:
        meta = dict(metadata_base)
        meta["run_state"] = state
        return meta

    start_time = time.time()

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        workspace_dir = temp_path / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)

        sandbox_target = prepare_workspace(Path(file_path), workspace_dir)
        bootstrap_path = write_bootstrap(
            temp_path,
            workspace_dir,
            sandbox_target,
            func_name,
            args,
        )

        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        env["PYTHONIOENCODING"] = "utf-8"
        env["NO_NETWORK"] = "1"
        env["PYTHONNOUSERSITE"] = "1"

        try:
            preexec_fn = make_preexec_fn(timeout_s, mem_mb)

            process = subprocess.Popen(
                [sys.executable, "-I", str(bootstrap_path)],
                cwd=workspace_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                preexec_fn=preexec_fn,
                start_new_session=preexec_fn is None,
            )

            try:
                stdout, stderr = process.communicate(timeout=timeout_s)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                duration_ms = (time.time() - start_time) * 1000
                return _result(
                    success=False,
                    duration_ms=duration_ms,
                    stdout="",
                    stderr=f"Process timed out after {timeout_s}s",
                    error="Timeout",
                    error_type="timeout",
                    error_code="SANDBOX_TIMEOUT",
                    sandbox_metadata=_metadata_with_state("timeout"),
                )

            duration_ms = (time.time() - start_time) * 1000

            if process.returncode != 0:
                return _result(
                    success=False,
                    duration_ms=duration_ms,
                    stdout=stdout,
                    stderr=stderr,
                    error=f"Process exited with code {process.returncode}",
                    error_type="process_exit",
                    error_code="SANDBOX_EXIT_CODE",
                    diagnostics={"returncode": process.returncode},
                    sandbox_metadata=_metadata_with_state("process_exit"),
                )

            parsed = parse_success(stdout)
            if parsed is None:
                return _result(
                    success=False,
                    duration_ms=duration_ms,
                    stdout=stdout,
                    stderr=stderr,
                    error="No success marker found in output",
                    error_type="output_parse",
                    error_code="SANDBOX_PARSE_ERROR",
                    sandbox_metadata=_metadata_with_state("output_parse"),
                )

            return _result(
                success=True,
                duration_ms=duration_ms,
                stdout=stdout,
                stderr=stderr,
                result=parsed,
                sandbox_metadata=_metadata_with_state("success"),
            )

        except Exception as exc:  # pragma: no cover - defensive safety net
            duration_ms = (time.time() - start_time) * 1000
            return _result(
                success=False,
                duration_ms=duration_ms,
                stdout="",
                stderr="",
                error=f"Execution failed: {exc}",
                error_type="internal_error",
                error_code="SANDBOX_UNHANDLED_EXCEPTION",
                sandbox_metadata=_metadata_with_state("internal_error"),
            )



