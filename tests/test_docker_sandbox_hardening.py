
import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from metamorphic_guard.sandbox.docker import _run_docker_sandbox

@pytest.fixture
def mock_subprocess():
    with patch("metamorphic_guard.sandbox.docker.subprocess.run") as mock:
        # Default mock response
        mock.return_value.returncode = 0
        mock.return_value.stdout = '{"success": true, "result": 42}'
        mock.return_value.stderr = ""
        yield mock

@pytest.fixture
def mock_digest_resolution():
    with patch("metamorphic_guard.sandbox.docker._resolve_image_digest") as mock:
        mock.return_value = "python:3.11@sha256:1234567890abcdef"
        yield mock

def test_docker_env_file_usage(mock_subprocess, tmp_path):
    """Test that environment variables are passed via file, not CLI args."""
    # Setup
    file_path = tmp_path / "script.py"
    file_path.touch()
    
    config = {
        "env": {"SECRET_KEY": "super-secret-value", "PUBLIC_VAR": "visible"},
        "use_env_file": True  # New flag to force env file usage
    }
    
    # Execute
    _run_docker_sandbox(str(file_path), "func", (), config=config)
    
    # Verify
    # The second call to subprocess.run is the one running the container (first is inspect)
    # Actually, _run_docker_sandbox calls inspect first.
    
    # Find the call that runs 'docker run'
    run_call = None
    for call in mock_subprocess.call_args_list:
        args = call[0][0]
        if "run" in args and "docker" in args:
            run_call = args
            break
            
    assert run_call is not None
    
    # Check that secrets are NOT in CLI args
    assert "SECRET_KEY=super-secret-value" not in run_call
    assert "PUBLIC_VAR=visible" not in run_call
    
    # Check that --env-file is used
    assert "--env-file" in run_call

def test_docker_digest_enforcement(mock_subprocess, mock_digest_resolution, tmp_path):
    """Test that image tag is resolved to digest when pinned."""
    file_path = tmp_path / "script.py"
    file_path.touch()
    
    config = {
        "image": "python:3.11",
        "pin_image": True
    }
    
    _run_docker_sandbox(str(file_path), "func", (), config=config)
    
    # Verify image resolution was called
    mock_digest_resolution.assert_called_with("python:3.11")
    
    # Verify docker run used the resolved digest
    run_call = None
    for call in mock_subprocess.call_args_list:
        args = call[0][0]
        if "run" in args:
            run_call = args
            break
            
    assert "python:3.11@sha256:1234567890abcdef" in run_call

def test_docker_ulimits(mock_subprocess, tmp_path):
    """Test that ulimits are applied."""
    file_path = tmp_path / "script.py"
    file_path.touch()
    
    config = {
        "ulimits": ["nofile=1024:1024", "nproc=50"]
    }
    
    _run_docker_sandbox(str(file_path), "func", (), config=config)
    
    run_call = None
    for call in mock_subprocess.call_args_list:
        args = call[0][0]
        if "run" in args:
            run_call = args
            break
            
    assert "--ulimit" in run_call
    assert "nofile=1024:1024" in run_call
    assert "nproc=50" in run_call

