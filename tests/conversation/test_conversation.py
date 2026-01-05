"""Tests for the main Conversation class."""

from typing import Any

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


class TestConversationInit:
    """Tests for Conversation initialization."""

    def test_default_initialization(self) -> None:
        """Test default initialization."""
        conv = Conversation()
        assert len(conv) == 0

    def test_with_custom_strategy(self) -> None:
        """Test initialization with custom strategy."""
        strategy = SlidingWindow(window_size=5)
        conv = Conversation(strategy=strategy)
        assert conv._strategy is strategy

    def test_default_strategy_is_full_history(self) -> None:
        """Test that default strategy is FullHistory."""
        conv = Conversation()
        assert isinstance(conv._strategy, FullHistory)


class TestConversationAddMessages:
    """Tests for message addition methods."""

    def test_add_system(self, empty_conversation: Conversation) -> None:
        """Test adding a system message."""
        msg = empty_conversation.add_system("You are helpful.")
        assert msg.role == "system"
        assert msg.content == "You are helpful."
        assert len(empty_conversation) == 1

    def test_add_user(self, empty_conversation: Conversation) -> None:
        """Test adding a user message."""
        msg = empty_conversation.add_user("Hello!")
        assert msg.role == "user"
        assert msg.content == "Hello!"

    def test_add_user_with_images(self, empty_conversation: Conversation) -> None:
        """Test adding a user message with images."""
        msg = empty_conversation.add_user(
            "What's this?",
            images=["https://example.com/img1.jpg", "https://example.com/img2.jpg"],
        )
        assert msg.role == "user"
        assert isinstance(msg.content, list)
        assert len(msg.content) == 3  # 1 text + 2 images
        assert msg.content[0].type == "text"
        assert msg.content[0].text == "What's this?"
        assert msg.content[1].type == "image_url"
        assert msg.content[1].image_url == "https://example.com/img1.jpg"

    def test_add_assistant(self, empty_conversation: Conversation) -> None:
        """Test adding an assistant message."""
        msg = empty_conversation.add_assistant("Hi there!")
        assert msg.role == "assistant"
        assert msg.content == "Hi there!"

    def test_add_assistant_with_tool_calls(
        self, empty_conversation: Conversation
    ) -> None:
        """Test adding an assistant message with tool calls."""
        tool_calls = [
            ToolCall(id="call_1", name="Search", arguments={"query": "test"})
        ]
        msg = empty_conversation.add_assistant("", tool_calls=tool_calls)
        assert msg.tool_calls is not None
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0].name == "Search"

    def test_add_assistant_with_dict_metadata(
        self, empty_conversation: Conversation
    ) -> None:
        """Test adding assistant message with metadata as dict."""
        msg = empty_conversation.add_assistant(
            "Response",
            metadata={"cost": 0.002, "latency_ms": 450, "model": "gpt-4o"},
        )
        assert msg.metadata.cost == 0.002
        assert msg.metadata.latency_ms == 450
        assert msg.metadata.model == "gpt-4o"

    def test_add_assistant_with_metadata_object(
        self, empty_conversation: Conversation, sample_metadata: MessageMetadata
    ) -> None:
        """Test adding assistant message with MessageMetadata object."""
        msg = empty_conversation.add_assistant("Response", metadata=sample_metadata)
        assert msg.metadata is sample_metadata

    def test_add_tool_result(self, empty_conversation: Conversation) -> None:
        """Test adding a tool result message."""
        msg = empty_conversation.add_tool_result(
            tool_call_id="call_123",
            content='{"result": "success"}',
        )
        assert msg.role == "tool"
        assert msg.tool_call_id == "call_123"
        assert msg.content == '{"result": "success"}'

    def test_add_tool_result_with_metadata(
        self, empty_conversation: Conversation
    ) -> None:
        """Test adding tool result with metadata."""
        msg = empty_conversation.add_tool_result(
            tool_call_id="call_123",
            content='{"result": "success"}',
            metadata={"latency_ms": 50},
        )
        assert msg.metadata.latency_ms == 50

    def test_messages_preserve_order(
        self, empty_conversation: Conversation
    ) -> None:
        """Test that messages preserve insertion order."""
        empty_conversation.add_system("System")
        empty_conversation.add_user("User 1")
        empty_conversation.add_assistant("Assistant 1")
        empty_conversation.add_user("User 2")

        messages = empty_conversation.get_all_messages()
        assert messages[0].content == "System"
        assert messages[1].content == "User 1"
        assert messages[2].content == "Assistant 1"
        assert messages[3].content == "User 2"

    def test_add_returns_message(self, empty_conversation: Conversation) -> None:
        """Test that add methods return the created message."""
        msg = empty_conversation.add_user("Test")
        assert isinstance(msg, Message)
        assert msg.id is not None


class TestConversationRetrieval:
    """Tests for message retrieval methods."""

    def test_get_history_empty(self, empty_conversation: Conversation) -> None:
        """Test get_history on empty conversation."""
        history = empty_conversation.get_history()
        assert history == []

    def test_get_history_format(self, sample_conversation: Conversation) -> None:
        """Test that get_history returns list of dicts."""
        history = sample_conversation.get_history()
        assert isinstance(history, list)
        assert all(isinstance(m, dict) for m in history)

    def test_get_history_contains_role_and_content(
        self, sample_conversation: Conversation
    ) -> None:
        """Test that history dicts have role and content."""
        history = sample_conversation.get_history()
        for msg in history:
            assert "role" in msg
            assert "content" in msg

    def test_get_history_with_sliding_window(self) -> None:
        """Test get_history applies strategy."""
        conv = Conversation(strategy=SlidingWindow(window_size=2))
        conv.add_system("System")
        conv.add_user("User 1")
        conv.add_assistant("Assistant 1")
        conv.add_user("User 2")
        conv.add_assistant("Assistant 2")

        history = conv.get_history()
        # System + last 2 non-system
        assert len(history) == 3
        assert history[0]["content"] == "System"
        assert history[1]["content"] == "User 2"
        assert history[2]["content"] == "Assistant 2"

    def test_get_all_messages_returns_message_objects(
        self, sample_conversation: Conversation
    ) -> None:
        """Test that get_all_messages returns Message objects."""
        messages = sample_conversation.get_all_messages()
        assert all(isinstance(m, Message) for m in messages)

    def test_get_all_messages_ignores_strategy(self) -> None:
        """Test that get_all_messages ignores the strategy."""
        conv = Conversation(strategy=SlidingWindow(window_size=1))
        conv.add_system("System")
        conv.add_user("User 1")
        conv.add_user("User 2")
        conv.add_user("User 3")

        messages = conv.get_all_messages()
        assert len(messages) == 4  # All messages, not windowed


class TestConversationMessageToDict:
    """Tests for _message_to_dict conversion."""

    def test_simple_text_message(self, empty_conversation: Conversation) -> None:
        """Test converting simple text message."""
        msg = Message(role="user", content="Hello!")
        result = empty_conversation._message_to_dict(msg)
        assert result == {"role": "user", "content": "Hello!"}

    def test_multimodal_message(self, empty_conversation: Conversation) -> None:
        """Test converting multimodal message."""
        msg = Message(
            role="user",
            content=[
                ContentBlock(type="text", text="What's this?"),
                ContentBlock(type="image_url", image_url="https://example.com/img.jpg"),
            ],
        )
        result = empty_conversation._message_to_dict(msg)
        assert result["role"] == "user"
        assert isinstance(result["content"], list)
        assert result["content"][0] == {"type": "text", "text": "What's this?"}
        assert result["content"][1] == {
            "type": "image_url",
            "image_url": "https://example.com/img.jpg",
        }

    def test_message_with_tool_calls(self, empty_conversation: Conversation) -> None:
        """Test converting message with tool calls."""
        msg = Message(
            role="assistant",
            content="",
            tool_calls=[
                ToolCall(id="call_1", name="GetWeather", arguments={"city": "NYC"})
            ],
        )
        result = empty_conversation._message_to_dict(msg)
        assert "tool_calls" in result
        assert len(result["tool_calls"]) == 1
        tc = result["tool_calls"][0]
        assert tc["id"] == "call_1"
        assert tc["type"] == "function"
        assert tc["function"]["name"] == "GetWeather"
        # Arguments should be JSON string
        assert tc["function"]["arguments"] == '{"city": "NYC"}'

    def test_tool_result_message(self, empty_conversation: Conversation) -> None:
        """Test converting tool result message."""
        msg = Message(
            role="tool",
            content='{"temp": 72}',
            tool_call_id="call_1",
        )
        result = empty_conversation._message_to_dict(msg)
        assert result["role"] == "tool"
        assert result["content"] == '{"temp": 72}'
        assert result["tool_call_id"] == "call_1"


class TestConversationUtility:
    """Tests for utility methods."""

    def test_len(self, sample_conversation: Conversation) -> None:
        """Test __len__ returns message count."""
        assert len(sample_conversation) == 4

    def test_len_empty(self, empty_conversation: Conversation) -> None:
        """Test __len__ on empty conversation."""
        assert len(empty_conversation) == 0

    def test_clear(self, sample_conversation: Conversation) -> None:
        """Test clear removes all messages."""
        sample_conversation.clear()
        assert len(sample_conversation) == 0
        assert sample_conversation.get_history() == []


class TestConversationWithTools:
    """Tests for conversations with tool usage."""

    def test_full_tool_flow(
        self, conversation_with_tools: Conversation
    ) -> None:
        """Test a complete tool usage flow."""
        history = conversation_with_tools.get_history()

        # System message
        assert history[0]["role"] == "system"

        # User request
        assert history[1]["role"] == "user"
        assert "weather" in history[1]["content"].lower()

        # Assistant tool call
        assert history[2]["role"] == "assistant"
        assert "tool_calls" in history[2]
        assert history[2]["tool_calls"][0]["function"]["name"] == "GetWeather"

        # Tool result
        assert history[3]["role"] == "tool"
        assert history[3]["tool_call_id"] == "call_abc123"

        # Final assistant response
        assert history[4]["role"] == "assistant"
        assert "72" in history[4]["content"]
