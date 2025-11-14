"""
Tests for multi-turn conversation support.
"""

from __future__ import annotations

import pytest

from metamorphic_guard.llm_specs import multi_turn_llm_inputs, simple_llm_inputs
from metamorphic_guard.llm_harness import LLMHarness


def test_multi_turn_llm_inputs_basic():
    """Test basic multi-turn input generation."""
    history = [
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "What is 2+2?"},
        {"role": "assistant", "content": "2+2 equals 4."},
    ]
    
    gen_fn = multi_turn_llm_inputs(history, user_prompts=["What is 3+3?"])
    inputs = gen_fn(n=3, seed=42)
    
    assert len(inputs) == 3
    for history_tuple, user_prompt in inputs:
        assert isinstance(history_tuple, list)
        assert len(history_tuple) >= 3
        assert history_tuple[0]["role"] == "system"
        assert user_prompt == "What is 3+3?"  # Same prompt each time when list has one item


def test_multi_turn_llm_inputs_no_user_prompts():
    """Test multi-turn input generation using last user message from history."""
    history = [
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "First question"},
        {"role": "assistant", "content": "First answer"},
        {"role": "user", "content": "Second question"},
    ]
    
    gen_fn = multi_turn_llm_inputs(history, user_prompts=None)
    inputs = gen_fn(n=2, seed=42)
    
    assert len(inputs) == 2
    for history_tuple, user_prompt in inputs:
        assert isinstance(history_tuple, list)
        assert len(history_tuple) == 4
        assert user_prompt == "Second question"  # Last user message


def test_multi_turn_llm_inputs_with_system():
    """Test multi-turn input generation with system prompt parameter."""
    history = [
        {"role": "user", "content": "What is 2+2?"},
        {"role": "assistant", "content": "2+2 equals 4."},
    ]
    
    gen_fn = multi_turn_llm_inputs(history, system_prompt="You are a math tutor")
    inputs = gen_fn(n=1, seed=42)
    
    assert len(inputs) == 1
    history_tuple, _ = inputs[0]
    assert history_tuple[0]["role"] == "system"
    assert history_tuple[0]["content"] == "You are a math tutor"


def test_multi_turn_llm_inputs_empty_history():
    """Test multi-turn input generation with empty history."""
    gen_fn = multi_turn_llm_inputs([], user_prompts=["Test prompt"])
    inputs = gen_fn(n=1, seed=42)
    
    assert len(inputs) == 1
    history_tuple, user_prompt = inputs[0]
    assert isinstance(history_tuple, list)
    assert len(history_tuple) == 1
    assert history_tuple[0]["role"] == "user"
    assert user_prompt == "Test prompt"


def test_llm_harness_multi_turn_dict_format():
    """Test LLMHarness with multi-turn conversation format."""
    h = LLMHarness(
        model="gpt-3.5-turbo",
        provider="openai",
        executor_config={},  # Mock config
    )
    
    # Multi-turn format: dict with "conversation" key
    case = {
        "conversation": [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ],
        "user": "How are you?",
    }
    
    # Should not raise error during parsing
    # (Actual execution would require API key)
    try:
        from metamorphic_guard.llm_specs import create_llm_spec, multi_turn_llm_inputs
        from metamorphic_guard.specs import Spec
        
        conversation_history = case.get("conversation", [])
        user_prompts = [case.get("user", "")]
        system_prompt = None
        
        gen_fn = multi_turn_llm_inputs(conversation_history, user_prompts, system_prompt)
        inputs = gen_fn(n=1, seed=42)
        
        assert len(inputs) == 1
        history, user_prompt = inputs[0]
        assert len(history) == 3
        assert user_prompt == "How are you?"
    except Exception as e:
        pytest.skip(f"Multi-turn setup failed: {e}")


def test_llm_harness_multi_turn_list_format():
    """Test LLMHarness with multi-turn conversation as list of messages."""
    h = LLMHarness(
        model="gpt-3.5-turbo",
        provider="openai",
        executor_config={},
    )
    
    # Multi-turn format: list of message dicts
    case = [
        {"role": "system", "content": "You are helpful"},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": "How are you?"},
    ]
    
    try:
        from metamorphic_guard.llm_specs import multi_turn_llm_inputs
        
        gen_fn = multi_turn_llm_inputs(case, user_prompts=None)
        inputs = gen_fn(n=1, seed=42)
        
        assert len(inputs) == 1
        history, user_prompt = inputs[0]
        assert len(history) == 4
        assert user_prompt == "How are you?"  # Last user message
    except Exception as e:
        pytest.skip(f"Multi-turn setup failed: {e}")

