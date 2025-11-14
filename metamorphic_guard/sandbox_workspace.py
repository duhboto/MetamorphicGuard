"""
Workspace and bootstrap helpers for sandbox execution.
"""

from __future__ import annotations

import ast
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

from .sandbox_cache import clone_snapshot_dir, clone_snapshot_file, snapshot_source


def write_bootstrap(
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


        try:
            import socket as _socket_module
        except ImportError:
            _socket_module = None

        try:
            import _socket as _c_socket_module
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
            import subprocess as _subprocess_module
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
            elif name in {{"ctypes", "_ctypes", "cffi"}}:
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
            except Exception as exc:
                print("ERROR:", exc)
                sys.exit(1)
        """
    )

    bootstrap_file = temp_path / "bootstrap.py"
    bootstrap_file.write_text(bootstrap_code)
    return bootstrap_file


def prepare_workspace(source_path: Path, workspace_dir: Path) -> Path:
    """Copy the relevant source tree into the sandbox and return the module path."""

    if source_path.is_dir():
        snapshot, is_dir = snapshot_source(source_path)
        if not is_dir:
            raise FileNotFoundError(f"Expected directory for {source_path}")
        dest_dir = workspace_dir / source_path.name
        clone_snapshot_dir(snapshot, dest_dir)
        candidate = dest_dir / "__init__.py"
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"No __init__.py found in package directory {source_path}")

    package_root = determine_package_root(source_path)
    if package_root is None:
        parent = source_path.parent
        if parent == Path(".") or parent == parent.parent:
            snapshot, is_dir = snapshot_source(source_path)
            if is_dir:
                raise FileNotFoundError(f"Unexpected package directory at {source_path}")
            dest = workspace_dir / source_path.name
            clone_snapshot_file(snapshot, dest)
            return dest

        try:
            tmp_root = Path(tempfile.gettempdir()).resolve()
        except FileNotFoundError:  # pragma: no cover - extremely unlikely
            tmp_root = None

        if tmp_root is not None and parent.resolve() == tmp_root:
            snapshot, is_dir = snapshot_source(source_path)
            if is_dir:
                raise FileNotFoundError(f"Unexpected package directory at {source_path}")
            dest = workspace_dir / source_path.name
            clone_snapshot_file(snapshot, dest)
            return dest

        dest_parent = workspace_dir / parent.name
        snapshot_parent, is_dir = snapshot_source(parent)
        if not is_dir:
            raise FileNotFoundError(f"Expected directory for {parent}")
        clone_snapshot_dir(snapshot_parent, dest_parent)
        return dest_parent / source_path.name

    dest_root = workspace_dir / package_root.name
    snapshot_root, is_dir = snapshot_source(package_root)
    if not is_dir:
        raise FileNotFoundError(f"Expected package directory for {package_root}")
    clone_snapshot_dir(snapshot_root, dest_root)
    return dest_root / source_path.relative_to(package_root)


def determine_package_root(source_path: Path) -> Optional[Path]:
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


def parse_success(stdout: str) -> Optional[Any]:
    """Extract the literal value from the sandbox stdout, if present."""
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if not lines or not lines[-1].startswith("SUCCESS:"):
        return None

    payload = lines[-1].split("SUCCESS:", 1)[1].strip()
    try:
        return ast.literal_eval(payload)
    except (SyntaxError, ValueError) as exc:
        raise ValueError(f"Failed to parse sandbox output: {exc}") from exc


__all__ = [
    "write_bootstrap",
    "prepare_workspace",
    "determine_package_root",
    "parse_success",
]

