"""
Tests for sandbox execution with resource limits and isolation.
"""

import os
import tempfile
from typing import Any, Dict, Optional

from metamorphic_guard.sandbox import run_in_sandbox


def fake_executor(
    _file_path: str,
    _func_name: str,
    _args: tuple,
    _timeout_s: float,
    _mem_mb: int,
    *,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "success": True,
        "result": config.get("value") if config else "fake",
        "stdout": "",
        "stderr": "",
        "duration_ms": 0.0,
        "error": None,
    }


def test_sandbox_success():
    """Test successful execution in sandbox."""
    # Create a simple test file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('''
def solve(x, y):
    return x + y
''')
        test_file = f.name
    
    try:
        result = run_in_sandbox(test_file, "solve", (5, 3), timeout_s=1.0, mem_mb=100)
        
        assert result["success"] is True
        assert result["result"] == 8
        assert result["error"] is None
        assert result["duration_ms"] > 0
    finally:
        os.unlink(test_file)


def test_sandbox_timeout():
    """Test sandbox timeout enforcement."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('''
import time
def solve(x):
    time.sleep(2)  # Sleep longer than timeout (but not too long)
    return x
''')
        test_file = f.name
    
    try:
        result = run_in_sandbox(test_file, "solve", (42,), timeout_s=0.1, mem_mb=100)
        
        assert result["success"] is False
        assert result.get("error_type") == "timeout"
        assert result.get("error_code") == "SANDBOX_TIMEOUT"
        # Check for timeout indicators in error or stderr
        error_msg = (result["error"] or "").lower()
        stderr_msg = (result["stderr"] or "").lower()
        # Accept various timeout indicators or process termination
        assert ("timeout" in error_msg or "timeout" in stderr_msg or 
                "timed out" in error_msg or "timed out" in stderr_msg or
                "exited with code" in error_msg or "exited with code" in stderr_msg)
    finally:
        os.unlink(test_file)


def test_sandbox_network_denial():
    """Test that sandbox prevents network access."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('''
import socket
def solve(x):
    try:
        s = socket.socket()
        return "network_allowed"
    except Exception as e:
        return f"network_denied: {e}"
''')
        test_file = f.name
    
    try:
        result = run_in_sandbox(test_file, "solve", (42,), timeout_s=1.0, mem_mb=100)

        assert result["success"] is False
        combined_output = (result["stdout"] or "") + (result["stderr"] or "")
        lowered = combined_output.lower()
        assert "network access denied" in lowered or "network or process access denied" in lowered
    finally:
        os.unlink(test_file)


def test_sandbox_import_error():
    """Test sandbox handles import errors gracefully."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('''
def solve(x):
    import nonexistent_module
    return x
''')
        test_file = f.name
    
    try:
        result = run_in_sandbox(test_file, "solve", (42,), timeout_s=1.0, mem_mb=100)
        
        assert result["success"] is False
        assert result["error"] is not None
    finally:
        os.unlink(test_file)


def test_sandbox_function_not_found():
    """Test sandbox handles missing function gracefully."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('''
def other_function(x):
    return x
''')
        test_file = f.name
    
    try:
        result = run_in_sandbox(test_file, "solve", (42,), timeout_s=1.0, mem_mb=100)
        
        assert result["success"] is False
        assert result["error"] is not None
    finally:
        os.unlink(test_file)


def test_sandbox_blocks_ctypes():
    """Sandbox should prohibit ctypes usage."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('''
def solve(x):
    import ctypes
    return ctypes.c_int(42).value
''')
        test_file = f.name

    try:
        result = run_in_sandbox(test_file, "solve", (0,), timeout_s=1.0, mem_mb=100)
        assert result["success"] is False
        combined = (result["stderr"] or "") + (result["stdout"] or "")
        assert "access denied" in combined.lower()
    finally:
        os.unlink(test_file)


def test_sandbox_blocks_fork():
    """Sandbox should block attempts to fork new processes."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('''
import os

def solve(x):
    os.fork()
    return x
''')
        test_file = f.name

    try:
        result = run_in_sandbox(test_file, "solve", (1,), timeout_s=1.0, mem_mb=100)
        assert result["success"] is False
        combined = (result["stderr"] or "") + (result["stdout"] or "")
        assert "denied" in combined.lower() or "fork" in combined.lower()
    finally:
        os.unlink(test_file)


def test_sandbox_handles_recursion_exhaustion():
    """Sandbox should surface recursion errors cleanly."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('''
import sys

def solve(x):
    def recurse(n):
        return n + recurse(n + 1)
    return recurse(0)
''')
        test_file = f.name

    try:
        result = run_in_sandbox(test_file, "solve", (1,), timeout_s=1.0, mem_mb=50)
        assert result["success"] is False
        combined = (result["stderr"] or "") + (result["stdout"] or "")
        assert "recursion" in combined.lower()
    finally:
        os.unlink(test_file)


def test_sandbox_custom_executor(monkeypatch):
    """Custom executor path should be used when environment variable is set."""
    monkeypatch.setenv("METAMORPHIC_GUARD_EXECUTOR", "tests.test_sandbox:fake_executor")
    monkeypatch.setenv("METAMORPHIC_GUARD_EXECUTOR_CONFIG", '{"value": "custom-result"}')

    try:
        result = run_in_sandbox("ignored.py", "solve", tuple(), timeout_s=0.1, mem_mb=32)
        assert result["success"] is True
        assert result["result"] == "custom-result"
    finally:
        monkeypatch.delenv("METAMORPHIC_GUARD_EXECUTOR", raising=False)
        monkeypatch.delenv("METAMORPHIC_GUARD_EXECUTOR_CONFIG", raising=False)


def test_sandbox_secret_redaction(monkeypatch):
    monkeypatch.setenv("METAMORPHIC_GUARD_REDACT", r"(?i)password\s*=\s*\w+")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(
            """
def solve():
    return "password=abc123"
"""
        )
        test_file = f.name

    try:
        result = run_in_sandbox(test_file, "solve", tuple(), timeout_s=1.0, mem_mb=64)
        assert result["success"] is True
        assert result["result"] == "[REDACTED]"
        assert "password" not in (result["stdout"] or "")
    finally:
        os.unlink(test_file)
        monkeypatch.delenv("METAMORPHIC_GUARD_REDACT", raising=False)
