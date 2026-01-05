"""Main Conversation class for agent memory and state management."""

from __future__ import annotations

import json
from typing import Any

from rawagents.state.storage.base import BaseStorage
from rawagents.state.storage.memory import InMemoryStorage
from rawagents.state.strategies.base import BaseStrategy
from rawagents.state.strategies.window import FullHistory
from rawagents.state.types import (
    ContentBlock,
    Message,
    MessageMetadata,
    ToolCall,
)


class Conversation:
    """Smart container for agent memory and state.

    The Conversation component is the "operating system for context",
    managing the timeline of messages, tool calls, and structured outputs
    between a user and an LLM.

    Features:
        - Canonical Data Model: Strongly-typed Pydantic models
        - Branching Support: fork() for tree-of-thought reasoning
        - State Checkpointing: snapshot()/load() for pause/resume
        - Context Strategies: Pluggable logic for context selection
        - Storage Agnosticism: Swappable storage backends

    Core Principle:
        "State before Execution" - This component manages state (what happened).
        The LLM manages execution (what to do next). They are distinct
        but interoperable.

    Attributes:
        _storage: The storage backend (default: InMemoryStorage).
        _strategy: The context selection strategy (default: FullHistory).

    Example:
        >>> conv = Conversation()
        >>> conv.add_system("You are a helpful assistant.")
        >>> conv.add_user("Hello!")
        >>> messages = conv.get_history()  # For LLM API
        >>> # Use with LLM:
        >>> # response = client.complete(messages=messages)
    """

    def __init__(
        self,
        storage: BaseStorage | None = None,
        strategy: BaseStrategy | None = None,
    ) -> None:
        """Initialize a new conversation.

        Args:
            storage: Storage backend for message persistence.
                Defaults to InMemoryStorage.
            strategy: Context selection strategy for get_history().
                Defaults to FullHistory.
        """
        self._storage: BaseStorage = storage or InMemoryStorage()
        self._strategy: BaseStrategy = strategy or FullHistory()

    # === Message Addition ===

    def add_system(self, content: str) -> Message:
        """Add a system message.

        Args:
            content: The system prompt text.

        Returns:
            The created Message object.
        """
        msg = Message(role="system", content=content)
        self._storage.save_message(msg)
        return msg

    def add_user(
        self,
        content: str,
        images: list[str] | None = None,
    ) -> Message:
        """Add a user message, optionally with images.

        Args:
            content: The user's text message.
            images: Optional list of image URLs for multimodal input.

        Returns:
            The created Message object.

        Example:
            >>> conv.add_user("What's in this image?", images=["https://..."])
        """
        if images:
            blocks: list[ContentBlock] = [ContentBlock(type="text", text=content)]
            blocks.extend(
                ContentBlock(type="image_url", image_url=url) for url in images
            )
            msg = Message(role="user", content=blocks)
        else:
            msg = Message(role="user", content=content)
        self._storage.save_message(msg)
        return msg

    def add_assistant(
        self,
        content: str,
        tool_calls: list[ToolCall] | list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | MessageMetadata | None = None,
    ) -> Message:
        """Add an assistant message with optional tool calls and metrics.

        Args:
            content: The assistant's response text.
            tool_calls: Optional list of tool calls requested by the assistant.
                Can be ToolCall objects or dicts.
            metadata: Optimization metrics (cost, latency, model).
                Can be a dict or MessageMetadata instance.

        Returns:
            The created Message object.

        Example:
            >>> conv.add_assistant(
            ...     content="Hello!",
            ...     metadata={"cost": 0.002, "latency_ms": 450, "model": "gpt-4o"}
            ... )
        """
        if isinstance(metadata, dict):
            meta = MessageMetadata(**metadata)
        else:
            meta = metadata or MessageMetadata()

        # Handle tool calls conversion if necessary
        final_tool_calls: list[ToolCall] | None = None
        if tool_calls:
            final_tool_calls = []
            for tc in tool_calls:
                if isinstance(tc, dict):
                    final_tool_calls.append(ToolCall(**tc))
                else:
                    final_tool_calls.append(tc)

        msg = Message(
            role="assistant",
            content=content,
            tool_calls=final_tool_calls,
            metadata=meta,
        )
        self._storage.save_message(msg)
        return msg

    def add_tool_result(
        self,
        tool_call_id: str,
        content: str,
        metadata: dict[str, Any] | MessageMetadata | None = None,
    ) -> Message:
        """Add a tool result message.

        Args:
            tool_call_id: ID of the tool call this result responds to.
            content: The tool's output (typically JSON string).
            metadata: Optional metadata for the tool execution.

        Returns:
            The created Message object.

        Example:
            >>> conv.add_tool_result(
            ...     tool_call_id="call_abc123",
            ...     content='{"temperature": 72, "unit": "F"}'
            ... )
        """
        if isinstance(metadata, dict):
            meta = MessageMetadata(**metadata)
        else:
            meta = metadata or MessageMetadata()

        msg = Message(
            role="tool",
            content=content,
            tool_call_id=tool_call_id,
            metadata=meta,
        )
        self._storage.save_message(msg)
        return msg

    # === Retrieval ===

    def get_history(self) -> list[dict[str, Any]]:
        """Get filtered history as dicts for LLM API.

        Applies the active context strategy (e.g., sliding window)
        and formats messages for direct use with LLM providers.

        Returns:
            List of OpenAI-compatible message dicts.

        Example:
            >>> messages = conv.get_history()
            >>> response = client.complete(messages=messages)
        """
        messages = self._strategy.select_messages(self._storage.get_messages())
        return [self._message_to_dict(m) for m in messages]

    def get_all_messages(self) -> list[Message]:
        """Get all raw Message objects (no strategy filtering).

        Use this when you need access to metadata, timestamps,
        or other fields not included in the LLM-formatted output.

        Returns:
            List of all Message objects in chronological order.
        """
        return self._storage.get_messages()

    def _message_to_dict(self, msg: Message) -> dict[str, Any]:
        """Convert Message to OpenAI-compatible dict.

        Args:
            msg: The Message to convert.

        Returns:
            Dict suitable for LLM API calls.
        """
        d: dict[str, Any] = {"role": msg.role}

        # Handle content
        if isinstance(msg.content, str):
            d["content"] = msg.content
        else:
            d["content"] = [
                block.model_dump(exclude_none=True) for block in msg.content
            ]

        # Handle tool calls (assistant messages)
        if msg.tool_calls:
            d["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": (
                            json.dumps(tc.arguments)
                            if isinstance(tc.arguments, dict)
                            else tc.arguments
                        ),
                    },
                }
                for tc in msg.tool_calls
            ]

        # Handle tool result (tool messages)
        if msg.tool_call_id:
            d["tool_call_id"] = msg.tool_call_id

        return d

    # === Branching ===

    def fork(self) -> Conversation:
        """Create an independent copy for exploration.

        Creates a deep copy of the conversation history. If the storage
        backend supports efficient forking (like InMemoryStorage), it
        will use that. Otherwise, it may fall back to creating a new
        InMemoryStorage with the current messages.

        Returns:
            New Conversation instance with copied state.

        Example:
            >>> branch = conv.fork()
            >>> branch.add_user("Try approach A")
            >>> # Original conv is unchanged
        """
        # Use the storage's fork method to create a copy of the backend
        # We assume strict strict typing in BaseStorage ensures fork() exists
        new_storage = self._storage.fork()
        return Conversation(storage=new_storage, strategy=self._strategy)

    def merge(self, branch: Conversation) -> None:
        """Append new messages from a branch to this conversation.

        Only messages not already in this conversation are added.
        Messages are identified by their unique ID.

        Args:
            branch: The branch conversation to merge from.

        Example:
            >>> branch = conv.fork()
            >>> branch.add_user("New message")
            >>> conv.merge(branch)  # "New message" added to conv
        """
        current_ids = {m.id for m in self._storage.get_messages()}
        for msg in branch._storage.get_messages():
            if msg.id not in current_ids:
                self._storage.save_message(msg)

    def truncate(self, message_id: str) -> None:
        """Remove all messages after the specified ID (undo).

        The message with the given ID is kept; all messages
        added after it are removed. Use for "undo" or "retry" flows.

        Args:
            message_id: ID of the last message to keep.

        Raises:
            ValueError: If message_id is not found.

        Example:
            >>> msg = conv.add_user("Wrong question")
            >>> conv.truncate(prev_msg.id)  # Remove "Wrong question"
        """
        self._storage.delete_after(message_id)

    # === Checkpointing ===

    def snapshot(self) -> dict[str, Any]:
        """Export full state to a dictionary.

        Creates a serializable snapshot of the conversation state
        for persistence or transfer. Use with load() to restore.

        Warning:
            The 'custom' field in MessageMetadata must contain only
            JSON-serializable types. If you store complex objects
            (classes, datetime, etc.) in metadata.custom, this method
            may fail or produce non-serializable output.

        Returns:
            Dict containing all conversation state.

        Example:
            >>> state = conv.snapshot()
            >>> db.save(session_id, state)
        """
        return {
            "messages": [
                m.model_dump(mode="json") for m in self._storage.get_messages()
            ],
            "strategy": type(self._strategy).__name__,
        }

    def load(self, snapshot: dict[str, Any]) -> None:
        """Restore state from a snapshot.

        Replaces current state with the snapshot contents.
        The strategy is preserved (not restored from snapshot).

        Args:
            snapshot: Dict from a previous snapshot() call.

        Example:
            >>> state = db.load(session_id)
            >>> conv = Conversation()
            >>> conv.load(state)
        """
        self._storage.clear()
        for msg_data in snapshot["messages"]:
            msg = Message.model_validate(msg_data)
            self._storage.save_message(msg)

    # === Utility ===

    def __len__(self) -> int:
        """Return the number of messages in the conversation."""
        return len(self._storage.get_messages())

    def clear(self) -> None:
        """Remove all messages from the conversation."""
        self._storage.clear()
