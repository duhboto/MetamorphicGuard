"""
Sandbox execution with resource limits and isolation.
"""

import ast
import hashlib
import importlib
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

try:
    import resource  # type: ignore
except ImportError:  # pragma: no cover - resource is POSIX-only
    resource = None  # type: ignore[assignment]


_CACHE_ROOT = Path(tempfile.gettempdir()) / "metamorphic_guard_cache"
_CACHE_ROOT.mkdir(parents=True, exist_ok=True)
_SNAPSHOT_CACHE: Dict[str, tuple[Path, bool]] = {}
_SNAPSHOT_LOCK = threading.Lock()

from .redaction import get_redactor
from .plugins import executor_plugins

def run_in_sandbox(
    file_path: str,
    func_name: str,
    args: tuple,
    timeout_s: float = 2.0,
    mem_mb: int = 512,
    *,
    executor: Optional[str] = None,
    executor_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Execute the requested function inside an isolated sandbox.

    An alternative executor can be selected via the `executor` argument, the
    `METAMORPHIC_GUARD_EXECUTOR` environment variable, or by registering a custom
    callable. Built-in options include:

    * `local`  (default): fork/exec on the host with resource limits.
    * `docker`: launch inside a Docker container with network disabled.
    * `<module>:<callable>`: import and invoke an external plugin.
    """

    backend = _resolve_executor_name(executor)
    config = executor_config if executor_config is not None else _load_executor_config()

    if backend == "local":
        raw_result = _run_local_sandbox(
            file_path,
            func_name,
            args,
            timeout_s,
            mem_mb,
            config=config,
        )
        return _finalize_result(raw_result, config)
    if backend == "docker":
        raw_result = _run_docker_sandbox(
            file_path,
            func_name,
            args,
            timeout_s,
            mem_mb,
            config=config,
        )
        return _finalize_result(raw_result, config)

    # Check plugin registry for executor plugins
    plugin_registry = executor_plugins()
    plugin_def = plugin_registry.get(backend.lower())
    if plugin_def is not None:
        executor_instance = plugin_def.factory(config=config)
        if hasattr(executor_instance, "execute"):
            raw_result = executor_instance.execute(
                file_path, func_name, args, timeout_s, mem_mb
            )
            return _finalize_result(raw_result, config)
        raise TypeError(f"Executor plugin '{backend}' must have an 'execute' method.")

    # Fall back to module:callable syntax
    executor_callable = _load_executor_callable(backend)
    call_kwargs: Dict[str, Any] = {}
    if config is not None:
        call_kwargs["config"] = config

    raw_result = executor_callable(file_path, func_name, args, timeout_s, mem_mb, **call_kwargs)
    return _finalize_result(raw_result, config)


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
        env["PYTHONNOUSERSITE"] = "1"

        try:
            import subprocess  # Local import keeps sandbox namespace tighter

            preexec_fn = _make_preexec_fn(timeout_s, mem_mb)

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

            parsed = _parse_success(stdout)
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


def _run_docker_sandbox(
    file_path: str,
    func_name: str,
    args: tuple,
    timeout_s: float = 2.0,
    mem_mb: int = 512,
    *,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
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

        sandbox_target = _prepare_workspace(Path(file_path), workspace_dir)
        bootstrap_path = _write_bootstrap(
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

        import subprocess

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

        parsed = _parse_success(completed.stdout)
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


def _resolve_executor_name(explicit: Optional[str]) -> str:
    if explicit and explicit.strip():
        return explicit.strip()
    env_value = os.environ.get("METAMORPHIC_GUARD_EXECUTOR")
    if env_value and env_value.strip():
        return env_value.strip()
    return "local"


def _load_executor_config() -> Optional[Dict[str, Any]]:
    raw = os.environ.get("METAMORPHIC_GUARD_EXECUTOR_CONFIG")
    if not raw:
        return None
    try:
        config = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return config if isinstance(config, dict) else None


def _load_executor_callable(path: str) -> Callable[..., Dict[str, Any]]:
    if not path:
        raise ValueError("Executor path cannot be empty.")

    module_name: Optional[str]
    attr_name: str
    if ":" in path:
        module_name, attr_name = path.split(":", 1)
    else:
        module_name, _, attr_name = path.rpartition(".")
        if not module_name:
            raise ValueError(
                f"Executor '{path}' must be in 'module:callable' or dotted form."
            )

    module = importlib.import_module(module_name)
    target = getattr(module, attr_name)

    if isinstance(target, type):
        target = target()

    if hasattr(target, "run") and callable(target.run):
        return target.run  # type: ignore[return-value]

    if callable(target):
        return target  # type: ignore[return-value]

    raise TypeError(f"Executor '{path}' is not callable.")


def _force_remove_container(name: str) -> None:
    if not name:
        return
    import subprocess

    try:
        subprocess.run(
            ["docker", "rm", "-f", name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except FileNotFoundError:
        # Docker not installed; nothing to clean up.
        return


def _snapshot_source(source: Path) -> tuple[Path, bool]:
    """Return a cached snapshot path and whether it represents a directory."""
    resolved = source.resolve()
    try:
        mtime = resolved.stat().st_mtime_ns
    except FileNotFoundError as exc:  # pragma: no cover - source removed mid-run
        raise FileNotFoundError(f"Source path not found: {resolved}") from exc

    key_material = f"{resolved}:{mtime}".encode("utf-8")
    digest = hashlib.sha256(key_material).hexdigest()

    with _SNAPSHOT_LOCK:
        cached = _SNAPSHOT_CACHE.get(digest)
        if cached and cached[0].exists():
            return cached

        snapshot_base = _CACHE_ROOT / digest
        if snapshot_base.exists():
            shutil.rmtree(snapshot_base)
        snapshot_base.mkdir(parents=True, exist_ok=True)

        if resolved.is_dir():
            target = snapshot_base / resolved.name
            shutil.copytree(resolved, target, dirs_exist_ok=True)
            result = (target, True)
        else:
            target = snapshot_base / resolved.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(resolved, target)
            result = (target, False)

        _SNAPSHOT_CACHE[digest] = result
        return result


def _clone_snapshot_dir(snapshot: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(snapshot, destination, copy_function=_link_or_copy)


def _clone_snapshot_file(snapshot: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()
    _link_or_copy(snapshot, destination)


def _link_or_copy(src: str | Path, dst: str | Path) -> None:
    src_path = os.fspath(src)
    dst_path = os.fspath(dst)
    try:
        os.link(src_path, dst_path)
    except OSError:
        shutil.copy2(src_path, dst_path)


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


        _DEFAULT_BANNED = {{
            "socket",
            "_socket",
            "subprocess",
            "_subprocess",
            "multiprocessing",
            "multiprocessing.util",
            "multiprocessing.spawn",
            "multiprocessing.popen_spawn_posix",
            "ctypes",
            "_ctypes",
            "cffi",
        }}
        _EXTRA_BANNED_RAW = _os_module.environ.get("METAMORPHIC_GUARD_BANNED", "")
        _EXTRA_BANNED = {{
            item.strip()
            for item in _EXTRA_BANNED_RAW.split(",")
            if item.strip()
        }}
        _BANNED = _DEFAULT_BANNED.union(_EXTRA_BANNED)
        _ORIG_IMPORT = builtins.__import__


        def _is_banned(module_name: str) -> bool:
            return any(
                module_name == banned or module_name.startswith(f"{{banned}}.")
                for banned in _BANNED
            )


        def _sandbox_import(name, *args, **kwargs):
            if _is_banned(name):
                raise ImportError("Network or process access denied in sandbox")
            module = _ORIG_IMPORT(name, *args, **kwargs)
            if name == "os":
                for attr in _PROCESS_ATTRS:
                    if hasattr(module, attr):
                        setattr(module, attr, _deny_process)
            elif name.startswith("multiprocessing"):
                raise ImportError("multiprocessing is disabled in sandbox")
            elif name in {"ctypes", "_ctypes", "cffi"}:
                raise ImportError("native FFI access denied in sandbox")
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

    if source_path.is_dir():
        snapshot, is_dir = _snapshot_source(source_path)
        if not is_dir:
            raise FileNotFoundError(f"Expected directory for {source_path}")
        dest_dir = workspace_dir / source_path.name
        _clone_snapshot_dir(snapshot, dest_dir)
        candidate = dest_dir / "__init__.py"
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"No __init__.py found in package directory {source_path}")

    package_root = _determine_package_root(source_path)
    if package_root is None:
        parent = source_path.parent
        if parent == Path(".") or parent == parent.parent:
            snapshot, is_dir = _snapshot_source(source_path)
            if is_dir:
                raise FileNotFoundError(f"Unexpected package directory at {source_path}")
            dest = workspace_dir / source_path.name
            _clone_snapshot_file(snapshot, dest)
            return dest

        try:
            tmp_root = Path(tempfile.gettempdir()).resolve()
        except FileNotFoundError:  # pragma: no cover - extremely unlikely
            tmp_root = None

        if tmp_root is not None and parent.resolve() == tmp_root:
            snapshot, is_dir = _snapshot_source(source_path)
            if is_dir:
                raise FileNotFoundError(f"Unexpected package directory at {source_path}")
            dest = workspace_dir / source_path.name
            _clone_snapshot_file(snapshot, dest)
            return dest

        dest_parent = workspace_dir / parent.name
        snapshot_parent, is_dir = _snapshot_source(parent)
        if not is_dir:
            raise FileNotFoundError(f"Expected directory for {parent}")
        _clone_snapshot_dir(snapshot_parent, dest_parent)
        return dest_parent / source_path.name

    dest_root = workspace_dir / package_root.name
    snapshot_root, is_dir = _snapshot_source(package_root)
    if not is_dir:
        raise FileNotFoundError(f"Expected package directory for {package_root}")
    _clone_snapshot_dir(snapshot_root, dest_root)
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


def _make_preexec_fn(timeout_s: float, mem_mb: int):
    """
    Build a POSIX-only pre-exec function for applying resource limits.

    Windows does not allow preexec_fn, so we return None in that case and
    rely on communicate() timeouts plus process groups for cleanup.
    """
    if resource is None or os.name == "nt":
        return None

    def _apply_limits() -> None:
        _set_resource_limits(timeout_s, mem_mb)

    return _apply_limits


def _result(
    *,
    success: bool,
    duration_ms: float,
    stdout: str,
    stderr: str,
    error: Optional[str] = None,
    result: Optional[Any] = None,
    error_type: Optional[str] = None,
    error_code: Optional[str] = None,
    diagnostics: Optional[Dict[str, Any]] = None,
    sandbox_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Helper for constructing run_in_sandbox response payloads."""
    payload: Dict[str, Any] = {
        "success": success,
        "result": result,
        "stdout": stdout,
        "stderr": stderr,
        "duration_ms": duration_ms,
        "error": error,
    }
    if error_type:
        payload["error_type"] = error_type
    if error_code:
        payload["error_code"] = error_code
    if diagnostics:
        payload["diagnostics"] = diagnostics
    if sandbox_metadata is not None:
        payload["sandbox_metadata"] = sandbox_metadata
    return payload


def _sanitize_config_payload(payload: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if payload is None:
        return None
    try:
        return json.loads(json.dumps(payload, default=str))
    except Exception:
        sanitized: Dict[str, Any] = {}
        for key, value in payload.items():
            sanitized[str(key)] = str(value)
        return sanitized


def _extract_capabilities(flags: Sequence[str]) -> Dict[str, List[str]]:
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
    metadata: Dict[str, Any] = {"image": image}
    try:
        import subprocess

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


def _finalize_result(result: Any, config: Optional[Dict[str, Any]]) -> Any:
    if not isinstance(result, dict):
        return result
    redactor = get_redactor(config if isinstance(config, dict) else None)
    return redactor.redact(result)
