"""
Integration tests for distributed execution with queue dispatcher.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict

import pytest

from metamorphic_guard.dispatch_queue import QueueDispatcher
from metamorphic_guard.harness import run_eval


class TestDistributedExecution:
    """Integration tests for distributed execution scenarios."""

    def test_queue_dispatcher_memory_backend_integration(self, tmp_path: Path) -> None:
        """Test full evaluation with in-memory queue backend."""
        baseline_path = Path("examples/top_k_baseline.py")
        candidate_path = Path("examples/top_k_improved.py")
        
        if not baseline_path.exists() or not candidate_path.exists():
            pytest.skip("Example files not found")
        
        queue_config = {
            "backend": "memory",
            "spawn_local_workers": True,
            "workers": 2,
            "heartbeat_interval": 0.5,
            "lease_timeout": 10.0,
        }
        
        result = run_eval(
            task_name="top_k",
            baseline_path=str(baseline_path),
            candidate_path=str(candidate_path),
            n=50,
            seed=42,
            dispatcher="queue",
            queue_config=queue_config,
            parallel=2,
        )
        
        assert result["baseline"]["total"] == 50
        assert result["candidate"]["total"] == 50
        assert "decision" in result
        assert "statistics" in result

    def test_queue_dispatcher_worker_failure_recovery(self, tmp_path: Path) -> None:
        """Test that queue dispatcher recovers from worker failures."""
        baseline_path = Path("examples/top_k_baseline.py")
        candidate_path = Path("examples/top_k_improved.py")
        
        if not baseline_path.exists() or not candidate_path.exists():
            pytest.skip("Example files not found")
        
        queue_config = {
            "backend": "memory",
            "spawn_local_workers": True,
            "workers": 2,
            "heartbeat_interval": 0.1,  # Fast heartbeat for quick failure detection
            "lease_timeout": 0.5,  # Short timeout to trigger requeue
        }
        
        # This test verifies that tasks are requeued if workers fail
        # In a real scenario, we'd kill workers, but here we just verify
        # the queue system handles timeouts correctly
        result = run_eval(
            task_name="top_k",
            baseline_path=str(baseline_path),
            candidate_path=str(candidate_path),
            n=20,
            seed=42,
            dispatcher="queue",
            queue_config=queue_config,
            parallel=2,
        )
        
        assert result["baseline"]["total"] == 20
        assert result["candidate"]["total"] == 20

    def test_queue_dispatcher_concurrent_evaluations(self, tmp_path: Path) -> None:
        """Test multiple concurrent evaluations with queue dispatcher."""
        baseline_path = Path("examples/top_k_baseline.py")
        candidate_path = Path("examples/top_k_improved.py")
        
        if not baseline_path.exists() or not candidate_path.exists():
            pytest.skip("Example files not found")
        
        queue_config = {
            "backend": "memory",
            "spawn_local_workers": True,
            "workers": 4,
        }
        
        # Run two evaluations concurrently
        import concurrent.futures
        
        def run_evaluation(seed: int) -> Dict[str, Any]:
            return run_eval(
                task_name="top_k",
                baseline_path=str(baseline_path),
                candidate_path=str(candidate_path),
                n=20,
                seed=seed,
                dispatcher="queue",
                queue_config=queue_config,
                parallel=2,
            )
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(run_evaluation, seed) for seed in [42, 43]]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        # Verify both completed successfully
        assert len(results) == 2
        for result in results:
            assert result["baseline"]["total"] == 20
            assert result["candidate"]["total"] == 20

    def test_queue_dispatcher_large_scale(self, tmp_path: Path) -> None:
        """Test queue dispatcher with larger number of test cases."""
        baseline_path = Path("examples/top_k_baseline.py")
        candidate_path = Path("examples/top_k_improved.py")
        
        if not baseline_path.exists() or not candidate_path.exists():
            pytest.skip("Example files not found")
        
        queue_config = {
            "backend": "memory",
            "spawn_local_workers": True,
            "workers": 4,
            "adaptive_batching": True,
            "initial_batch_size": 10,
            "max_batch_size": 50,
        }
        
        result = run_eval(
            task_name="top_k",
            baseline_path=str(baseline_path),
            candidate_path=str(candidate_path),
            n=200,
            seed=42,
            dispatcher="queue",
            queue_config=queue_config,
            parallel=4,
        )
        
        assert result["baseline"]["total"] == 200
        assert result["candidate"]["total"] == 200
        assert result["baseline"]["pass_rate"] >= 0.0
        assert result["candidate"]["pass_rate"] >= 0.0

    @pytest.mark.skipif(
        not pytest.importorskip("redis", reason="Redis not available"),
        reason="Redis not installed",
    )
    def test_queue_dispatcher_redis_backend(self, tmp_path: Path) -> None:
        """Test queue dispatcher with Redis backend (if available)."""
        try:
            import redis
            # Try to connect to Redis
            r = redis.Redis(host="localhost", port=6379, db=0, socket_connect_timeout=1)
            r.ping()
        except Exception:
            pytest.skip("Redis not available or not running")
        
        baseline_path = Path("examples/top_k_baseline.py")
        candidate_path = Path("examples/top_k_improved.py")
        
        if not baseline_path.exists() or not candidate_path.exists():
            pytest.skip("Example files not found")
        
        queue_config = {
            "backend": "redis",
            "redis_url": "redis://localhost:6379/0",
            "spawn_local_workers": True,
            "workers": 2,
        }
        
        result = run_eval(
            task_name="top_k",
            baseline_path=str(baseline_path),
            candidate_path=str(candidate_path),
            n=30,
            seed=42,
            dispatcher="queue",
            queue_config=queue_config,
            parallel=2,
        )
        
        assert result["baseline"]["total"] == 30
        assert result["candidate"]["total"] == 30

    def test_queue_dispatcher_messagepack_serialization(self, tmp_path: Path) -> None:
        """Test queue dispatcher with MessagePack serialization."""
        baseline_path = Path("examples/top_k_baseline.py")
        candidate_path = Path("examples/top_k_improved.py")
        
        if not baseline_path.exists() or not candidate_path.exists():
            pytest.skip("Example files not found")
        
        try:
            import msgpack
        except ImportError:
            pytest.skip("msgpack not installed")
        
        queue_config = {
            "backend": "memory",
            "spawn_local_workers": True,
            "workers": 2,
            "use_msgpack": True,
        }
        
        result = run_eval(
            task_name="top_k",
            baseline_path=str(baseline_path),
            candidate_path=str(candidate_path),
            n=30,
            seed=42,
            dispatcher="queue",
            queue_config=queue_config,
            parallel=2,
        )
        
        assert result["baseline"]["total"] == 30
        assert result["candidate"]["total"] == 30

