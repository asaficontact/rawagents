"""Tests for conversation branching, merging, and checkpointing."""

import pytest

from rawagents.state import Conversation, Message, ToolCall


class TestFork:
    """Tests for fork() method."""

    def test_fork_creates_independent_copy(
        self, sample_conversation: Conversation
    ) -> None:
        """Test that fork creates a truly independent copy."""
        branch = sample_conversation.fork()

        # Add to branch
        branch.add_user("Branch message")

        # Original should be unchanged
        assert len(sample_conversation) == 4
        assert len(branch) == 5

    def test_fork_copies_existing_messages(
        self, sample_conversation: Conversation
    ) -> None:
        """Test that fork copies all existing messages."""
        branch = sample_conversation.fork()

        original_msgs = sample_conversation.get_all_messages()
        branch_msgs = branch.get_all_messages()

        assert len(original_msgs) == len(branch_msgs)
        for orig, branched in zip(original_msgs, branch_msgs, strict=True):
            assert orig.id == branched.id
            assert orig.content == branched.content

    def test_fork_preserves_message_ids(
        self, sample_conversation: Conversation
    ) -> None:
        """Test that forked messages keep their original IDs."""
        original_ids = [m.id for m in sample_conversation.get_all_messages()]
        branch = sample_conversation.fork()
        branch_ids = [m.id for m in branch.get_all_messages()]

        assert original_ids == branch_ids

    def test_fork_messages_are_independent_objects(
        self, sample_conversation: Conversation
    ) -> None:
        """Test that forked messages are separate objects."""
        branch = sample_conversation.fork()

        original_msg = sample_conversation.get_all_messages()[0]
        branch_msg = branch.get_all_messages()[0]

        # Same content but different objects
        assert original_msg.id == branch_msg.id
        assert original_msg is not branch_msg

    def test_fork_empty_conversation(
        self, empty_conversation: Conversation
    ) -> None:
        """Test forking an empty conversation."""
        branch = empty_conversation.fork()
        assert len(branch) == 0
        branch.add_user("Hello")
        assert len(branch) == 1
        assert len(empty_conversation) == 0

    def test_multiple_forks(self, sample_conversation: Conversation) -> None:
        """Test creating multiple independent forks."""
        branch1 = sample_conversation.fork()
        branch2 = sample_conversation.fork()

        branch1.add_user("Branch 1")
        branch2.add_user("Branch 2 message")
        branch2.add_assistant("Branch 2 response")

        assert len(sample_conversation) == 4
        assert len(branch1) == 5
        assert len(branch2) == 6


class TestMerge:
    """Tests for merge() method."""

    def test_merge_adds_new_messages(self, sample_conversation: Conversation) -> None:
        """Test that merge adds new messages from branch."""
        branch = sample_conversation.fork()
        branch.add_user("New from branch")
        branch.add_assistant("Response from branch")

        sample_conversation.merge(branch)

        assert len(sample_conversation) == 6
        messages = sample_conversation.get_all_messages()
        assert messages[-2].content == "New from branch"
        assert messages[-1].content == "Response from branch"

    def test_merge_skips_existing_messages(
        self, sample_conversation: Conversation
    ) -> None:
        """Test that merge doesn't duplicate existing messages."""
        original_len = len(sample_conversation)
        branch = sample_conversation.fork()
        # Don't add anything to branch

        sample_conversation.merge(branch)

        assert len(sample_conversation) == original_len

    def test_merge_uses_message_ids(self, sample_conversation: Conversation) -> None:
        """Test that merge identifies messages by ID."""
        branch = sample_conversation.fork()
        new_msg = branch.add_user("New message")
        original_new_id = new_msg.id

        sample_conversation.merge(branch)

        # The merged message should have the same ID
        messages = sample_conversation.get_all_messages()
        assert messages[-1].id == original_new_id

    def test_merge_empty_branch(self, sample_conversation: Conversation) -> None:
        """Test merging an empty branch (branch from parent's state)."""
        branch = sample_conversation.fork()
        original_len = len(sample_conversation)

        sample_conversation.merge(branch)

        assert len(sample_conversation) == original_len

    def test_merge_into_empty_conversation(
        self, empty_conversation: Conversation
    ) -> None:
        """Test merging into an empty conversation."""
        branch = Conversation()
        branch.add_system("System")
        branch.add_user("User")

        empty_conversation.merge(branch)

        assert len(empty_conversation) == 2


class TestTruncate:
    """Tests for truncate() method."""

    def test_truncate_removes_after_id(
        self, sample_conversation: Conversation
    ) -> None:
        """Test that truncate removes messages after the given ID."""
        messages = sample_conversation.get_all_messages()
        keep_id = messages[1].id  # Keep system + first user message

        sample_conversation.truncate(keep_id)

        assert len(sample_conversation) == 2
        remaining = sample_conversation.get_all_messages()
        assert remaining[-1].id == keep_id

    def test_truncate_keeps_target_message(
        self, sample_conversation: Conversation
    ) -> None:
        """Test that truncate keeps the target message."""
        messages = sample_conversation.get_all_messages()
        target = messages[2]  # The assistant response

        sample_conversation.truncate(target.id)

        remaining = sample_conversation.get_all_messages()
        assert remaining[-1].id == target.id
        assert remaining[-1].content == target.content

    def test_truncate_at_last_message(
        self, sample_conversation: Conversation
    ) -> None:
        """Test truncate at the last message (no-op for messages)."""
        messages = sample_conversation.get_all_messages()
        last_id = messages[-1].id
        original_len = len(sample_conversation)

        sample_conversation.truncate(last_id)

        assert len(sample_conversation) == original_len

    def test_truncate_unknown_id_raises(
        self, sample_conversation: Conversation
    ) -> None:
        """Test that truncate raises ValueError for unknown ID."""
        with pytest.raises(ValueError, match="not found"):
            sample_conversation.truncate("nonexistent_id")

    def test_truncate_empty_conversation_raises(
        self, empty_conversation: Conversation
    ) -> None:
        """Test that truncate raises on empty conversation."""
        with pytest.raises(ValueError, match="not found"):
            empty_conversation.truncate("any_id")

    def test_truncate_enables_undo(self, sample_conversation: Conversation) -> None:
        """Test using truncate for undo functionality."""
        # Remember state before new message
        messages = sample_conversation.get_all_messages()
        last_good_id = messages[-1].id

        # Add a "mistake"
        sample_conversation.add_user("Wrong question")
        sample_conversation.add_assistant("Wrong answer")
        assert len(sample_conversation) == 6

        # Undo
        sample_conversation.truncate(last_good_id)
        assert len(sample_conversation) == 4


class TestSnapshot:
    """Tests for snapshot() method."""

    def test_snapshot_returns_dict(self, sample_conversation: Conversation) -> None:
        """Test that snapshot returns a dictionary."""
        snapshot = sample_conversation.snapshot()
        assert isinstance(snapshot, dict)

    def test_snapshot_contains_messages(
        self, sample_conversation: Conversation
    ) -> None:
        """Test that snapshot contains messages."""
        snapshot = sample_conversation.snapshot()
        assert "messages" in snapshot
        assert len(snapshot["messages"]) == 4

    def test_snapshot_messages_are_serializable(
        self, sample_conversation: Conversation
    ) -> None:
        """Test that snapshot messages are JSON-serializable dicts."""
        snapshot = sample_conversation.snapshot()
        for msg_data in snapshot["messages"]:
            assert isinstance(msg_data, dict)
            assert "id" in msg_data
            assert "role" in msg_data
            assert "content" in msg_data

    def test_snapshot_contains_strategy_name(
        self, sample_conversation: Conversation
    ) -> None:
        """Test that snapshot contains strategy class name."""
        snapshot = sample_conversation.snapshot()
        assert "strategy" in snapshot
        assert snapshot["strategy"] == "FullHistory"

    def test_snapshot_empty_conversation(
        self, empty_conversation: Conversation
    ) -> None:
        """Test snapshot of empty conversation."""
        snapshot = empty_conversation.snapshot()
        assert snapshot["messages"] == []


class TestLoad:
    """Tests for load() method."""

    def test_load_restores_messages(
        self, sample_conversation: Conversation, empty_conversation: Conversation
    ) -> None:
        """Test that load restores messages."""
        snapshot = sample_conversation.snapshot()

        empty_conversation.load(snapshot)

        assert len(empty_conversation) == 4
        messages = empty_conversation.get_all_messages()
        assert messages[0].role == "system"

    def test_load_replaces_existing_messages(
        self, sample_conversation: Conversation
    ) -> None:
        """Test that load replaces existing content."""
        # Create a new conversation with different content
        new_conv = Conversation()
        new_conv.add_system("Different system")
        new_conv.add_user("Different user")

        # Load from sample_conversation
        snapshot = sample_conversation.snapshot()
        new_conv.load(snapshot)

        assert len(new_conv) == 4
        assert new_conv.get_all_messages()[0].content == "You are a helpful assistant."

    def test_load_preserves_message_ids(
        self, sample_conversation: Conversation
    ) -> None:
        """Test that load preserves original message IDs."""
        original_ids = [m.id for m in sample_conversation.get_all_messages()]
        snapshot = sample_conversation.snapshot()

        new_conv = Conversation()
        new_conv.load(snapshot)

        loaded_ids = [m.id for m in new_conv.get_all_messages()]
        assert original_ids == loaded_ids

    def test_snapshot_load_roundtrip(
        self, sample_conversation: Conversation
    ) -> None:
        """Test complete snapshot/load roundtrip."""
        # Snapshot
        snapshot = sample_conversation.snapshot()

        # Load into new conversation
        restored = Conversation()
        restored.load(snapshot)

        # Compare
        original_msgs = sample_conversation.get_all_messages()
        restored_msgs = restored.get_all_messages()

        assert len(original_msgs) == len(restored_msgs)
        for orig, rest in zip(original_msgs, restored_msgs, strict=True):
            assert orig.id == rest.id
            assert orig.role == rest.role
            assert orig.content == rest.content

    def test_load_with_tool_calls(
        self, conversation_with_tools: Conversation
    ) -> None:
        """Test load preserves tool calls."""
        snapshot = conversation_with_tools.snapshot()

        restored = Conversation()
        restored.load(snapshot)

        # Find the assistant message with tool calls
        messages = restored.get_all_messages()
        tool_call_msg = next(m for m in messages if m.tool_calls)

        assert tool_call_msg.tool_calls is not None
        assert len(tool_call_msg.tool_calls) == 1
        assert tool_call_msg.tool_calls[0].name == "GetWeather"

    def test_load_empty_snapshot(self, sample_conversation: Conversation) -> None:
        """Test loading empty snapshot clears conversation."""
        empty_snapshot = {"messages": [], "strategy": "FullHistory"}

        sample_conversation.load(empty_snapshot)

        assert len(sample_conversation) == 0


class TestBranchingWorkflow:
    """Integration tests for complete branching workflows."""

    def test_tree_of_thoughts_workflow(self) -> None:
        """Test a tree-of-thoughts style workflow."""
        main = Conversation()
        main.add_system("You are a problem solver.")
        main.add_user("Solve P=NP")

        # Create exploration branches
        branch_a = main.fork()
        branch_b = main.fork()
        branch_c = main.fork()

        # Each branch explores different approach
        branch_a.add_assistant("Approach A: Try reduction...")
        branch_b.add_assistant("Approach B: Try approximation...")
        branch_c.add_assistant("Approach C: Try heuristics...")

        # Main is unchanged
        assert len(main) == 2

        # Branches are independent
        assert len(branch_a) == 3
        assert len(branch_b) == 3
        assert len(branch_c) == 3

        # Pick winner and merge
        main.merge(branch_b)
        assert len(main) == 3
        assert main.get_all_messages()[-1].content == "Approach B: Try approximation..."

    def test_retry_workflow(self) -> None:
        """Test a retry workflow using truncate."""
        conv = Conversation()
        conv.add_system("You are helpful.")
        user_msg = conv.add_user("What's 2+2?")
        conv.add_assistant("The answer is 5.")  # Wrong answer

        # Retry by truncating back to user message
        conv.truncate(user_msg.id)
        conv.add_assistant("The answer is 4.")  # Correct answer

        assert len(conv) == 3
        assert conv.get_all_messages()[-1].content == "The answer is 4."

    def test_checkpoint_resume_workflow(self) -> None:
        """Test a checkpoint and resume workflow."""
        # Initial session
        conv1 = Conversation()
        conv1.add_system("You are helpful.")
        conv1.add_user("Hello")
        conv1.add_assistant("Hi!")

        # Save state (simulate persisting to DB)
        saved_state = conv1.snapshot()

        # Later: Resume session
        conv2 = Conversation()
        conv2.load(saved_state)

        # Continue conversation
        conv2.add_user("How are you?")
        conv2.add_assistant("I'm doing well!")

        assert len(conv2) == 5
        assert conv2.get_all_messages()[-1].content == "I'm doing well!"
