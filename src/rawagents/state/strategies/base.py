"""Base strategy protocol for context selection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol


if TYPE_CHECKING:
    from rawagents.state.types import Message


class BaseStrategy(Protocol):
    """Context selection strategy protocol.

    Strategies determine which messages from the full conversation
    history are sent to the LLM. This enables context management
    without modifying the underlying storage.

    Note:
        Strategies must be pure functions operating only on the
        message list. They must NOT access the Conversation object
        or Storage backend directly.

    Example:
        >>> class TokenLimitedStrategy:
        ...     def __init__(self, max_tokens: int):
        ...         self.max_tokens = max_tokens
        ...
        ...     def select_messages(self, messages: list[Message]) -> list[Message]:
        ...         # Return messages that fit within token budget
        ...         pass
    """

    def select_messages(self, messages: list[Message]) -> list[Message]:
        """Select which messages to include in the LLM context.

        Args:
            messages: Full list of conversation messages.

        Returns:
            Filtered/selected list of messages for the LLM.
        """
        ...
