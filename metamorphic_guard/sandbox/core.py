"""
Core sandbox execution entry point.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .docker import _run_docker_sandbox
from .local import _run_local_sandbox
from .plugins import _get_executor_plugin, _load_executor_callable, _resolve_executor
from .utils import _finalize_result


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

    backend, config = _resolve_executor(executor, executor_config)

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
    plugin_def = _get_executor_plugin(backend)
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



