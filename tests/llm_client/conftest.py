"""Pytest fixtures for LLM client tests."""

from typing import Any
from unittest.mock import MagicMock

import pytest

from rawagents import LLMClient, LLMConfig


@pytest.fixture
def mock_litellm_response() -> MagicMock:
    """Create a mock LiteLLM response object."""
    response = MagicMock()
    message = MagicMock(content="Hello! How can I help you?", tool_calls=None)
    # Standard responses don't have reasoning attributes
    message.reasoning_content = None
    message.thinking_blocks = None
    response.choices = [
        MagicMock(
            message=message,
            finish_reason="stop",
        )
    ]
    response.model = "gpt-4o-mini"
    response.usage = MagicMock(
        prompt_tokens=10,
        completion_tokens=8,
        total_tokens=18,
    )
    response._hidden_params = {"response_cost": 0.00005}
    return response


@pytest.fixture
def mock_reasoning_response() -> MagicMock:
    """Create a mock LiteLLM response with reasoning content."""
    response = MagicMock()
    message = MagicMock(content="The answer is 42.", tool_calls=None)
    # Reasoning model response includes reasoning content
    message.reasoning_content = "Let me think about this step by step..."
    message.thinking_blocks = [
        {"type": "thinking", "thinking": "Let me think about this step by step..."}
    ]
    response.choices = [
        MagicMock(
            message=message,
            finish_reason="stop",
        )
    ]
    response.model = "o3-mini"
    response.usage = MagicMock(
        prompt_tokens=15,
        completion_tokens=100,
        total_tokens=115,
    )
    response._hidden_params = {"response_cost": 0.001}
    return response


@pytest.fixture
def mock_tool_call_response() -> MagicMock:
    """Create a mock LiteLLM response with tool calls."""
    response = MagicMock()

    tool_call = MagicMock()
    tool_call.id = "call_abc123"
    tool_call.function = MagicMock()
    tool_call.function.name = "GetWeather"
    tool_call.function.arguments = '{"location": "New York, NY"}'

    message = MagicMock(content=None, tool_calls=[tool_call])
    message.reasoning_content = None
    message.thinking_blocks = None

    response.choices = [
        MagicMock(
            message=message,
            finish_reason="tool_calls",
        )
    ]
    response.model = "gpt-4o-mini"
    response.usage = MagicMock(
        prompt_tokens=15,
        completion_tokens=12,
        total_tokens=27,
    )
    response._hidden_params = {"response_cost": 0.00008}
    return response


@pytest.fixture
def default_config() -> LLMConfig:
    """Create a default test configuration."""
    return LLMConfig(
        model="openai/gpt-4o-mini",
        retries=2,
        structured_validation_retries=2,
        timeout=30,
    )


@pytest.fixture
def client(default_config: LLMConfig) -> LLMClient:
    """Create a test client with default configuration."""
    return LLMClient(config=default_config)


@pytest.fixture
def sample_messages() -> list[dict[str, Any]]:
    """Create sample messages for testing."""
    return [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"},
    ]
