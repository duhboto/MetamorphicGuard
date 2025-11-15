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
    enable_cache: bool = True,
) -> Dict[str, Any]:
    """
    Execute the requested function inside an isolated sandbox.

    An alternative executor can be selected via the `executor` argument, the
    `METAMORPHIC_GUARD_EXECUTOR` environment variable, or by registering a custom
    callable. Built-in options include:

    * `local`  (default): fork/exec on the host with resource limits.
    * `docker`: launch inside a Docker container with network disabled.
    * `<module>:<callable>`: import and invoke an external plugin.
    
    Args:
        file_path: Path to implementation file
        func_name: Function name to call
        args: Input arguments
        timeout_s: Timeout in seconds
        mem_mb: Memory limit in MB
        executor: Executor backend name
        executor_config: Executor configuration
        enable_cache: Whether to use result caching (default: True)
    """

    # Check cache if enabled (only for non-LLM executors to avoid caching API calls)
    if enable_cache:
        backend, _ = _resolve_executor(executor, executor_config)
        # Don't cache LLM executor results (they may vary, and caching API calls is not useful)
        if backend not in ("openai", "anthropic", "vllm"):
            try:
                from ..result_cache import get_result_cache
                cache = get_result_cache()
                cached = cache.get(file_path, func_name, args)
                if cached is not None:
                    return cached
            except Exception:
                # If caching fails, continue with normal execution
                pass

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
    result = _finalize_result(raw_result, config)
    
    # Cache result if enabled and not an LLM executor
    if enable_cache and backend not in ("openai", "anthropic", "vllm"):
        try:
            from ..result_cache import get_result_cache
            cache = get_result_cache()
            # Only cache successful results to avoid caching errors
            if result.get("success", False):
                cache.set(file_path, func_name, args, result)
        except Exception:
            # If caching fails, continue normally
            pass
    
    return result



