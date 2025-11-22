import logging
import pytest
from typing import Any, Dict, List, Tuple
from unittest.mock import MagicMock

from metamorphic_guard.dispatch import (
    Dispatcher,
    LocalDispatcher,
    ShadowDispatcher,
    TrafficSource,
    ensure_dispatcher,
)
from metamorphic_guard.dispatch.shadow import InMemoryTrafficSource
from metamorphic_guard.redaction import SecretRedactor

class MockDispatcher(Dispatcher):
    def __init__(self):
        super().__init__(workers=1, kind="mock")
        self.executed_cases = []

    def execute(
        self,
        *,
        test_inputs: List[Tuple[Any, ...]],
        run_case: Any,
        role: str,
        monitors: Any = None,
        call_spec: Any = None,
        seed: Any = None,
    ) -> List[Dict[str, Any]]:
        results = []
        for idx, args in enumerate(test_inputs):
            self.executed_cases.append((idx, args))
            # Execute the wrapper
            results.append(run_case(idx, args))
        return results

def test_shadow_dispatcher_basic():
    """Test that ShadowDispatcher delegates execution."""
    delegate = MockDispatcher()
    shadow = ShadowDispatcher(delegate, sample_rate=1.0, safe_mode=True)

    inputs = [("input1",), ("input2",)]
    
    def run_case(idx, args):
        return {"success": True, "result": f"processed {args[0]}"}

    results = shadow.execute(
        test_inputs=inputs,
        run_case=run_case,
        role="candidate"
    )

    assert len(results) == 2
    assert results[0]["result"] == "processed input1"
    assert len(delegate.executed_cases) == 2

def test_shadow_dispatcher_redaction():
    """Test that ShadowDispatcher redacts sensitive info."""
    delegate = MockDispatcher()
    # Redact "secret"
    import re
    redactor = SecretRedactor([re.compile("secret")])
    shadow = ShadowDispatcher(delegate, redactor=redactor)

    inputs = [("input1",)]
    
    def run_case(idx, args):
        return {"success": True, "result": "this is a secret message"}

    results = shadow.execute(
        test_inputs=inputs,
        run_case=run_case,
        role="candidate"
    )

    assert results[0]["result"] == "this is a [REDACTED] message"

def test_shadow_dispatcher_safe_mode():
    """Test that ShadowDispatcher catches exceptions in safe mode."""
    delegate = MockDispatcher()
    shadow = ShadowDispatcher(delegate, safe_mode=True)

    inputs = [("input1",)]
    
    def run_case(idx, args):
        raise ValueError("Something went wrong!")

    results = shadow.execute(
        test_inputs=inputs,
        run_case=run_case,
        role="candidate"
    )

    assert results[0]["success"] is False
    assert "Shadow execution error" in results[0]["error"]
    assert results[0]["shadow_suppressed"] is True

def test_shadow_dispatcher_traffic_source():
    """Test fetching inputs from TrafficSource."""
    delegate = MockDispatcher()
    source = InMemoryTrafficSource([("traffic1",), ("traffic2",)])
    shadow = ShadowDispatcher(delegate, traffic_source=source)

    def run_case(idx, args):
        return {"success": True, "val": args[0]}

    # Pass empty inputs
    results = shadow.execute(
        test_inputs=[],
        run_case=run_case,
        role="candidate"
    )

    # Should have fetched from source
    assert len(results) > 0
    # Default batch size might fetch all
    assert any(r["val"] == "traffic1" for r in results)

def test_ensure_dispatcher_shadow():
    """Test creating shadow dispatcher via factory."""
    dispatcher = ensure_dispatcher(
        "shadow",
        workers=1,
        queue_config={"sample_rate": 0.5, "safe_mode": False}
    )
    
    assert isinstance(dispatcher, ShadowDispatcher)
    assert dispatcher.sample_rate == 0.5
    assert dispatcher.safe_mode is False
    assert isinstance(dispatcher.delegate, LocalDispatcher)




