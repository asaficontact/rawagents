"""Window-based context selection strategies."""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from rawagents.state.types import Message


class FullHistory:
    """Return all messages (identity strategy).

    This is the default strategy that passes through all messages
    without any filtering. Use when context length is not a concern.

    Example:
        >>> strategy = FullHistory()
        >>> selected = strategy.select_messages(messages)
        >>> len(selected) == len(messages)
        True
    """

    def select_messages(self, messages: list[Message]) -> list[Message]:
        """Return all messages unchanged.

        Args:
            messages: Full list of conversation messages.

        Returns:
            The same list of messages (identity operation).
        """
        return messages


class SlidingWindow:
    """Return system messages plus the last N non-system messages.

    Preserves all system prompts while limiting the conversation
    history to the most recent exchanges. Useful for long-running
    conversations where full history would exceed context limits.

    Attributes:
        window_size: Number of non-system messages to keep.

    Example:
        >>> strategy = SlidingWindow(window_size=5)
        >>> # With 100 messages (1 system + 99 user/assistant)
        >>> selected = strategy.select_messages(messages)
        >>> # Returns: 1 system + last 5 non-system = 6 messages
    """

    def __init__(self, window_size: int = 10) -> None:
        """Initialize with window size.

        Args:
            window_size: Number of non-system messages to include.
                Must be at least 1.

        Raises:
            ValueError: If window_size is less than 1.
        """
        if window_size < 1:
            raise ValueError("window_size must be >= 1")
        self.window_size = window_size

    def select_messages(self, messages: list[Message]) -> list[Message]:
        """Select system messages plus last N non-system messages.

        Args:
            messages: Full list of conversation messages.

        Returns:
            System messages followed by the last window_size
            non-system messages, preserving chronological order.
        """
        if not messages:
            return []

        # Separate system messages from others
        system_msgs = [m for m in messages if m.role == "system"]
        non_system = [m for m in messages if m.role != "system"]

        # Take last window_size non-system messages
        windowed = non_system[-self.window_size :]

        return system_msgs + windowed
