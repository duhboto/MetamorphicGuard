"""
Tests for gate adoption decision logic.
"""

import pytest
from metamorphic_guard.gate import decide_adopt


def test_decide_adopt_success():
    """Test adoption when all conditions are met."""
    result = {
        "candidate": {
            "pass_rate": 0.95,
            "prop_violations": [],
            "mr_violations": []
        },
        "delta_ci": [0.05, 0.15]  # Lower bound > 0.02
    }
    
    decision = decide_adopt(result, min_delta=0.02, min_pass_rate=0.80)
    
    assert decision["adopt"] is True
    assert decision["reason"] == "meets_gate"


def test_decide_adopt_property_violations():
    """Test rejection due to property violations."""
    result = {
        "candidate": {
            "pass_rate": 0.95,
            "prop_violations": [{"test_case": 1, "property": "test"}],
            "mr_violations": []
        },
        "delta_ci": [0.05, 0.15]
    }
    
    decision = decide_adopt(result, min_delta=0.02, min_pass_rate=0.80)
    
    assert decision["adopt"] is False
    assert "Property violations" in decision["reason"]


def test_decide_adopt_mr_violations():
    """Test rejection due to metamorphic relation violations."""
    result = {
        "candidate": {
            "pass_rate": 0.95,
            "prop_violations": [],
            "mr_violations": [{"test_case": 1, "relation": "test"}]
        },
        "delta_ci": [0.05, 0.15]
    }
    
    decision = decide_adopt(result, min_delta=0.02, min_pass_rate=0.80)
    
    assert decision["adopt"] is False
    assert "Metamorphic relation violations" in decision["reason"]


def test_decide_adopt_low_pass_rate():
    """Test rejection due to low pass rate."""
    result = {
        "candidate": {
            "pass_rate": 0.70,  # Below 0.80 threshold
            "prop_violations": [],
            "mr_violations": []
        },
        "delta_ci": [0.05, 0.15]
    }
    
    decision = decide_adopt(result, min_delta=0.02, min_pass_rate=0.80)
    
    assert decision["adopt"] is False
    assert "Pass rate too low" in decision["reason"]


def test_decide_adopt_insufficient_improvement():
    """Test rejection due to insufficient improvement."""
    result = {
        "candidate": {
            "pass_rate": 0.95,
            "prop_violations": [],
            "mr_violations": []
        },
        "delta_ci": [0.01, 0.15]  # Lower bound <= 0.02
    }
    
    decision = decide_adopt(result, min_delta=0.02, min_pass_rate=0.80)
    
    assert decision["adopt"] is False
    assert "Improvement insufficient" in decision["reason"]


def test_decide_adopt_boundary_conditions():
    """Test boundary conditions for adoption."""
    # Test exact threshold values
    result = {
        "candidate": {
            "pass_rate": 0.80,  # Exactly at threshold
            "prop_violations": [],
            "mr_violations": []
        },
        "delta_ci": [0.0201, 0.15]  # Just above threshold
    }
    
    decision = decide_adopt(result, min_delta=0.02, min_pass_rate=0.80)
    
    assert decision["adopt"] is True
    assert decision["reason"] == "meets_gate"
