
import pytest
from unittest.mock import MagicMock, patch
from metamorphic_guard.harness.adaptive_execution import execute_adaptively
from metamorphic_guard.harness.execution import ExecutionPlan
from metamorphic_guard.adaptive import AdaptiveConfig, AdaptiveDecision

@pytest.fixture
def mock_spec():
    spec = MagicMock()
    # Mock gen_inputs to return dummy inputs
    spec.gen_inputs.side_effect = lambda n, s: [("input", i) for i in range(n)]
    return spec

@pytest.fixture
def mock_execute_impl():
    with patch("metamorphic_guard.harness.adaptive_execution.execute_implementations") as mock:
        # Return dummy results
        def side_effect(plan, **kwargs):
            # Return results for the chunk
            n = len(plan.test_inputs)
            base = [{"status": "ok", "pass": True, "success": True, "result": "res"}] * n
            cand = [{"status": "ok", "pass": True, "success": True, "result": "res"}] * n
            return base, cand
        mock.side_effect = side_effect
        yield mock

@pytest.fixture
def mock_should_continue():
    with patch("metamorphic_guard.harness.adaptive_execution.should_continue_adaptive") as mock:
        yield mock

def test_adaptive_grows_sample_size(mock_spec, mock_execute_impl, mock_should_continue):
    # Setup
    initial_inputs = [("init", i) for i in range(10)]
    plan = ExecutionPlan(
        spec=mock_spec,
        test_inputs=initial_inputs, # Start with 10
        dispatcher=MagicMock(),
        monitors=[],
        worker_count=1,
        run_id="test_run"
    )
    
    adaptive_config = AdaptiveConfig(
        enabled=True,
        min_sample_size=5,
        check_interval=5,
        max_sample_size=20,
        group_sequential=False
    )
    
    # Mock decisions:
    # 1. First check (at n=5): Power low, recommend n=15
    # 2. Second check (at n=10): Power still low, recommend n=15 (already planned)
    # 3. Third check (at n=15): Power sufficient, stop.
    
    def decision_side_effect(baseline_metrics, candidate_metrics, current_n, **kwargs):
        if current_n <= 10:
            return AdaptiveDecision(
                continue_sampling=True,
                recommended_n=15,
                current_power=0.5,
                reason="low_power"
            )
        else:
            return AdaptiveDecision(
                continue_sampling=False, # Stop
                recommended_n=15,
                current_power=0.95,
                reason="sufficient_power"
            )
            
    mock_should_continue.side_effect = decision_side_effect
    
    # Execute
    base, cand, metadata = execute_adaptively(
        plan=plan,
        baseline_path="b.py", candidate_path="c.py",
        timeout_s=1, mem_mb=1,
        executor="local", executor_config={},
        baseline_executor=None, baseline_executor_config=None,
        candidate_executor=None, candidate_executor_config=None,
        alpha=0.05, min_delta=0.01, power_target=0.8,
        adaptive_config=adaptive_config,
        violation_cap=10, seed=42, shrink_violations=False,
        spec=mock_spec
    )
    
    # Verify
    # Should have grown from 10 to 15
    assert len(plan.test_inputs) == 15
    assert metadata["final_n"] == 15
    # Check that gen_inputs was called to add 5 cases (15 - 10)
    # The original inputs were 10.
    # Check calls to gen_inputs
    assert mock_spec.gen_inputs.called
    
    # Verify flow
    # Chunk 1: 5 items
    # Chunk 2: 5 items (reached 10, decision says go to 15)
    # Chunk 3: 5 items (reached 15, decision says stop)
    assert mock_execute_impl.call_count >= 3

