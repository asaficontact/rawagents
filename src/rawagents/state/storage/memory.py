"""In-memory storage implementation."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from rawagents.state.types import Message


class InMemoryStorage:
    """In-memory message storage.

    Default storage backend that keeps messages in a Python list.
    Suitable for single-process applications, scripts, and testing.

    Note:
        Messages are lost when the process exits. For persistence,
        use snapshot/load or implement a persistent storage backend.

    Example:
        >>> storage = InMemoryStorage()
        >>> storage.save_message(Message(role="user", content="Hi"))
        >>> messages = storage.get_messages()
        >>> len(messages)
        1
    """

    def __init__(self) -> None:
        """Initialize empty storage."""
        self._messages: list[Message] = []

    def save_message(self, message: Message) -> None:
        """Append a message to storage.

        Args:
            message: The message to store.
        """
        self._messages.append(message)

    def get_messages(self) -> list[Message]:
        """Get all messages as a new list.

        Returns:
            Copy of the message list (modifications don't affect storage).
        """
        return list(self._messages)

    def delete_after(self, message_id: str) -> None:
        """Delete all messages after the specified ID.

        The message with the given ID is kept; all messages added
        after it are removed.

        Args:
            message_id: ID of the last message to keep.

        Raises:
            ValueError: If message_id is not found in storage.
        """
        for i, msg in enumerate(self._messages):
            if msg.id == message_id:
                self._messages = self._messages[: i + 1]
                return
        raise ValueError(f"Message '{message_id}' not found")

    def clear(self) -> None:
        """Remove all messages from storage."""
        self._messages.clear()

    def fork(self) -> InMemoryStorage:
        """Create an independent copy of the storage.

        Returns:
            New InMemoryStorage with deep-copied messages.
        """
        new = InMemoryStorage()
        # Deep copy messages to ensure immutability of the fork
        new._messages = [copy.deepcopy(m) for m in self._messages]
        return new

    def __len__(self) -> int:
        """Return the number of stored messages."""
        return len(self._messages)
