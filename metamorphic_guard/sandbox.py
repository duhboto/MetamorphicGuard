"""
Sandbox execution with resource limits and isolation.
"""

import ast
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import resource  # type: ignore
except ImportError:  # pragma: no cover - resource is POSIX-only
    resource = None  # type: ignore[assignment]


def run_in_sandbox(
    file_path: str,
    func_name: str,
    args: tuple,
    timeout_s: float = 2.0,
    mem_mb: int = 512,
) -> Dict[str, Any]:
    """
    Execute the requested function inside an isolated subprocess.

    Returns execution metadata along with either the parsed result (on success) or
    structured error information (on failure).
    """
    start_time = time.time()

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        workspace_dir = temp_path / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)

        sandbox_target = _prepare_workspace(Path(file_path), workspace_dir)
        bootstrap_path = _write_bootstrap(
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

        try:
            import subprocess  # Local import keeps sandbox namespace tighter

            process = subprocess.Popen(
                [sys.executable, "-I", str(bootstrap_path)],
                cwd=workspace_dir,
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
    workspace_dir: Path,
    sandbox_target: Path,
    func_name: str,
    args: tuple,
) -> Path:
    """Emit the bootstrap script used to execute the target safely."""
    from textwrap import dedent

    workspace_repr = repr(str(workspace_dir))
    target_repr = repr(str(sandbox_target))
    args_repr = repr(args)
    func_name_repr = repr(func_name)

    bootstrap_code = dedent(
        f"""
        import builtins
        import importlib.util
        import sys

        sys.path.insert(0, {workspace_repr})


        def _deny_socket(*_args, **_kwargs):
            raise RuntimeError("Network access denied in sandbox")


        def _deny_process(*_args, **_kwargs):
            raise RuntimeError("Process creation denied in sandbox")


        # Harden socket module.
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


        # Harden os helpers that can spawn processes.
        import os as _os_module

        _PROCESS_ATTRS = (
            "system",
            "popen",
            "popen2",
            "popen3",
            "popen4",
            "spawnl",
            "spawnle",
            "spawnlp",
            "spawnlpe",
            "spawnv",
            "spawnve",
            "spawnvp",
            "spawnvpe",
            "fork",
            "forkpty",
            "fspawn",
            "execv",
            "execve",
            "execl",
            "execle",
            "execlp",
            "execlpe",
            "execvp",
            "execvpe",
        )

        for _attr in _PROCESS_ATTRS:
            if hasattr(_os_module, _attr):
                setattr(_os_module, _attr, _deny_process)

        try:
            import subprocess as _subprocess_module  # noqa: WPS433 - confined to sandbox
        except ImportError:
            _subprocess_module = None

        if _subprocess_module is not None:
            for _attr in ("Popen", "call", "check_call", "check_output", "run"):
                if hasattr(_subprocess_module, _attr):
                    setattr(_subprocess_module, _attr, _deny_process)


        _BANNED = {{
            "socket",
            "_socket",
            "subprocess",
            "_subprocess",
            "multiprocessing",
            "importlib",
        }}
        _ORIG_IMPORT = builtins.__import__


        def _sandbox_import(name, *args, **kwargs):
            if name in _BANNED:
                raise ImportError("Network or process access denied in sandbox")
            module = _ORIG_IMPORT(name, *args, **kwargs)
            if name == "os":
                for attr in _PROCESS_ATTRS:
                    if hasattr(module, attr):
                        setattr(module, attr, _deny_process)
            elif name == "importlib":
                raise ImportError("importlib is disabled in sandbox")
            return module


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


def _prepare_workspace(source_path: Path, workspace_dir: Path) -> Path:
    """Copy the relevant source tree into the sandbox and return the module path."""
    import shutil
    import tempfile

    if source_path.is_dir():
        dest_dir = workspace_dir / source_path.name
        shutil.copytree(source_path, dest_dir, dirs_exist_ok=True)
        candidate = dest_dir / "__init__.py"
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"No __init__.py found in package directory {source_path}")

    package_root = _determine_package_root(source_path)
    if package_root is None:
        parent = source_path.parent
        if parent == Path(".") or parent == parent.parent:
            dest = workspace_dir / source_path.name
            dest.write_bytes(source_path.read_bytes())
            return dest

        try:
            tmp_root = Path(tempfile.gettempdir()).resolve()
        except FileNotFoundError:  # pragma: no cover - extremely unlikely
            tmp_root = None

        if tmp_root is not None and parent.resolve() == tmp_root:
            dest = workspace_dir / source_path.name
            dest.write_bytes(source_path.read_bytes())
            return dest

        dest_parent = workspace_dir / parent.name
        dest_parent.mkdir(parents=True, exist_ok=True)

        for entry in parent.iterdir():
            target = dest_parent / entry.name
            if entry == source_path:
                continue
            if entry.is_file():
                shutil.copy2(entry, target)
            elif entry.is_dir():
                shutil.copytree(entry, target, dirs_exist_ok=True)

        dest_file = dest_parent / source_path.name
        shutil.copy2(source_path, dest_file)
        return dest_file

    dest_root = workspace_dir / package_root.name
    shutil.copytree(package_root, dest_root, dirs_exist_ok=True)
    return dest_root / source_path.relative_to(package_root)


def _determine_package_root(source_path: Path) -> Optional[Path]:
    """Return the highest package directory containing the source file, if any."""
    current = source_path.parent
    package_root: Optional[Path] = None

    while current != current.parent and (current / "__init__.py").exists():
        package_root = current
        current = current.parent
        if not (current / "__init__.py").exists():
            break

    if package_root is None and (source_path.parent / "__init__.py").exists():
        package_root = source_path.parent

    return package_root


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
    if resource is None:
        return

    try:
        cpu_limit = max(1, int(timeout_s * 2))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit))

        mem_limit = max(mem_mb, 32) * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem_limit, mem_limit))

        resource.setrlimit(resource.RLIMIT_NPROC, (32, 32))
        resource.setrlimit(resource.RLIMIT_NOFILE, (16, 16))
    except (OSError, ValueError):
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
