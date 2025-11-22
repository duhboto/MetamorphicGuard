import time
import pytest
import threading
from unittest.mock import patch, MagicMock
from typing import Any, Dict, List, Tuple

from metamorphic_guard.dispatch.queue_dispatcher import QueueDispatcher
from metamorphic_guard.queue_adapter import InMemoryQueueAdapter

class MockRunCase:
    def __init__(self):
        self.calls = []

    def __call__(self, idx: int, args: Tuple[Any, ...]) -> Dict[str, Any]:
        self.calls.append((idx, args))
        return {"success": True, "result": f"processed {args[0]}"}

@pytest.fixture
def dispatcher_config():
    return {
        "backend": "memory",
        "heartbeat_timeout": 0.5,
        "heartbeat_check_interval": 0.1,
        "circuit_breaker_threshold": 2,
        "spawn_local_workers": False,  # We will manage workers manually
        "enable_requeue": True,
        "global_timeout": 5.0,
        "metrics_interval": 0.1,
        "result_poll_timeout": 0.1,  # Ensure fast polling for tests
    }

def test_dropped_heartbeats_requeue(dispatcher_config):
    """Test that tasks assigned to workers with dropped heartbeats are requeued."""
    
    # Create inputs
    inputs = [("input1",)]
    run_case = MockRunCase()
    
    # Use a mock time to control flow
    with patch("time.monotonic") as mock_time:
        start_time = 1000.0
        mock_time.return_value = start_time
        
        # Setup dispatcher inside patch so HeartbeatManager gets mocked time
        dispatcher = QueueDispatcher(workers=1, config=dispatcher_config)
        
        results_container = []
        def run_dispatcher():
            try:
                res = dispatcher.execute(
                    test_inputs=inputs,
                    run_case=run_case,
                    role="candidate"
                )
                results_container.append(res)
            except Exception as e:
                results_container.append(e)

        dispatcher_thread = threading.Thread(target=run_dispatcher)
        dispatcher_thread.start()
        
        time.sleep(0.1)
        
        worker_id = "worker-1"
        dispatcher.adapter.register_worker(worker_id)
        
        task = dispatcher.adapter.consume_task(worker_id)
        assert task is not None
        
        # Simulate dropped heartbeats
        mock_time.return_value = start_time + 2.0
        
        time.sleep(0.2) 
        
        worker_id_2 = "worker-2"
        dispatcher.adapter.register_worker(worker_id_2)
        
        task_retry = None
        for _ in range(10):
            task_retry = dispatcher.adapter.consume_task(worker_id_2, timeout=0.1)
            if task_retry:
                break
            time.sleep(0.1)
            
        assert task_retry is not None, "Task should have been requeued"
        
        from metamorphic_guard.queue_adapter import QueueResult
        result = QueueResult(
            job_id=task_retry.job_id,
            task_id=task_retry.task_id,
            case_index=task_retry.case_indices[0],
            role=task_retry.role,
            result={"success": True, "result": "recovered"}
        )
        dispatcher.adapter.publish_result(result)
        
        dispatcher_thread.join(timeout=2.0)
        
        assert len(results_container) == 1

def test_worker_crash_simulation(dispatcher_config):
    """Test that tasks are requeued when a worker crashes."""
    inputs = [("input1",), ("input2",)]
    run_case = MockRunCase()
    
    with patch("time.monotonic") as mock_time:
        start_time = 2000.0
        mock_time.return_value = start_time
        
        dispatcher = QueueDispatcher(workers=1, config=dispatcher_config)
        
        results_container = []
        def run_dispatcher():
            try:
                res = dispatcher.execute(
                    test_inputs=inputs,
                    run_case=run_case,
                    role="candidate"
                )
                results_container.append(res)
            except Exception as e:
                results_container.append(e)

        t = threading.Thread(target=run_dispatcher)
        t.start()
        
        time.sleep(0.1)
        
        w1 = "worker-crasher"
        dispatcher.adapter.register_worker(w1)
        task1 = dispatcher.adapter.consume_task(w1, timeout=0.1)
        
        w2 = "worker-steady"
        dispatcher.adapter.register_worker(w2)
        task2 = dispatcher.adapter.consume_task(w2, timeout=0.1)
        
        step = 0.0
        for _ in range(5):
            step += 0.4 
            mock_time.return_value = start_time + step
            dispatcher.adapter.register_worker(w2) 
            time.sleep(0.05)
            
        assert dispatcher.adapter.is_worker_lost(w1)
        assert not dispatcher.adapter.is_worker_lost(w2)
        
        from metamorphic_guard.queue_adapter import QueueResult
        res2 = QueueResult(
            job_id=task2.job_id,
            task_id=task2.task_id,
            case_index=task2.case_indices[0],
            role=task2.role,
            result={"success": True, "val": 2}
        )
        dispatcher.adapter.publish_result(res2)
        
        task1_retry = None
        for _ in range(10):
            task1_retry = dispatcher.adapter.consume_task(w2, timeout=0.1)
            if task1_retry:
                break
            time.sleep(0.1)
            
        assert task1_retry is not None
        
        res1 = QueueResult(
            job_id=task1_retry.job_id,
            task_id=task1_retry.task_id,
            case_index=task1_retry.case_indices[0],
            role=task1_retry.role,
            result={"success": True, "val": 1}
        )
        dispatcher.adapter.publish_result(res1)
        
        t.join(timeout=2.0)
        assert len(results_container) == 1

def test_requeue_limit_deadlock():
    """Test forced deadlock prevention via requeue limits."""
    config = {
        "backend": "memory",
        "heartbeat_timeout": 0.1,
        "heartbeat_check_interval": 0.1,
        "circuit_breaker_threshold": 2,
        "spawn_local_workers": False,
        "enable_requeue": True,
        "global_timeout": 5.0,
        "metrics_interval": 0.1,
        "result_poll_timeout": 0.1,
        "max_requeue_attempts": 2,
    }
    
    inputs = [("input1",)]
    run_case = MockRunCase()
    
    with patch("time.monotonic") as mock_time:
        start_time = 1000.0
        mock_time.return_value = start_time
        
        dispatcher = QueueDispatcher(workers=1, config=config)
        
        results_container = []
        def run_dispatcher():
            try:
                dispatcher.execute(
                    test_inputs=inputs,
                    run_case=run_case,
                    role="candidate"
                )
            except Exception as e:
                results_container.append(e)
        
        t = threading.Thread(target=run_dispatcher)
        t.start()
        
        time.sleep(0.1)
        
        # Initial take
        w1 = "worker-1"
        dispatcher.adapter.register_worker(w1)
        dispatcher.adapter.consume_task(w1, timeout=0.1)
        
        # Requeue 1
        mock_time.return_value = start_time + 1.0
        time.sleep(0.1)
        w2 = "worker-2"
        dispatcher.adapter.register_worker(w2)
        dispatcher.adapter.consume_task(w2, timeout=0.1)
        
        # Requeue 2
        mock_time.return_value = start_time + 2.0
        time.sleep(0.1)
        w3 = "worker-3"
        dispatcher.adapter.register_worker(w3)
        dispatcher.adapter.consume_task(w3, timeout=0.1)
        
        # Requeue 3 -> Limit hit
        mock_time.return_value = start_time + 3.0
        time.sleep(0.1)
        w4 = "worker-4"
        dispatcher.adapter.register_worker(w4)
        task_final = dispatcher.adapter.consume_task(w4, timeout=0.1)
        assert task_final is None
        
        mock_time.return_value = start_time + 10.0 
        time.sleep(0.2)
        
        t.join(timeout=2.0)
        assert isinstance(results_container[0], TimeoutError)

def test_worker_starvation_logic():
    """Test requeue logic when workers are starving."""
    config = {
        "backend": "memory",
        "heartbeat_timeout": 0.5,
        "heartbeat_check_interval": 0.1,
        "circuit_breaker_threshold": 2,
        "spawn_local_workers": False,
        "enable_requeue": True,
        "global_timeout": 5.0,
        "metrics_interval": 0.1,
        "result_poll_timeout": 0.1,
        "lease_seconds": 0.5, 
    }
    
    inputs = [("input1",)]
    run_case = MockRunCase()
    
    with patch("time.monotonic") as mock_time:
        start_time = 1000.0
        mock_time.return_value = start_time
        
        dispatcher = QueueDispatcher(workers=1, config=config)
        
        results_container = []
        def run_dispatcher():
            try:
                res = dispatcher.execute(
                    test_inputs=inputs,
                    run_case=run_case,
                    role="candidate"
                )
                results_container.append(res)
            except Exception as e:
                results_container.append(e)
        
        t = threading.Thread(target=run_dispatcher)
        t.start()
        time.sleep(0.1)
        
        w1 = "worker-slow"
        dispatcher.adapter.register_worker(w1)
        task = dispatcher.adapter.consume_task(w1, timeout=0.1)
        
        # Advance time past lease
        mock_time.return_value = start_time + 1.0 
        dispatcher.adapter.register_worker(w1)
        time.sleep(0.1)
        
        w2 = "worker-fast"
        dispatcher.adapter.register_worker(w2)
        task_retry = dispatcher.adapter.consume_task(w2, timeout=0.1)
        assert task_retry is not None
        assert task_retry.task_id == task.task_id
        
        from metamorphic_guard.queue_adapter import QueueResult
        result = QueueResult(
            job_id=task_retry.job_id,
            task_id=task_retry.task_id,
            case_index=task_retry.case_indices[0],
            role=task_retry.role,
            result={"success": True}
        )
        dispatcher.adapter.publish_result(result)
        
        t.join(timeout=2.0)
        assert isinstance(results_container[0], list)


