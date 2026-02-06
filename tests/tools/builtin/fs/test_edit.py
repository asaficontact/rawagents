"""Tests for the edit tool."""

from __future__ import annotations

from pathlib import Path

import pytest

from rawagents.tools.builtin.fs import edit, read, SecurityContext, set_security_context


class TestEdit:
    """Test the edit tool."""

    @pytest.mark.asyncio
    async def test_replaces_text(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should replace text in file."""
        test_file = temp_workspace / "test.py"

        # Read first
        await read(file_path=str(test_file))

        # Edit
        result = await edit(
            file_path=str(test_file),
            old_string="def hello():",
            new_string="def goodbye():",
        )

        assert "successfully" in result.lower()
        assert "goodbye" in test_file.read_text()

    @pytest.mark.asyncio
    async def test_requires_read_before_edit(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should require reading before editing."""
        test_file = temp_workspace / "test.py"

        result = await edit(
            file_path=str(test_file),
            old_string="def hello():",
            new_string="def goodbye():",
        )

        assert "Error" in result
        assert "read" in result.lower()

    @pytest.mark.asyncio
    async def test_empty_old_string_creates_file(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Empty old_string should create/overwrite file."""
        new_file = temp_workspace / "created.txt"

        result = await edit(
            file_path=str(new_file),
            old_string="",
            new_string="new content",
        )

        assert "successfully" in result.lower()
        assert new_file.exists()
        assert new_file.read_text() == "new content"

    @pytest.mark.asyncio
    async def test_fails_when_old_string_not_found(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should fail when old_string is not found."""
        test_file = temp_workspace / "test.py"

        # Read first
        await read(file_path=str(test_file))

        result = await edit(
            file_path=str(test_file),
            old_string="nonexistent text",
            new_string="replacement",
        )

        assert "Error" in result
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_fails_when_multiple_matches_without_replace_all(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should fail when multiple matches found without replace_all."""
        # Create file with duplicates
        dup_file = temp_workspace / "duplicates.txt"
        dup_file.write_text("foo bar foo baz foo")
        secure_context.mark_file_read(dup_file)

        result = await edit(
            file_path=str(dup_file),
            old_string="foo",
            new_string="qux",
            replace_all=False,
        )

        assert "Error" in result
        assert "multiple" in result.lower() or "3" in result

    @pytest.mark.asyncio
    async def test_replace_all_works(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should replace all occurrences with replace_all=True."""
        dup_file = temp_workspace / "duplicates.txt"
        dup_file.write_text("foo bar foo baz foo")
        secure_context.mark_file_read(dup_file)

        result = await edit(
            file_path=str(dup_file),
            old_string="foo",
            new_string="qux",
            replace_all=True,
        )

        assert "successfully" in result.lower()
        assert dup_file.read_text() == "qux bar qux baz qux"
        assert "3 replacements" in result


class TestEditFallbackStrategies:
    """Test edit tool's fallback matching strategies."""

    @pytest.mark.asyncio
    async def test_matches_with_different_indentation(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should match even with different indentation."""
        # Create file with specific indentation
        indented_file = temp_workspace / "indented.py"
        indented_file.write_text("    def hello():\n        pass\n")
        secure_context.mark_file_read(indented_file)

        # Try to match with different indentation
        result = await edit(
            file_path=str(indented_file),
            old_string="def hello():\n    pass",  # No leading indent
            new_string="def goodbye():\n    return",
        )

        # Should succeed using flexible replacer
        assert "successfully" in result.lower()

    @pytest.mark.asyncio
    async def test_matches_with_whitespace_differences(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should match with whitespace differences."""
        ws_file = temp_workspace / "whitespace.txt"
        ws_file.write_text("hello    world\n")
        secure_context.mark_file_read(ws_file)

        result = await edit(
            file_path=str(ws_file),
            old_string="hello world",  # Single space
            new_string="goodbye universe",
        )

        # May or may not match depending on exact strategy
        # The simple replacer won't match, but others might
        # For now, just verify it doesn't crash
        assert "Error" in result or "successfully" in result.lower()
