"""
Tests for the OpenAI and Anthropic executors.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from metamorphic_guard.executors.openai import OpenAIExecutor
from metamorphic_guard.executors.anthropic import AnthropicExecutor


class DummyAPIError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


def _stub_openai(monkeypatch, client_cls=SimpleNamespace):
    class DummyClient:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key

    module = SimpleNamespace(OpenAI=DummyClient)
    monkeypatch.setattr("metamorphic_guard.executors.openai.openai", module)


def _stub_anthropic(monkeypatch):
    class DummyClient:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key

    module = SimpleNamespace(Anthropic=DummyClient)
    monkeypatch.setattr("metamorphic_guard.executors.anthropic.anthropic", module)


@pytest.mark.parametrize("status_code", [429, 500])
def test_openai_executor_retries_and_succeeds(monkeypatch, status_code):
    _stub_openai(monkeypatch)
    monkeypatch.setattr("metamorphic_guard.executors.__init__.time.sleep", lambda *_args, **_kwargs: None)

    executor = OpenAIExecutor(
        {
            "api_key": "test",
            "max_retries": 2,
            "retry_backoff_base": 0,
            "retry_jitter": 0,
        }
    )

    attempts = {"count": 0}

    def fake_call_llm(self, **_kwargs):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise DummyAPIError("rate limited", status_code)
        return {
            "content": "ok",
            "tokens_prompt": 10,
            "tokens_completion": 5,
            "tokens_total": 15,
            "cost_usd": 0.0025,
            "finish_reason": "stop",
        }

    monkeypatch.setattr(OpenAIExecutor, "_call_llm", fake_call_llm, raising=False)

    result = executor.execute("system prompt", "gpt-4", ("Hello there",))

    assert result["success"] is True
    assert result["retries"] == 2
    assert attempts["count"] == 3
    assert result["cost_usd"] == pytest.approx(0.0025)
    assert result["tokens_total"] == 15


def test_openai_executor_stops_on_non_retry_error(monkeypatch):
    _stub_openai(monkeypatch)
    monkeypatch.setattr("metamorphic_guard.executors.__init__.time.sleep", lambda *_args, **_kwargs: None)

    executor = OpenAIExecutor(
        {
            "api_key": "test",
            "max_retries": 3,
            "retry_backoff_base": 0,
            "retry_jitter": 0,
        }
    )

    def fake_call_llm(self, **_kwargs):
        raise DummyAPIError("invalid request", 400)

    monkeypatch.setattr(OpenAIExecutor, "_call_llm", fake_call_llm, raising=False)

    result = executor.execute("system", "gpt-4", ("Hello",))

    assert result["success"] is False
    assert result["retries"] == 0
    assert result["error_code"] == "invalid_request"


def test_anthropic_executor_retries(monkeypatch):
    _stub_anthropic(monkeypatch)
    monkeypatch.setattr("metamorphic_guard.executors.__init__.time.sleep", lambda *_args, **_kwargs: None)

    executor = AnthropicExecutor(
        {
            "api_key": "test",
            "max_retries": 1,
            "retry_backoff_base": 0,
            "retry_jitter": 0,
        }
    )

    attempts = {"count": 0}

    def fake_call_llm(self, **_kwargs):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise DummyAPIError("temporary unavailable", 503)
        return {
            "content": "ok",
            "tokens_prompt": 12,
            "tokens_completion": 3,
            "tokens_total": 15,
            "cost_usd": 0.03,
            "finish_reason": "end_turn",
        }

    monkeypatch.setattr(AnthropicExecutor, "_call_llm", fake_call_llm, raising=False)

    result = executor.execute("system", "claude-3-sonnet-20240229", ("Explain safety",))

    assert result["success"] is True
    assert result["retries"] == 1
    assert attempts["count"] == 2

