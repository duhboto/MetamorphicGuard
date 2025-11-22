import pytest
import time
import sys

def test_sandbox_timeout_kill_path(tmp_path):
    """Test that sandbox kills processes exceeding timeout."""
    # Create a script that sleeps longer than the timeout
    script_path = tmp_path / "long_sleep.py"
    script_path.write_text("""
import time
def run(args):
    time.sleep(2.0)
    return {"result": "done"}
""")
    
    from metamorphic_guard.sandbox.local import _run_local_sandbox
    
    # Run with short timeout
    start = time.time()
    result = _run_local_sandbox(
        str(script_path),
        "run",
        (),
        timeout_s=0.5,
        mem_mb=128
    )
    duration = time.time() - start
    
    assert not result["success"]
    
    if result["error_code"] == "SANDBOX_EXIT_CODE":
        # Likely killed by CPU limit or signal
        assert result["diagnostics"]["returncode"] != 0
    else:
        assert result["error_code"] == "SANDBOX_TIMEOUT"
        assert "Timeout" in result["stderr"]
    
    assert duration < 1.5

def test_sandbox_memory_limit_kill_path(tmp_path):
    """Test that sandbox kills processes exceeding memory limit."""
    if sys.platform == "win32":
        pytest.skip("Memory limits not supported on Windows")
        
    # Create a script that consumes memory rapidly
    script_path = tmp_path / "mem_hog.py"
    script_path.write_text("""
def run(args):
    # Try to allocate 100MB
    data = []
    while True:
        data.append(' ' * 1024 * 1024) # 1MB chunks
    return {"result": "done"}
""")
    
    from metamorphic_guard.sandbox.local import _run_local_sandbox
    
    # Run with strict memory limit (e.g., 50MB)
    result = _run_local_sandbox(
        str(script_path),
        "run",
        (),
        timeout_s=2.0,
        mem_mb=50
    )
    
    assert not result["success"]
    assert result["error_code"] == "SANDBOX_EXIT_CODE"
    assert result["diagnostics"]["returncode"] != 0


