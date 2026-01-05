"""Tests for conversation storage backends."""

import copy

import pytest

from rawagents.state import Message
from rawagents.state.storage.memory import InMemoryStorage


class TestInMemoryStorage:
    """Tests for InMemoryStorage."""

    def test_empty_storage(self, in_memory_storage: InMemoryStorage) -> None:
        """Test newly created storage is empty."""
        assert in_memory_storage.get_messages() == []
        assert len(in_memory_storage) == 0

    def test_save_message(self, in_memory_storage: InMemoryStorage) -> None:
        """Test saving a message."""
        msg = Message(role="user", content="Hello!")
        in_memory_storage.save_message(msg)
        messages = in_memory_storage.get_messages()
        assert len(messages) == 1
        assert messages[0].id == msg.id

    def test_save_multiple_messages(self, in_memory_storage: InMemoryStorage) -> None:
        """Test saving multiple messages preserves order."""
        msg1 = Message(role="user", content="First")
        msg2 = Message(role="assistant", content="Second")
        msg3 = Message(role="user", content="Third")

        in_memory_storage.save_message(msg1)
        in_memory_storage.save_message(msg2)
        in_memory_storage.save_message(msg3)

        messages = in_memory_storage.get_messages()
        assert len(messages) == 3
        assert messages[0].content == "First"
        assert messages[1].content == "Second"
        assert messages[2].content == "Third"

    def test_get_messages_returns_copy(self, in_memory_storage: InMemoryStorage) -> None:
        """Test that get_messages returns a copy, not the internal list."""
        msg = Message(role="user", content="Hello!")
        in_memory_storage.save_message(msg)

        messages1 = in_memory_storage.get_messages()
        messages2 = in_memory_storage.get_messages()

        # Modify one list
        messages1.append(Message(role="user", content="Extra"))

        # Other list should be unaffected
        assert len(messages2) == 1

    def test_delete_after(self, in_memory_storage: InMemoryStorage) -> None:
        """Test delete_after removes subsequent messages."""
        msg1 = Message(role="user", content="Keep")
        msg2 = Message(role="assistant", content="Delete this")
        msg3 = Message(role="user", content="Delete this too")

        in_memory_storage.save_message(msg1)
        in_memory_storage.save_message(msg2)
        in_memory_storage.save_message(msg3)

        in_memory_storage.delete_after(msg1.id)

        messages = in_memory_storage.get_messages()
        assert len(messages) == 1
        assert messages[0].id == msg1.id

    def test_delete_after_keeps_target_message(
        self, in_memory_storage: InMemoryStorage
    ) -> None:
        """Test that delete_after keeps the target message."""
        msg1 = Message(role="user", content="First")
        msg2 = Message(role="assistant", content="Target")
        msg3 = Message(role="user", content="Third")

        in_memory_storage.save_message(msg1)
        in_memory_storage.save_message(msg2)
        in_memory_storage.save_message(msg3)

        in_memory_storage.delete_after(msg2.id)

        messages = in_memory_storage.get_messages()
        assert len(messages) == 2
        assert messages[1].id == msg2.id

    def test_delete_after_unknown_id(self, in_memory_storage: InMemoryStorage) -> None:
        """Test delete_after raises ValueError for unknown ID."""
        msg = Message(role="user", content="Hello!")
        in_memory_storage.save_message(msg)

        with pytest.raises(ValueError, match="not found"):
            in_memory_storage.delete_after("nonexistent_id")

    def test_delete_after_empty_storage(
        self, in_memory_storage: InMemoryStorage
    ) -> None:
        """Test delete_after raises ValueError on empty storage."""
        with pytest.raises(ValueError, match="not found"):
            in_memory_storage.delete_after("any_id")

    def test_clear(self, in_memory_storage: InMemoryStorage) -> None:
        """Test clear removes all messages."""
        in_memory_storage.save_message(Message(role="user", content="1"))
        in_memory_storage.save_message(Message(role="user", content="2"))
        in_memory_storage.save_message(Message(role="user", content="3"))

        in_memory_storage.clear()

        assert in_memory_storage.get_messages() == []
        assert len(in_memory_storage) == 0

    def test_len(self, in_memory_storage: InMemoryStorage) -> None:
        """Test __len__ returns correct count."""
        assert len(in_memory_storage) == 0

        in_memory_storage.save_message(Message(role="user", content="1"))
        assert len(in_memory_storage) == 1

        in_memory_storage.save_message(Message(role="user", content="2"))
        assert len(in_memory_storage) == 2

    def test_deepcopy(self, in_memory_storage: InMemoryStorage) -> None:
        """Test deep copy creates independent storage."""
        msg1 = Message(role="user", content="Original")
        in_memory_storage.save_message(msg1)

        copied = copy.deepcopy(in_memory_storage)

        # Add message to original
        in_memory_storage.save_message(Message(role="user", content="New"))

        # Copy should not have the new message
        assert len(in_memory_storage) == 2
        assert len(copied) == 1

    def test_deepcopy_messages_are_independent(
        self, in_memory_storage: InMemoryStorage
    ) -> None:
        """Test that deep copied messages are independent objects."""
        msg = Message(role="user", content="Original")
        in_memory_storage.save_message(msg)

        copied = copy.deepcopy(in_memory_storage)

        # Messages should have same content
        original_msg = in_memory_storage.get_messages()[0]
        copied_msg = copied.get_messages()[0]
        assert original_msg.id == copied_msg.id
        assert original_msg.content == copied_msg.content

        # But be different objects (for mutable metadata)
        assert original_msg is not copied_msg
