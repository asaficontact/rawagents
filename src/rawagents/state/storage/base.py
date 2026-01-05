"""Base storage protocol for conversation persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Self


if TYPE_CHECKING:
    from rawagents.state.types import Message


class BaseStorage(Protocol):
    """Storage backend protocol for conversation messages.

    Defines the interface that all storage implementations must follow.
    Use InMemoryStorage for development/testing, or implement custom
    backends for Redis, PostgreSQL, etc.

    Example:
        >>> class RedisStorage:
        ...     def save_message(self, message: Message) -> None:
        ...         # Store in Redis
        ...         pass
        ...     def get_messages(self) -> list[Message]:
        ...         # Retrieve from Redis
        ...         pass
        ...     # ... implement other methods
    """

    def save_message(self, message: Message) -> None:
        """Persist a message to storage.

        Args:
            message: The message to store.
        """
        ...

    def get_messages(self) -> list[Message]:
        """Retrieve all messages in chronological order.

        Returns:
            List of all stored messages.
        """
        ...

    def delete_after(self, message_id: str) -> None:
        """Delete all messages after the specified message ID.

        Used for truncation/undo operations. The message with the
        given ID is kept; all subsequent messages are removed.

        Args:
            message_id: ID of the last message to keep.

        Raises:
            ValueError: If message_id is not found.
        """
        ...

    def clear(self) -> None:
        """Remove all messages from storage."""
        ...

    def fork(self) -> Self:
        """Create an independent copy of the storage.

        This is used when forking a conversation. The new storage
        must contain a copy of the current messages but be
        independent (changes to one don't affect the other).

        Returns:
            A new instance of the storage backend with copied state.
        """
        ...
