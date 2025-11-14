"""
Agent trace recording and replay for LLM agent evaluation.

Captures conversation history, intermediate reasoning steps, and tool calls
for debugging and replaying agent interactions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class AgentTrace:
    """Trace of an agent interaction."""
    case_index: int
    role: str  # "baseline" or "candidate"
    timestamp: datetime = field(default_factory=datetime.now)
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    intermediate_steps: List[Dict[str, Any]] = field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    final_output: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize trace to dictionary."""
        return {
            "case_index": self.case_index,
            "role": self.role,
            "timestamp": self.timestamp.isoformat(),
            "conversation_history": self.conversation_history,
            "intermediate_steps": self.intermediate_steps,
            "tool_calls": self.tool_calls,
            "final_output": self.final_output,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentTrace":
        """Deserialize trace from dictionary."""
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.now()
        
        return cls(
            case_index=data.get("case_index", 0),
            role=data.get("role", "candidate"),
            timestamp=timestamp,
            conversation_history=data.get("conversation_history", []),
            intermediate_steps=data.get("intermediate_steps", []),
            tool_calls=data.get("tool_calls", []),
            final_output=data.get("final_output"),
            metadata=data.get("metadata", {}),
        )


class AgentTraceRecorder:
    """Records agent traces during evaluation."""
    
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.traces: Dict[int, AgentTrace] = {}
    
    def start_trace(
        self,
        case_index: int,
        role: str,
        initial_conversation: Optional[List[Dict[str, str]]] = None,
    ) -> None:
        """Start recording a trace for a test case."""
        if not self.enabled:
            return
        
        trace = AgentTrace(
            case_index=case_index,
            role=role,
            conversation_history=list(initial_conversation) if initial_conversation else [],
        )
        self.traces[case_index] = trace
    
    def add_message(
        self,
        case_index: int,
        role: str,
        content: str,
        message_role: str = "assistant",
    ) -> None:
        """Add a message to the conversation history."""
        if not self.enabled:
            return
        
        if case_index not in self.traces:
            self.start_trace(case_index, role)
        
        trace = self.traces[case_index]
        trace.conversation_history.append({
            "role": message_role,
            "content": content,
        })
    
    def add_intermediate_step(
        self,
        case_index: int,
        step_type: str,
        data: Dict[str, Any],
    ) -> None:
        """Add an intermediate reasoning step."""
        if not self.enabled:
            return
        
        if case_index not in self.traces:
            self.start_trace(case_index, "candidate")
        
        trace = self.traces[case_index]
        trace.intermediate_steps.append({
            "type": step_type,
            "timestamp": datetime.now().isoformat(),
            **data,
        })
    
    def add_tool_call(
        self,
        case_index: int,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_output: Any,
    ) -> None:
        """Add a tool call to the trace."""
        if not self.enabled:
            return
        
        if case_index not in self.traces:
            self.start_trace(case_index, "candidate")
        
        trace = self.traces[case_index]
        trace.tool_calls.append({
            "tool_name": tool_name,
            "input": tool_input,
            "output": tool_output,
            "timestamp": datetime.now().isoformat(),
        })
    
    def finalize_trace(
        self,
        case_index: int,
        final_output: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Finalize a trace with the final output."""
        if not self.enabled:
            return
        
        if case_index not in self.traces:
            self.start_trace(case_index, "candidate")
        
        trace = self.traces[case_index]
        trace.final_output = final_output
        if metadata:
            trace.metadata.update(metadata)
    
    def get_trace(self, case_index: int) -> Optional[AgentTrace]:
        """Get trace for a case index."""
        return self.traces.get(case_index)
    
    def get_all_traces(self) -> List[AgentTrace]:
        """Get all recorded traces."""
        return list(self.traces.values())
    
    def save_traces(self, file_path: Path) -> None:
        """Save all traces to a JSON file."""
        if not self.enabled:
            return
        
        traces_data = [trace.to_dict() for trace in self.traces.values()]
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(json.dumps(traces_data, indent=2), encoding="utf-8")
    
    @classmethod
    def load_traces(cls, file_path: Path) -> List[AgentTrace]:
        """Load traces from a JSON file."""
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return [AgentTrace.from_dict(trace_data) for trace_data in data]


def extract_trace_from_result(
    result: Dict[str, Any],
    case_index: int,
    role: str,
) -> AgentTrace:
    """
    Extract agent trace from an execution result.
    
    For LLM executors, captures conversation history if available.
    """
    trace = AgentTrace(case_index=case_index, role=role)
    
    # Extract conversation history if available in result
    if "conversation_history" in result:
        trace.conversation_history = result["conversation_history"]
    
    # Extract final output
    trace.final_output = result.get("result") or result.get("stdout", "")
    
    # Extract metadata
    trace.metadata = {
        "success": result.get("success", False),
        "duration_ms": result.get("duration_ms", 0.0),
        "tokens_prompt": result.get("tokens_prompt"),
        "tokens_completion": result.get("tokens_completion"),
        "tokens_total": result.get("tokens_total"),
        "cost_usd": result.get("cost_usd"),
        "error": result.get("error"),
        "error_code": result.get("error_code"),
    }
    
    return trace


def replay_trace(trace: AgentTrace, executor: Any) -> Dict[str, Any]:
    """
    Replay an agent trace using an executor.
    
    Args:
        trace: AgentTrace to replay
        executor: LLM executor instance
        
    Returns:
        Execution result dictionary
    """
    # Reconstruct conversation from trace
    conversation_history = trace.conversation_history.copy()
    
    # Determine last user message (or use final output as prompt)
    if trace.final_output:
        user_prompt = trace.final_output
    else:
        # Extract last user message from history
        user_messages = [msg for msg in conversation_history if msg.get("role") == "user"]
        user_prompt = user_messages[-1].get("content", "") if user_messages else ""
    
    # Execute with conversation history
    # Note: This requires executor to support multi-turn conversations
    # Format: (conversation_history, user_prompt)
    args = (conversation_history, user_prompt)
    
    result = executor.execute(
        file_path="",  # Not needed for LLM executors
        func_name="",  # Use executor's default model
        args=args,
        timeout_s=30.0,
        mem_mb=512,
    )
    
    return result

