"""Tests for conversation context strategies."""

import pytest

from rawagents.state import FullHistory, Message, SlidingWindow


class TestFullHistory:
    """Tests for FullHistory strategy."""

    def test_empty_list(self, full_history_strategy: FullHistory) -> None:
        """Test with empty message list."""
        result = full_history_strategy.select_messages([])
        assert result == []

    def test_returns_all_messages(self, full_history_strategy: FullHistory) -> None:
        """Test that all messages are returned."""
        messages = [
            Message(role="system", content="System"),
            Message(role="user", content="User 1"),
            Message(role="assistant", content="Assistant 1"),
            Message(role="user", content="User 2"),
        ]

        result = full_history_strategy.select_messages(messages)

        assert len(result) == 4
        assert result == messages

    def test_returns_same_list_reference(
        self, full_history_strategy: FullHistory
    ) -> None:
        """Test that the same list is returned (identity)."""
        messages = [Message(role="user", content="Hello")]
        result = full_history_strategy.select_messages(messages)
        assert result is messages


class TestSlidingWindow:
    """Tests for SlidingWindow strategy."""

    def test_init_default_window_size(self) -> None:
        """Test default window size."""
        strategy = SlidingWindow()
        assert strategy.window_size == 10

    def test_init_custom_window_size(self) -> None:
        """Test custom window size."""
        strategy = SlidingWindow(window_size=5)
        assert strategy.window_size == 5

    def test_init_window_size_validation(self) -> None:
        """Test that window_size must be >= 1."""
        with pytest.raises(ValueError, match="window_size must be >= 1"):
            SlidingWindow(window_size=0)

        with pytest.raises(ValueError, match="window_size must be >= 1"):
            SlidingWindow(window_size=-1)

    def test_empty_list(self, sliding_window_strategy: SlidingWindow) -> None:
        """Test with empty message list."""
        result = sliding_window_strategy.select_messages([])
        assert result == []

    def test_preserves_system_messages(
        self, sliding_window_strategy: SlidingWindow
    ) -> None:
        """Test that system messages are always included."""
        messages = [
            Message(role="system", content="System 1"),
            Message(role="system", content="System 2"),
            Message(role="user", content="User 1"),
            Message(role="assistant", content="Assistant 1"),
            Message(role="user", content="User 2"),
            Message(role="assistant", content="Assistant 2"),
            Message(role="user", content="User 3"),
            Message(role="assistant", content="Assistant 3"),
        ]

        # window_size=3, so should get: 2 system + last 3 non-system
        # Non-system messages in order: User 1, Assistant 1, User 2, Assistant 2, User 3, Assistant 3
        # Last 3: Assistant 2, User 3, Assistant 3
        result = sliding_window_strategy.select_messages(messages)

        assert len(result) == 5  # 2 system + 3 windowed
        assert result[0].content == "System 1"
        assert result[1].content == "System 2"
        assert result[2].content == "Assistant 2"
        assert result[3].content == "User 3"
        assert result[4].content == "Assistant 3"

    def test_fewer_messages_than_window(self) -> None:
        """Test when there are fewer messages than window size."""
        strategy = SlidingWindow(window_size=10)
        messages = [
            Message(role="system", content="System"),
            Message(role="user", content="User"),
        ]

        result = strategy.select_messages(messages)

        # All messages should be returned
        assert len(result) == 2

    def test_only_system_messages(
        self, sliding_window_strategy: SlidingWindow
    ) -> None:
        """Test with only system messages."""
        messages = [
            Message(role="system", content="System 1"),
            Message(role="system", content="System 2"),
        ]

        result = sliding_window_strategy.select_messages(messages)

        # Only system messages returned (no non-system to window)
        assert len(result) == 2

    def test_no_system_messages(self, sliding_window_strategy: SlidingWindow) -> None:
        """Test with no system messages."""
        messages = [
            Message(role="user", content="User 1"),
            Message(role="assistant", content="Assistant 1"),
            Message(role="user", content="User 2"),
            Message(role="assistant", content="Assistant 2"),
            Message(role="user", content="User 3"),
        ]

        # window_size=3, last 3 non-system: User 2, Assistant 2, User 3
        result = sliding_window_strategy.select_messages(messages)

        assert len(result) == 3
        assert result[0].content == "User 2"
        assert result[1].content == "Assistant 2"
        assert result[2].content == "User 3"

    def test_exact_window_size(self) -> None:
        """Test when non-system messages exactly match window size."""
        strategy = SlidingWindow(window_size=3)
        messages = [
            Message(role="system", content="System"),
            Message(role="user", content="User 1"),
            Message(role="assistant", content="Assistant 1"),
            Message(role="user", content="User 2"),
        ]

        result = strategy.select_messages(messages)

        # System + all 3 non-system
        assert len(result) == 4

    def test_window_size_one(self) -> None:
        """Test with window_size=1."""
        strategy = SlidingWindow(window_size=1)
        messages = [
            Message(role="system", content="System"),
            Message(role="user", content="User 1"),
            Message(role="assistant", content="Assistant"),
            Message(role="user", content="User 2"),
        ]

        result = strategy.select_messages(messages)

        # System + last 1 non-system
        assert len(result) == 2
        assert result[0].content == "System"
        assert result[1].content == "User 2"

    def test_preserves_message_order(
        self, sliding_window_strategy: SlidingWindow
    ) -> None:
        """Test that message order is preserved (system first, then chronological)."""
        messages = [
            Message(role="user", content="User 1"),
            Message(role="system", content="System"),  # System not at start
            Message(role="assistant", content="Assistant 1"),
            Message(role="user", content="User 2"),
            Message(role="assistant", content="Assistant 2"),
        ]

        result = sliding_window_strategy.select_messages(messages)

        # System messages first, then windowed non-system
        assert result[0].content == "System"
        # Last 3 non-system in original order
        assert result[1].content == "Assistant 1"
        assert result[2].content == "User 2"
        assert result[3].content == "Assistant 2"
