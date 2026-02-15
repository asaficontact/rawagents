"""Tests for the write tool."""

from __future__ import annotations

from pathlib import Path

import pytest

from rawagents.tools.builtin.fs import (
    SecurityContext,
    read,
    set_security_context,
    write,
)


class TestWrite:
    """Test the write tool."""

    @pytest.mark.asyncio
    async def test_creates_new_file(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should create a new file."""
        new_file = temp_workspace / "new_file.txt"
        result = await write(file_path=str(new_file), content="Hello, World!")

        assert "successfully" in result.lower()
        assert new_file.exists()
        assert new_file.read_text() == "Hello, World!"

    @pytest.mark.asyncio
    async def test_creates_parent_directories(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should create parent directories if they don't exist."""
        nested_file = temp_workspace / "new" / "nested" / "file.txt"
        result = await write(file_path=str(nested_file), content="Nested content")

        assert "successfully" in result.lower()
        assert nested_file.exists()

    @pytest.mark.asyncio
    async def test_requires_read_before_overwrite(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should require reading before overwriting existing file."""
        existing_file = temp_workspace / "test.py"

        # Try to write without reading first
        result = await write(file_path=str(existing_file), content="new content")

        assert "Error" in result
        assert "read" in result.lower()

    @pytest.mark.asyncio
    async def test_allows_overwrite_after_read(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should allow overwriting after reading the file."""
        existing_file = temp_workspace / "test.py"

        # Read first
        await read(file_path=str(existing_file))

        # Now write should work
        result = await write(file_path=str(existing_file), content="new content")

        assert "successfully" in result.lower()
        assert existing_file.read_text() == "new content"

    @pytest.mark.asyncio
    async def test_blocks_files_outside_workspace(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should block writing outside workspace."""
        result = await write(file_path="/tmp/outside.txt", content="bad")

        assert "Error" in result

    @pytest.mark.asyncio
    async def test_handles_unicode_content(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should handle unicode content correctly."""
        unicode_file = temp_workspace / "unicode.txt"
        content = "Hello 世界 🌍"

        result = await write(file_path=str(unicode_file), content=content)

        assert "successfully" in result.lower()
        assert unicode_file.read_text(encoding="utf-8") == content

    @pytest.mark.asyncio
    async def test_write_rejects_stale_file(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Write should reject if file was modified externally since read."""
        import time

        existing_file = temp_workspace / "stale_write.txt"
        existing_file.write_text("original")

        # Read first
        await read(file_path=str(existing_file))

        # External modification
        time.sleep(0.05)
        existing_file.write_text("externally modified")

        # Try to overwrite — should fail
        result = await write(file_path=str(existing_file), content="agent content")
        assert "Error" in result
        assert "modified externally" in result

    @pytest.mark.asyncio
    async def test_rejects_oversized_content(
        self, temp_workspace: Path,
    ) -> None:
        """Should reject content that exceeds max_file_size."""
        ctx = SecurityContext(workspace=str(temp_workspace), max_file_size=100)
        set_security_context(ctx)

        new_file = temp_workspace / "big_file.txt"
        large_content = "x" * 200

        result = await write(file_path=str(new_file), content=large_content)

        assert "Error" in result
        assert "too large" in result.lower()
        assert not new_file.exists()
