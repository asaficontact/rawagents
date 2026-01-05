"""Canonical data models for the Conversation component."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from rawagents.utils.types import ToolCall

__all__ = [
    "ContentBlock",
    "Message",
    "MessageMetadata",
    "ToolCall",
]


class MessageMetadata(BaseModel):
    """Optimization metrics for a message.

    Tracks cost, latency, token usage, and model information for agent optimization.
    Fields align with LLMResponse from llm_client for seamless integration.

    Attributes:
        cost: USD cost of the API call that generated this message.
        latency_ms: Response time in milliseconds.
        finish_reason: Why the model stopped (e.g., "stop", "tool_calls").
        model: Model identifier that generated the response.
        usage: Token usage statistics (prompt_tokens, completion_tokens, total_tokens).
        reasoning_content: The model's reasoning/thinking text (for reasoning models).
            None if reasoning was not enabled or model doesn't support it.
        reasoning_blocks: Provider-specific reasoning blocks (e.g., Anthropic thinking_blocks).
            None if not available.
        custom: Arbitrary user-defined metadata.
    """

    cost: float | None = None
    latency_ms: float | None = None
    finish_reason: str | None = None
    model: str | None = None
    usage: dict[str, int] | None = None
    reasoning_content: str | None = None
    reasoning_blocks: list[dict[str, Any]] | None = None
    custom: dict[str, Any] = Field(default_factory=dict)


class ContentBlock(BaseModel):
    """Multimodal content block for text or images.

    Attributes:
        type: Content type - "text" or "image_url".
        text: Text content (when type="text").
        image_url: Image URL (when type="image_url").
    """

    type: Literal["text", "image_url"]
    text: str | None = None
    image_url: str | None = None


class Message(BaseModel):
    """Canonical message representation.

    Unified structure for all message types in a conversation.
    Supports text, multimodal content, tool calls, and tool results.

    Attributes:
        id: Unique message identifier (auto-generated UUID).
        role: Message role - "system", "user", "assistant", or "tool".
        content: Text string or list of ContentBlocks for multimodal.
        tool_calls: List of tool calls (assistant messages only).
        tool_call_id: ID of the tool call this message responds to (tool messages only).
        metadata: Optimization metrics (cost, latency, model).
        created_at: UTC timestamp of message creation.

    Example:
        >>> msg = Message(role="user", content="Hello!")
        >>> print(msg.id)  # Auto-generated UUID
        >>> print(msg.created_at)  # Auto-generated timestamp
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    role: Literal["system", "user", "assistant", "tool"]
    content: str | list[ContentBlock]
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    metadata: MessageMetadata = Field(default_factory=MessageMetadata)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
