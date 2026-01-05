"""Tests for conversation data models."""

from datetime import datetime, timezone

import pytest

from rawagents.state import ContentBlock, Message, MessageMetadata, ToolCall


class TestMessageMetadata:
    """Tests for MessageMetadata model."""

    def test_defaults(self) -> None:
        """Test default values."""
        metadata = MessageMetadata()
        assert metadata.cost is None
        assert metadata.latency_ms is None
        assert metadata.finish_reason is None
        assert metadata.model is None
        assert metadata.custom == {}

    def test_with_values(self, sample_metadata: MessageMetadata) -> None:
        """Test with provided values."""
        assert sample_metadata.cost == 0.002
        assert sample_metadata.latency_ms == 450.5
        assert sample_metadata.finish_reason == "stop"
        assert sample_metadata.model == "gpt-4o"
        assert sample_metadata.custom == {"request_id": "req_123"}

    def test_custom_field_mutable_default(self) -> None:
        """Test that custom dict doesn't share state between instances."""
        meta1 = MessageMetadata()
        meta2 = MessageMetadata()
        meta1.custom["key"] = "value"
        assert "key" not in meta2.custom


class TestContentBlock:
    """Tests for ContentBlock model."""

    def test_text_block(self) -> None:
        """Test text content block."""
        block = ContentBlock(type="text", text="Hello!")
        assert block.type == "text"
        assert block.text == "Hello!"
        assert block.image_url is None

    def test_image_block(self) -> None:
        """Test image content block."""
        block = ContentBlock(type="image_url", image_url="https://example.com/img.jpg")
        assert block.type == "image_url"
        assert block.image_url == "https://example.com/img.jpg"
        assert block.text is None

    def test_model_dump_excludes_none(self) -> None:
        """Test that model_dump with exclude_none works."""
        block = ContentBlock(type="text", text="Hello!")
        dumped = block.model_dump(exclude_none=True)
        assert "image_url" not in dumped
        assert dumped == {"type": "text", "text": "Hello!"}


class TestToolCall:
    """Tests for ToolCall model."""

    def test_creation(self) -> None:
        """Test tool call creation."""
        tc = ToolCall(
            id="call_123",
            name="GetWeather",
            arguments={"location": "NYC"},
        )
        assert tc.id == "call_123"
        assert tc.name == "GetWeather"
        assert tc.arguments == {"location": "NYC"}

    def test_complex_arguments(self) -> None:
        """Test tool call with complex arguments."""
        tc = ToolCall(
            id="call_456",
            name="Search",
            arguments={
                "query": "weather",
                "filters": {"date": "today", "limit": 10},
                "options": ["temperature", "humidity"],
            },
        )
        assert tc.arguments["filters"]["limit"] == 10
        assert "temperature" in tc.arguments["options"]


class TestMessage:
    """Tests for Message model."""

    def test_auto_generated_id(self) -> None:
        """Test that ID is auto-generated."""
        msg = Message(role="user", content="Hello!")
        assert msg.id is not None
        assert len(msg.id) == 36  # UUID format

    def test_unique_ids(self) -> None:
        """Test that each message gets a unique ID."""
        msg1 = Message(role="user", content="Hello!")
        msg2 = Message(role="user", content="Hello!")
        assert msg1.id != msg2.id

    def test_auto_generated_timestamp(self) -> None:
        """Test that timestamp is auto-generated."""
        before = datetime.now(timezone.utc)
        msg = Message(role="user", content="Hello!")
        after = datetime.now(timezone.utc)
        assert before <= msg.created_at <= after

    def test_system_message(self) -> None:
        """Test system message creation."""
        msg = Message(role="system", content="You are helpful.")
        assert msg.role == "system"
        assert msg.content == "You are helpful."

    def test_user_message(self, sample_message: Message) -> None:
        """Test user message creation."""
        assert sample_message.role == "user"
        assert sample_message.content == "Hello, world!"

    def test_assistant_message(self) -> None:
        """Test assistant message creation."""
        msg = Message(role="assistant", content="Hi there!")
        assert msg.role == "assistant"
        assert msg.content == "Hi there!"

    def test_tool_message(self) -> None:
        """Test tool message creation."""
        msg = Message(
            role="tool",
            content='{"result": "success"}',
            tool_call_id="call_123",
        )
        assert msg.role == "tool"
        assert msg.tool_call_id == "call_123"

    def test_multimodal_content(self, multimodal_message: Message) -> None:
        """Test message with multimodal content."""
        assert isinstance(multimodal_message.content, list)
        assert len(multimodal_message.content) == 2
        assert multimodal_message.content[0].type == "text"
        assert multimodal_message.content[1].type == "image_url"

    def test_message_with_tool_calls(self) -> None:
        """Test assistant message with tool calls."""
        msg = Message(
            role="assistant",
            content="",
            tool_calls=[
                ToolCall(id="call_1", name="Search", arguments={"q": "test"}),
                ToolCall(id="call_2", name="Calculate", arguments={"expr": "1+1"}),
            ],
        )
        assert msg.tool_calls is not None
        assert len(msg.tool_calls) == 2
        assert msg.tool_calls[0].name == "Search"

    def test_message_with_metadata(self, sample_metadata: MessageMetadata) -> None:
        """Test message with metadata."""
        msg = Message(
            role="assistant",
            content="Response",
            metadata=sample_metadata,
        )
        assert msg.metadata.cost == 0.002
        assert msg.metadata.model == "gpt-4o"

    def test_default_metadata(self) -> None:
        """Test that default metadata is created."""
        msg = Message(role="user", content="Hello!")
        assert isinstance(msg.metadata, MessageMetadata)
        assert msg.metadata.cost is None

    def test_json_serialization(self, sample_message: Message) -> None:
        """Test message can be serialized to JSON."""
        json_data = sample_message.model_dump(mode="json")
        assert isinstance(json_data["id"], str)
        assert json_data["role"] == "user"
        assert json_data["content"] == "Hello, world!"
        assert isinstance(json_data["created_at"], str)

    def test_json_round_trip(self, sample_message: Message) -> None:
        """Test message survives JSON round-trip."""
        json_data = sample_message.model_dump(mode="json")
        restored = Message.model_validate(json_data)
        assert restored.id == sample_message.id
        assert restored.role == sample_message.role
        assert restored.content == sample_message.content

    def test_invalid_role_rejected(self) -> None:
        """Test that invalid roles are rejected."""
        with pytest.raises(ValueError):
            Message(role="invalid", content="test")  # type: ignore[arg-type]
