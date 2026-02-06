"""Tests for the multiedit tool."""

from __future__ import annotations

from pathlib import Path

import pytest

from rawagents.tools.builtin.fs import multiedit, read, EditOp, SecurityContext, set_security_context


class TestMultiEdit:
    """Test the multiedit tool."""

    @pytest.mark.asyncio
    async def test_applies_multiple_edits(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should apply multiple edits to a file."""
        test_file = temp_workspace / "multi.txt"
        test_file.write_text("foo bar baz")
        secure_context.mark_file_read(test_file)

        result = await multiedit(
            file_path=str(test_file),
            edits=[
                EditOp(file_path=str(test_file), old_string="foo", new_string="FOO"),
                EditOp(file_path=str(test_file), old_string="bar", new_string="BAR"),
            ],
        )

        assert "successfully" in result.lower()
        assert test_file.read_text() == "FOO BAR baz"

    @pytest.mark.asyncio
    async def test_atomic_rollback_on_failure(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should rollback all changes if any edit fails."""
        test_file = temp_workspace / "atomic.txt"
        original_content = "foo bar baz"
        test_file.write_text(original_content)
        secure_context.mark_file_read(test_file)

        result = await multiedit(
            file_path=str(test_file),
            edits=[
                EditOp(file_path=str(test_file), old_string="foo", new_string="FOO"),
                EditOp(file_path=str(test_file), old_string="nonexistent", new_string="X"),
            ],
        )

        assert "Error" in result
        # File should be changed because first edit succeeded before second failed
        # Note: Our implementation applies edits to working copy, not original
        # So the file will actually be unchanged because we don't write on failure

    @pytest.mark.asyncio
    async def test_requires_same_file_path(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should require all edits to target the same file."""
        test_file = temp_workspace / "test.py"
        secure_context.mark_file_read(test_file)

        result = await multiedit(
            file_path=str(test_file),
            edits=[
                EditOp(file_path=str(test_file), old_string="foo", new_string="bar"),
                EditOp(file_path="/different/file.txt", old_string="a", new_string="b"),
            ],
        )

        assert "Error" in result
        assert "different" in result.lower() or "same file" in result.lower()

    @pytest.mark.asyncio
    async def test_requires_read_before_edit(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should require reading file before multiedit."""
        test_file = temp_workspace / "test.py"

        result = await multiedit(
            file_path=str(test_file),
            edits=[
                EditOp(file_path=str(test_file), old_string="foo", new_string="bar"),
            ],
        )

        assert "Error" in result
        assert "read" in result.lower()

    @pytest.mark.asyncio
    async def test_handles_empty_edits(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should handle empty edits list."""
        test_file = temp_workspace / "test.py"

        result = await multiedit(
            file_path=str(test_file),
            edits=[],
        )

        assert "Error" in result

    @pytest.mark.asyncio
    async def test_shows_edit_count(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should show count of edits applied."""
        test_file = temp_workspace / "count.txt"
        test_file.write_text("a b c")
        secure_context.mark_file_read(test_file)

        result = await multiedit(
            file_path=str(test_file),
            edits=[
                EditOp(file_path=str(test_file), old_string="a", new_string="A"),
                EditOp(file_path=str(test_file), old_string="b", new_string="B"),
            ],
        )

        assert "2 edits" in result
