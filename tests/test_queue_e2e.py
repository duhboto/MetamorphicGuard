"""End-to-end tests for queue dispatcher."""

from __future__ import annotations

from pathlib import Path

import pytest

from metamorphic_guard.dispatch_queue import QueueDispatcher
from metamorphic_guard.harness import run_eval


def test_queue_dispatcher_in_memory_e2e(tmp_path: Path) -> None:
    """Test queue dispatcher with in-memory backend end-to-end."""
    baseline_path = Path("examples/top_k_baseline.py")
    candidate_path = Path("examples/top_k_improved.py")
    
    if not baseline_path.exists() or not candidate_path.exists():
        pytest.skip("Example files not found")
    
    # Configure in-memory queue with explicit settings for test stability
    queue_config = {
        "backend": "memory",
        "heartbeat_interval": 0.5,  # Faster heartbeat for tests
        "lease_timeout": 10.0,
        "result_poll_timeout": 2.0,  # Explicit poll timeout
        "spawn_local_workers": True,  # Ensure local workers are spawned
        "workers": 1,  # Use single worker for deterministic test
    }
    
    # Run evaluation with queue dispatcher
    result = run_eval(
        task_name="top_k",
        baseline_path=str(baseline_path),
        candidate_path=str(candidate_path),
        n=10,  # Reduced for faster test execution
        seed=42,
        dispatcher="queue",
        queue_config=queue_config,
        parallel=1,  # Ensure single worker
    )
    
    # Verify evaluation completed
    assert "baseline" in result
    assert "candidate" in result
    assert "decision" in result
    
    # Verify metrics
    baseline = result["baseline"]
    candidate = result["candidate"]
    
    assert baseline["total"] == 10, "Should have 10 baseline test cases"
    assert candidate["total"] == 10, "Should have 10 candidate test cases"
    
    # Verify decision was made
    decision = result["decision"]
    assert "adopt" in decision
    assert "reason" in decision


def test_queue_dispatcher_adaptive_batching(tmp_path: Path) -> None:
    """Test that adaptive batching works in queue dispatcher."""
    baseline_path = Path("examples/top_k_baseline.py")
    candidate_path = Path("examples/top_k_improved.py")
    
    if not baseline_path.exists() or not candidate_path.exists():
        pytest.skip("Example files not found")
    
    # Configure queue with adaptive batching
    queue_config = {
        "backend": "memory",
        "adaptive_batching": True,
        "initial_batch_size": 5,
        "max_batch_size": 10,
    }
    
    # Run evaluation
    result = run_eval(
        task_name="top_k",
        baseline_path=str(baseline_path),
        candidate_path=str(candidate_path),
        n=30,
        seed=42,
        dispatcher="queue",
        queue_config=queue_config,
    )
    
    # Verify completion
    assert result["baseline"]["total"] == 30
    assert result["candidate"]["total"] == 30


def test_queue_dispatcher_compression(tmp_path: Path) -> None:
    """Test that compression works in queue dispatcher."""
    baseline_path = Path("examples/top_k_baseline.py")
    candidate_path = Path("examples/top_k_improved.py")
    
    if not baseline_path.exists() or not candidate_path.exists():
        pytest.skip("Example files not found")
    
    # Configure queue with compression
    queue_config = {
        "backend": "memory",
        "adaptive_compress": True,
        "compress_threshold_bytes": 100,
    }
    
    # Run evaluation
    result = run_eval(
        task_name="top_k",
        baseline_path=str(baseline_path),
        candidate_path=str(candidate_path),
        n=20,
        seed=42,
        dispatcher="queue",
        queue_config=queue_config,
    )
    
    # Verify completion
    assert result["baseline"]["total"] == 20
    assert result["candidate"]["total"] == 20

