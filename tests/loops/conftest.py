"""Shared fixtures for loop tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from rawagents.utils.types import ToolCall, ToolResult
from rawagents.llm.types import ToolResponse


@pytest.fixture
def mock_conversation() -> MagicMock:
    """Mock Conversation with controllable history."""
    conv = MagicMock()
    conv.get_history.return_value = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello"},
    ]
    return conv


@pytest.fixture
def mock_llm_no_tools() -> AsyncMock:
    """Mock LLM that responds without tool calls."""
    llm = AsyncMock()
    llm.complete_with_tools.return_value = ToolResponse(
        content="Hello! How can I help?",
        model="test-model",
        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        cost=0.001,
        latency_ms=100,
        raw_response=None,
        tool_calls=[],
    )
    return llm


@pytest.fixture
def mock_llm_with_tools() -> AsyncMock:
    """Mock LLM that requests tool calls then gives final answer."""
    llm = AsyncMock()
    # First call: request tool
    # Second call: final response
    llm.complete_with_tools.side_effect = [
        ToolResponse(
            content="Let me search for that.",
            model="test-model",
            usage={"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
            cost=0.002,
            latency_ms=150,
            raw_response=None,
            tool_calls=[
                ToolCall(id="call_1", name="search", arguments={"query": "test"})
            ],
        ),
        ToolResponse(
            content="Based on the search results, here's my answer.",
            model="test-model",
            usage={"prompt_tokens": 30, "completion_tokens": 15, "total_tokens": 45},
            cost=0.003,
            latency_ms=200,
            raw_response=None,
            tool_calls=[],
        ),
    ]
    return llm


@pytest.fixture
def mock_llm_multiple_tools() -> AsyncMock:
    """Mock LLM that requests multiple tool calls in one response."""
    llm = AsyncMock()
    llm.complete_with_tools.side_effect = [
        ToolResponse(
            content="Let me search and calculate.",
            model="test-model",
            usage={"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
            cost=0.002,
            latency_ms=150,
            raw_response=None,
            tool_calls=[
                ToolCall(id="call_1", name="search", arguments={"query": "test"}),
                ToolCall(id="call_2", name="calculate", arguments={"x": 5}),
            ],
        ),
        ToolResponse(
            content="Done with both tools.",
            model="test-model",
            usage={"prompt_tokens": 30, "completion_tokens": 15, "total_tokens": 45},
            cost=0.003,
            latency_ms=200,
            raw_response=None,
            tool_calls=[],
        ),
    ]
    return llm


@pytest.fixture
def mock_llm_infinite_tools() -> AsyncMock:
    """Mock LLM that always requests tools (for max_steps testing)."""
    llm = AsyncMock()
    llm.complete_with_tools.return_value = ToolResponse(
        content="Need more info.",
        model="test-model",
        usage={"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
        cost=0.002,
        latency_ms=150,
        raw_response=None,
        tool_calls=[
            ToolCall(id="call_inf", name="search", arguments={"query": "more"})
        ],
    )
    return llm


@pytest.fixture
def mock_tools() -> AsyncMock:
    """Mock ToolExecutor that returns success."""
    executor = AsyncMock()
    executor.execute.return_value = ToolResult(
        tool_call_id="call_1",
        name="search",
        content='{"results": ["result1", "result2"]}',
        is_error=False,
    )
    return executor


@pytest.fixture
def mock_tools_multi() -> AsyncMock:
    """Mock ToolExecutor that handles multiple tools."""
    executor = AsyncMock()

    def execute_side_effect(
        tool_call: ToolCall, context: dict[str, Any] | None = None
    ) -> ToolResult:
        return ToolResult(
            tool_call_id=tool_call.id,
            name=tool_call.name,
            content=f'{{"result": "{tool_call.name}_output"}}',
            is_error=False,
        )

    executor.execute.side_effect = execute_side_effect
    return executor


@pytest.fixture
def mock_tools_with_error() -> AsyncMock:
    """Mock ToolExecutor that returns an error."""
    executor = AsyncMock()
    executor.execute.return_value = ToolResult(
        tool_call_id="call_1",
        name="search",
        content="Tool 'search' raised ValueError: Invalid query",
        is_error=True,
    )
    return executor


@pytest.fixture
def tool_models() -> list[type]:
    """Mock list of tool models for LLM."""
    # Return empty list since we're mocking the LLM anyway
    return []
