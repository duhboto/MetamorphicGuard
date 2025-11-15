"""
Docker-based sandbox execution.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .utils import _result, _sanitize_config_payload
from ..sandbox_workspace import parse_success, prepare_workspace, write_bootstrap


def _force_remove_container(name: str) -> None:
    """Force remove a Docker container by name."""
    if not name:
        return
    try:
        subprocess.run(
            ["docker", "rm", "-f", name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except Exception:  # pragma: no cover - best effort cleanup
        pass


def _extract_capabilities(flags: Sequence[str]) -> Dict[str, List[str]]:
    """Extract capability add/drop flags from Docker command flags."""
    cap_add: List[str] = []
    cap_drop: List[str] = []
    i = 0
    while i < len(flags):
        flag = flags[i]
        if flag.startswith("--cap-add"):
            if flag == "--cap-add" and i + 1 < len(flags):
                cap_add.append(flags[i + 1])
                i += 2
                continue
            if "=" in flag:
                cap_add.append(flag.split("=", 1)[1])
        elif flag.startswith("--cap-drop"):
            if flag == "--cap-drop" and i + 1 < len(flags):
                cap_drop.append(flags[i + 1])
                i += 2
                continue
            if "=" in flag:
                cap_drop.append(flag.split("=", 1)[1])
        i += 1
    return {
        "add": sorted({c for c in cap_add if c}),
        "drop": sorted({c for c in cap_drop if c}),
    }


def _collect_docker_image_metadata(image: str) -> Dict[str, Any]:
    """Collect metadata about a Docker image."""
    metadata: Dict[str, Any] = {"image": image}
    try:
        completed = subprocess.run(
            ["docker", "image", "inspect", image],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            if completed.stderr.strip():
                metadata["image_inspect_error"] = completed.stderr.strip()
            elif completed.stdout.strip():
                metadata["image_inspect_error"] = completed.stdout.strip()
            return metadata
        data = json.loads(completed.stdout or "[]")
        if not data:
            return metadata
        entry = data[0]
        metadata["image_id"] = entry.get("Id")
        metadata["image_digest"] = entry.get("RepoDigests")
        metadata["image_created"] = entry.get("Created")
        metadata["image_size"] = entry.get("Size")
        metadata["image_repo_tags"] = entry.get("RepoTags")
    except Exception as exc:  # pragma: no cover - best effort
        metadata["image_inspect_error"] = str(exc)
    return metadata


def _run_docker_sandbox(
    file_path: str,
    func_name: str,
    args: tuple,
    timeout_s: float = 2.0,
    mem_mb: int = 512,
    *,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute the requested function inside a Docker container."""
    start_time = time.time()
    docker_config = config or {}

    image = (
        docker_config.get("image")
        or os.environ.get("METAMORPHIC_GUARD_DOCKER_IMAGE")
        or "python:3.11-slim"
    )
    workdir = str(docker_config.get("workdir", "/sandbox"))
    raw_flags = docker_config.get("flags", [])
    if isinstance(raw_flags, (list, tuple)):
        extra_flags = [str(flag) for flag in raw_flags]
    elif raw_flags:
        extra_flags = [str(raw_flags)]
    else:
        extra_flags = []
    network_mode = docker_config.get("network", "none")
    cpus = docker_config.get("cpus")
    pids_limit = int(docker_config.get("pids_limit", 64))
    memory_mb = int(docker_config.get("memory_mb", mem_mb))
    memory_limit_mb = max(memory_mb, mem_mb, 32)
    env_overrides = docker_config.get("env", {})

    banned_modules = os.environ.get("METAMORPHIC_GUARD_BANNED")

    sanitized_config = _sanitize_config_payload(docker_config)

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

        container_bootstrap = f"{workdir}/bootstrap.py"
        volume_spec = f"{temp_path}:{workdir}:ro"

        env_vars = {
            "NO_NETWORK": "1",
            "PYTHONNOUSERSITE": "1",
        }
        if banned_modules:
            env_vars["METAMORPHIC_GUARD_BANNED"] = banned_modules
        if isinstance(env_overrides, dict):
            for key, value in env_overrides.items():
                if value is None:
                    continue
                env_vars[str(key)] = str(value)

        container_name = f"metaguard-{uuid.uuid4().hex[:12]}"

        metadata_base: Dict[str, Any] = {
            "executor": "docker",
            "image": image,
            "workdir": workdir,
            "network": str(network_mode),
            "cpus": str(cpus) if cpus is not None else "1",
            "memory_limit_mb": memory_limit_mb,
            "pids_limit": pids_limit,
            "env_keys": sorted(env_vars.keys()),
            "capabilities": _extract_capabilities(extra_flags),
        }
        if sanitized_config:
            metadata_base["config"] = sanitized_config
            metadata_base["config_fingerprint"] = hashlib.sha256(
                json.dumps(sanitized_config, sort_keys=True).encode("utf-8")
            ).hexdigest()
        security_opts = docker_config.get("security_opt")
        if isinstance(security_opts, (list, tuple)):
            metadata_base["security_options"] = [str(opt) for opt in security_opts]
        metadata_base.update(_collect_docker_image_metadata(image))

        command = [
            "docker",
            "run",
            "--rm",
            "--name",
            container_name,
            "--network",
            str(network_mode),
            "--memory",
            f"{memory_limit_mb}m",
            "--pids-limit",
            str(pids_limit),
            "-v",
            volume_spec,
        ]

        if cpus is not None:
            command.extend(["--cpus", str(cpus)])
        else:
            command.extend(["--cpus", "1"])

        if isinstance(security_opts, (list, tuple)):
            for opt in security_opts:
                command.extend(["--security-opt", str(opt)])

        for key, value in env_vars.items():
            command.extend(["-e", f"{key}={value}"])

        command.extend(extra_flags)
        command.extend([str(image), "python", "-I", container_bootstrap])

        metadata_base["command_fingerprint"] = hashlib.sha256(
            " ".join(command).encode("utf-8")
        ).hexdigest()

        def _metadata_with_state(state: str) -> Dict[str, Any]:
            meta = dict(metadata_base)
            meta["run_state"] = state
            return meta

        try:
            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired:
            _force_remove_container(container_name)
            duration_ms = (time.time() - start_time) * 1000
            return _result(
                success=False,
                duration_ms=duration_ms,
                stdout="",
                stderr="",
                error=f"Process timed out after {timeout_s}s",
                error_type="timeout",
                error_code="SANDBOX_TIMEOUT",
                sandbox_metadata=_metadata_with_state("timeout"),
            )
        except FileNotFoundError:
            duration_ms = (time.time() - start_time) * 1000
            return _result(
                success=False,
                duration_ms=duration_ms,
                stdout="",
                stderr="",
                error="Docker executable not found",
                error_type="executor_missing",
                error_code="SANDBOX_DOCKER_NOT_FOUND",
                sandbox_metadata=_metadata_with_state("executor_missing"),
            )

        duration_ms = (time.time() - start_time) * 1000

        if completed.returncode != 0:
            return _result(
                success=False,
                duration_ms=duration_ms,
                stdout=completed.stdout,
                stderr=completed.stderr,
                error=f"Process exited with code {completed.returncode}",
                error_type="process_exit",
                error_code="SANDBOX_EXIT_CODE",
                diagnostics={"returncode": completed.returncode},
                sandbox_metadata=_metadata_with_state("process_exit"),
            )

        parsed = parse_success(completed.stdout)
        if parsed is None:
            return _result(
                success=False,
                duration_ms=duration_ms,
                stdout=completed.stdout,
                stderr=completed.stderr,
                error="No success marker found in output",
                error_type="output_parse",
                error_code="SANDBOX_PARSE_ERROR",
                sandbox_metadata=_metadata_with_state("output_parse"),
            )

        return _result(
            success=True,
            duration_ms=duration_ms,
            stdout=completed.stdout,
            stderr=completed.stderr,
            result=parsed,
            sandbox_metadata=_metadata_with_state("success"),
        )

