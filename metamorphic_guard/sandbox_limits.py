"""
Resource limit helpers for sandbox execution.
"""

from __future__ import annotations

import os
from typing import Callable, Optional

try:
    import resource  # type: ignore
except ImportError:  # pragma: no cover - resource is POSIX-only
    resource = None  # type: ignore[assignment]


def set_resource_limits(timeout_s: float, mem_mb: int) -> None:
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


def make_preexec_fn(timeout_s: float, mem_mb: int) -> Optional[Callable[[], None]]:
    """
    Build a POSIX-only pre-exec function for applying resource limits.

    Windows does not allow preexec_fn, so we return None in that case and
    rely on communicate() timeouts plus process groups for cleanup.
    """
    if resource is None or os.name == "nt":
        return None

    def _apply_limits() -> None:
        set_resource_limits(timeout_s, mem_mb)

    return _apply_limits


__all__ = ["set_resource_limits", "make_preexec_fn"]

