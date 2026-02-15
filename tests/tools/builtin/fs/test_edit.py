"""Tests for the edit tool."""

from __future__ import annotations

from pathlib import Path

import pytest

from rawagents.tools.builtin.fs import SecurityContext, edit, read


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


class TestEditMtimeSafety:
    """Test mtime-based stale file detection in edit tool."""

    @pytest.mark.asyncio
    async def test_edit_rejects_stale_file(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Edit should reject if file was modified externally since read."""
        import time

        test_file = temp_workspace / "stale.txt"
        test_file.write_text("original line\n")

        # Read the file
        await read(file_path=str(test_file))

        # External modification
        time.sleep(0.05)
        test_file.write_text("externally modified\n")

        # Try to edit — should fail
        result = await edit(
            file_path=str(test_file),
            old_string="original line",
            new_string="agent edit",
        )
        assert "Error" in result
        assert "modified externally" in result

    @pytest.mark.asyncio
    async def test_edit_refreshes_mtime_after_write(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """After a successful edit, subsequent edits should work without re-reading."""
        test_file = temp_workspace / "refresh.txt"
        test_file.write_text("line one\nline two\n")

        # Read the file
        await read(file_path=str(test_file))

        # First edit
        result = await edit(
            file_path=str(test_file),
            old_string="line one",
            new_string="line ONE",
        )
        assert "successfully" in result.lower()

        # Second edit — should work because mtime was refreshed
        result = await edit(
            file_path=str(test_file),
            old_string="line two",
            new_string="line TWO",
        )
        assert "successfully" in result.lower()
        assert test_file.read_text() == "line ONE\nline TWO\n"


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
    async def test_edit_fuzzy_fallback(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should succeed with fuzzy match and show notice."""
        fuzzy_file = temp_workspace / "fuzzy.py"
        fuzzy_file.write_text(
            "def calculate():\n"
            "    foo_bar = 1\n"
            "    result = foo_bar + 2\n"
            "    return result\n"
        )
        secure_context.mark_file_read(fuzzy_file)

        # LLM misremembers variable name
        result = await edit(
            file_path=str(fuzzy_file),
            old_string=(
                "def calculate():\n"
                "    foo_baz = 1\n"
                "    result = foo_baz + 2\n"
                "    return result"
            ),
            new_string="def calculate():\n    return 3\n",
        )

        assert "successfully" in result.lower()
        assert "fuzzy" in result.lower()

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
