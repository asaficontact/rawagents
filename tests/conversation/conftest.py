"""Pytest fixtures for conversation component tests."""

import pytest

from rawagents.state import (
    Conversation,
    ContentBlock,
    FullHistory,
    Message,
    MessageMetadata,
    SlidingWindow,
    ToolCall,
)
from rawagents.state.storage import InMemoryStorage


@pytest.fixture
def empty_conversation() -> Conversation:
    """Create an empty conversation."""
    return Conversation()


@pytest.fixture
def sample_conversation() -> Conversation:
    """Create a conversation with some messages."""
    conv = Conversation()
    conv.add_system("You are a helpful assistant.")
    conv.add_user("Hello!")
    conv.add_assistant("Hi there! How can I help you today?")
    conv.add_user("What's the weather?")
    return conv


@pytest.fixture
def conversation_with_tools() -> Conversation:
    """Create a conversation with tool calls."""
    conv = Conversation()
    conv.add_system("You are a helpful assistant with weather tools.")
    conv.add_user("What's the weather in NYC?")
    conv.add_assistant(
        content="",
        tool_calls=[
            ToolCall(
                id="call_abc123",
                name="GetWeather",
                arguments={"location": "New York, NY"},
            )
        ],
    )
    conv.add_tool_result(
        tool_call_id="call_abc123",
        content='{"temperature": 72, "unit": "F", "condition": "sunny"}',
    )
    conv.add_assistant("The weather in NYC is 72°F and sunny!")
    return conv


@pytest.fixture
def sample_message() -> Message:
    """Create a sample user message."""
    return Message(role="user", content="Hello, world!")


@pytest.fixture
def sample_metadata() -> MessageMetadata:
    """Create sample message metadata."""
    return MessageMetadata(
        cost=0.002,
        latency_ms=450.5,
        finish_reason="stop",
        model="gpt-4o",
        custom={"request_id": "req_123"},
    )


@pytest.fixture
def multimodal_message() -> Message:
    """Create a message with multimodal content."""
    return Message(
        role="user",
        content=[
            ContentBlock(type="text", text="What's in this image?"),
            ContentBlock(type="image_url", image_url="https://example.com/image.jpg"),
        ],
    )


@pytest.fixture
def in_memory_storage() -> InMemoryStorage:
    """Create an in-memory storage instance."""
    return InMemoryStorage()


@pytest.fixture
def full_history_strategy() -> FullHistory:
    """Create a FullHistory strategy."""
    return FullHistory()


@pytest.fixture
def sliding_window_strategy() -> SlidingWindow:
    """Create a SlidingWindow strategy with window_size=3."""
    return SlidingWindow(window_size=3)
