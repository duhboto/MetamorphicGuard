"""
Sandbox execution with resource limits and isolation.
"""

import ast
import os
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional


def run_in_sandbox(
    file_path: str,
    func_name: str,
    args: tuple,
    timeout_s: float = 2.0,
    mem_mb: int = 512,
) -> Dict[str, Any]:
    """
    Execute the requested function inside an isolated subprocess.

    Returns a dictionary containing execution metadata and either the parsed result
    (when successful) or contextual error information (when the sandboxed run fails).
    """
    start_time = time.time()

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Copy the target file into the sandbox directory
        import shutil  # Local import to avoid making the module importable by candidates

        target_file = Path(file_path)
        sandbox_target = temp_path / target_file.name
        shutil.copy2(target_file, sandbox_target)

        bootstrap_file = _write_bootstrap(temp_path, sandbox_target, func_name, args)

        # Prepare a clean environment for the subprocess
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        env["PYTHONIOENCODING"] = "utf-8"
        env["NO_NETWORK"] = "1"

        try:
            process = subprocess.Popen(
                [sys.executable, "-I", str(bootstrap_file)],
                cwd=temp_path,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                preexec_fn=lambda: _set_resource_limits(timeout_s, mem_mb),
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
                )

            duration_ms = (time.time() - start_time) * 1000

            if process.returncode != 0:
                return _result(
                    success=False,
                    duration_ms=duration_ms,
                    stdout=stdout,
                    stderr=stderr,
                    error=f"Process exited with code {process.returncode}",
                )

            parsed = _parse_success(stdout)
            if parsed is None:
                return _result(
                    success=False,
                    duration_ms=duration_ms,
                    stdout=stdout,
                    stderr=stderr,
                    error="No success marker found in output",
                )

            return _result(
                success=True,
                duration_ms=duration_ms,
                stdout=stdout,
                stderr=stderr,
                result=parsed,
            )

        except Exception as exc:  # pragma: no cover - defensive safety net
            duration_ms = (time.time() - start_time) * 1000
            return _result(
                success=False,
                duration_ms=duration_ms,
                stdout="",
                stderr="",
                error=f"Execution failed: {exc}",
            )


def _write_bootstrap(
    temp_path: Path,
    sandbox_target: Path,
    func_name: str,
    args: tuple,
) -> Path:
    """Create the bootstrap script that imports and executes the target safely."""
    from textwrap import dedent

    target_repr = repr(str(sandbox_target))
    args_repr = repr(args)
    func_name_repr = repr(func_name)

    bootstrap_code = dedent(
        f"""
        import builtins
        import importlib.util
        import sys


        def _deny_socket(*_args, **_kwargs):
            raise RuntimeError("Network access denied in sandbox")


        # Pre-import socket modules (if available) so we can stub network primitives.
        try:
            import socket as _socket_module  # noqa: WPS433 - confined to sandbox
        except ImportError:
            _socket_module = None

        try:
            import _socket as _c_socket_module  # noqa: WPS433 - confined to sandbox
        except ImportError:
            _c_socket_module = None

        if _socket_module is not None:
            for _attr in (
                "socket",
                "create_connection",
                "create_server",
                "socketpair",
                "fromfd",
                "fromshare",
                "getaddrinfo",
                "gethostbyname",
                "gethostbyaddr",
            ):
                if hasattr(_socket_module, _attr):
                    setattr(_socket_module, _attr, _deny_socket)

        if _c_socket_module is not None:
            for _attr in ("socket", "fromfd", "fromshare", "socketpair"):
                if hasattr(_c_socket_module, _attr):
                    setattr(_c_socket_module, _attr, _deny_socket)


        _BANNED = {{"socket", "_socket"}}
        _ORIG_IMPORT = builtins.__import__


        def _sandbox_import(name, *args, **kwargs):
            if name in _BANNED:
                raise ImportError("Network access denied in sandbox")
            return _ORIG_IMPORT(name, *args, **kwargs)


        builtins.__import__ = _sandbox_import


        def _load():
            spec = importlib.util.spec_from_file_location("target_module", {target_repr})
            if spec is None or spec.loader is None:
                raise ImportError("Unable to load target module")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module


        def _main():
            module = _load()
            try:
                func = getattr(module, {func_name_repr})
            except AttributeError as exc:
                raise AttributeError(f"Function '{{{func_name_repr}}}' not found") from exc
            result = func(*{args_repr})
            print("SUCCESS:", repr(result))


        if __name__ == "__main__":
            try:
                _main()
            except Exception as exc:  # noqa: BLE001 - report exact failure upstream
                print("ERROR:", exc)
                sys.exit(1)
        """
    )

    bootstrap_file = temp_path / "bootstrap.py"
    bootstrap_file.write_text(bootstrap_code)
    return bootstrap_file


def _parse_success(stdout: str) -> Optional[Any]:
    """Extract the literal value from the sandbox stdout, if present."""
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if not lines or not lines[-1].startswith("SUCCESS:"):
        return None

    payload = lines[-1].split("SUCCESS:", 1)[1].strip()
    try:
        return ast.literal_eval(payload)
    except (SyntaxError, ValueError) as exc:
        raise ValueError(f"Failed to parse sandbox output: {exc}") from exc


def _set_resource_limits(timeout_s: float, mem_mb: int) -> None:
    """Apply CPU, memory, and file descriptor limits to the sandbox process."""
    try:
        cpu_limit = max(1, int(timeout_s * 2))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit))

        mem_limit = max(mem_mb, 32) * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem_limit, mem_limit))

        resource.setrlimit(resource.RLIMIT_NPROC, (32, 32))
        resource.setrlimit(resource.RLIMIT_NOFILE, (16, 16))
    except (OSError, ValueError):
        # On platforms where rlimits are unsupported we fail open but continue executing.
        pass


def _result(
    *,
    success: bool,
    duration_ms: float,
    stdout: str,
    stderr: str,
    error: Optional[str] = None,
    result: Optional[Any] = None,
) -> Dict[str, Any]:
    """Helper for constructing run_in_sandbox response payloads."""
    return {
        "success": success,
        "result": result,
        "stdout": stdout,
        "stderr": stderr,
        "duration_ms": duration_ms,
        "error": error,
    }

