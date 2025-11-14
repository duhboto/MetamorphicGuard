"""
Tests for agent trace recording and replay.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from metamorphic_guard.agent_tracing import (
    AgentTrace,
    AgentTraceRecorder,
    extract_trace_from_result,
    replay_trace,
)


def test_agent_trace_creation():
    """Test creating an AgentTrace."""
    trace = AgentTrace(
        case_index=0,
        role="candidate",
        conversation_history=[
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ],
        final_output="Hi there!",
    )
    
    assert trace.case_index == 0
    assert trace.role == "candidate"
    assert len(trace.conversation_history) == 2
    assert trace.final_output == "Hi there!"


def test_agent_trace_serialization():
    """Test serializing and deserializing an AgentTrace."""
    trace = AgentTrace(
        case_index=1,
        role="baseline",
        conversation_history=[{"role": "user", "content": "Test"}],
        final_output="Test output",
        metadata={"test": "value"},
    )
    
    # Serialize
    data = trace.to_dict()
    assert data["case_index"] == 1
    assert data["role"] == "baseline"
    assert "conversation_history" in data
    assert data["final_output"] == "Test output"
    
    # Deserialize
    restored = AgentTrace.from_dict(data)
    assert restored.case_index == trace.case_index
    assert restored.role == trace.role
    assert restored.conversation_history == trace.conversation_history
    assert restored.final_output == trace.final_output
    assert restored.metadata == trace.metadata


def test_agent_trace_recorder():
    """Test AgentTraceRecorder."""
    recorder = AgentTraceRecorder(enabled=True)
    
    # Start trace
    recorder.start_trace(0, "candidate", [{"role": "system", "content": "You are helpful"}])
    
    # Add messages
    recorder.add_message(0, "candidate", "Hello", message_role="user")
    recorder.add_message(0, "candidate", "Hi there!", message_role="assistant")
    
    # Add intermediate step
    recorder.add_intermediate_step(0, "reasoning", {"thought": "User said hello"})
    
    # Add tool call
    recorder.add_tool_call(0, "search", {"query": "test"}, {"results": []})
    
    # Finalize
    recorder.finalize_trace(0, "Hi there!", {"success": True})
    
    # Retrieve trace
    trace = recorder.get_trace(0)
    assert trace is not None
    assert len(trace.conversation_history) >= 3  # system + user + assistant
    assert len(trace.intermediate_steps) == 1
    assert len(trace.tool_calls) == 1
    assert trace.final_output == "Hi there!"


def test_agent_trace_recorder_disabled():
    """Test that AgentTraceRecorder does nothing when disabled."""
    recorder = AgentTraceRecorder(enabled=False)
    
    recorder.start_trace(0, "candidate")
    recorder.add_message(0, "candidate", "Test")
    recorder.finalize_trace(0, "Output")
    
    assert len(recorder.get_all_traces()) == 0


def test_extract_trace_from_result():
    """Test extracting trace from execution result."""
    result = {
        "success": True,
        "result": "Test output",
        "duration_ms": 100.0,
        "tokens_total": 50,
        "cost_usd": 0.001,
        "conversation_history": [
            {"role": "user", "content": "Test"},
            {"role": "assistant", "content": "Test output"},
        ],
    }
    
    trace = extract_trace_from_result(result, case_index=0, role="candidate")
    
    assert trace.case_index == 0
    assert trace.role == "candidate"
    assert trace.final_output == "Test output"
    assert len(trace.conversation_history) == 2
    assert trace.metadata["success"] is True
    assert trace.metadata["duration_ms"] == 100.0
    assert trace.metadata["tokens_total"] == 50


def test_extract_trace_from_result_no_history():
    """Test extracting trace when conversation_history is missing."""
    result = {
        "success": True,
        "result": "Test output",
        "stdout": "Test output",
    }
    
    trace = extract_trace_from_result(result, case_index=1, role="baseline")
    
    assert trace.case_index == 1
    assert trace.final_output == "Test output"
    assert len(trace.conversation_history) == 0  # No history in result


def test_agent_trace_recorder_save_load(tmp_path):
    """Test saving and loading traces."""
    recorder = AgentTraceRecorder(enabled=True)
    
    recorder.start_trace(0, "candidate")
    recorder.add_message(0, "candidate", "Hello")
    recorder.finalize_trace(0, "Hi there!")
    
    # Save
    trace_file = tmp_path / "traces.json"
    recorder.save_traces(trace_file)
    
    assert trace_file.exists()
    
    # Load
    loaded_traces = AgentTraceRecorder.load_traces(trace_file)
    assert len(loaded_traces) == 1
    assert loaded_traces[0].case_index == 0
    assert loaded_traces[0].final_output == "Hi there!"

