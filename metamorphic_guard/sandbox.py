"""
Sandbox execution with resource limits and isolation.
"""

import os
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Tuple


def run_in_sandbox(
    file_path: str, 
    func_name: str, 
    args: tuple, 
    timeout_s: float = 2.0, 
    mem_mb: int = 512
) -> Dict[str, Any]:
    """
    Execute function in isolated sandbox with resource limits.
    
    Returns:
        Dict with keys: success, result, stdout, stderr, duration_ms, error
    """
    start_time = time.time()
    
    # Create temporary working directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Copy target file to sandbox directory
        import shutil
        target_file = Path(file_path)
        sandbox_target = temp_path / target_file.name
        shutil.copy2(target_file, sandbox_target)
        
        # Create bootstrap script that patches socket module and imports the target
        bootstrap_code = f'''
import sys
import os
import socket
import importlib.util

# Deny network access by monkeypatching socket
def deny_socket(*args, **kwargs):
    raise RuntimeError("Network access denied in sandbox")

socket.socket = deny_socket
socket.create_connection = deny_socket
socket.connect = deny_socket

# Import and execute the target function
try:
    # Load module from file path
    spec = importlib.util.spec_from_file_location("target_module", "{sandbox_target}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    func = getattr(module, "{func_name}")
    result = func(*{args})
    print("SUCCESS:", repr(result))
except Exception as e:
    print("ERROR:", str(e))
    sys.exit(1)
'''
        
        bootstrap_file = temp_path / "bootstrap.py"
        bootstrap_file.write_text(bootstrap_code)
        
        # Set up environment
        env = os.environ.copy()
        env.pop('PYTHONPATH', None)  # Remove PYTHONPATH
        env['PYTHONIOENCODING'] = 'utf-8'
        
        try:
            # Execute with resource limits
            process = subprocess.Popen(
                [sys.executable, '-I', str(bootstrap_file)],
                cwd=temp_path,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                preexec_fn=lambda: _set_resource_limits(timeout_s, mem_mb)
            )
            
            try:
                stdout, stderr = process.communicate(timeout=timeout_s)
                duration_ms = (time.time() - start_time) * 1000
                
                if process.returncode == 0:
                    # Parse result from stdout
                    lines = stdout.strip().split('\n')
                    if lines and lines[-1].startswith('SUCCESS:'):
                        result_str = lines[-1][8:]  # Remove 'SUCCESS: ' prefix
                        try:
                            result = eval(result_str)
                            return {
                                "success": True,
                                "result": result,
                                "stdout": stdout,
                                "stderr": stderr,
                                "duration_ms": duration_ms,
                                "error": None
                            }
                        except Exception as e:
                            return {
                                "success": False,
                                "result": None,
                                "stdout": stdout,
                                "stderr": stderr,
                                "duration_ms": duration_ms,
                                "error": f"Failed to parse result: {e}"
                            }
                    else:
                        return {
                            "success": False,
                            "result": None,
                            "stdout": stdout,
                            "stderr": stderr,
                            "duration_ms": duration_ms,
                            "error": "No success marker found in output"
                        }
                else:
                    return {
                        "success": False,
                        "result": None,
                        "stdout": stdout,
                        "stderr": stderr,
                        "duration_ms": duration_ms,
                        "error": f"Process exited with code {process.returncode}"
                    }
                    
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                duration_ms = (time.time() - start_time) * 1000
                return {
                    "success": False,
                    "result": None,
                    "stdout": "",
                    "stderr": f"Process timed out after {timeout_s}s",
                    "duration_ms": duration_ms,
                    "error": "Timeout"
                }
                
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return {
                "success": False,
                "result": None,
                "stdout": "",
                "stderr": "",
                "duration_ms": duration_ms,
                "error": f"Execution failed: {e}"
            }


def _set_resource_limits(timeout_s: float, mem_mb: int):
    """Set resource limits for the subprocess."""
    try:
        # Set CPU time limit (in seconds)
        cpu_limit = int(timeout_s * 2)  # Allow some buffer
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit))
        
        # Set memory limit (in bytes)
        mem_limit = mem_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem_limit, mem_limit))
        
        # Set other limits for security
        resource.setrlimit(resource.RLIMIT_NPROC, (50, 50))  # Limit processes
        resource.setrlimit(resource.RLIMIT_NOFILE, (10, 10))  # Limit file descriptors
        
    except (OSError, ValueError) as e:
        # If we can't set limits, continue anyway (some systems may not support all limits)
        pass
