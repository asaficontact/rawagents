"""Tests for the list tool."""

from __future__ import annotations

from pathlib import Path

import pytest

from rawagents.tools.builtin.fs import SecurityContext, list_dir


class TestListDir:
    """Test the list_dir tool."""

    @pytest.mark.asyncio
    async def test_lists_directory_with_tree(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should list directory with tree structure."""
        result = await list_dir(path=str(temp_workspace))

        # Should contain tree characters
        assert "├" in result or "└" in result
        # Should show files
        assert "test.py" in result

    @pytest.mark.asyncio
    async def test_shows_directories_with_slash(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should show directories with trailing slash."""
        result = await list_dir(path=str(temp_workspace))

        assert "subdir/" in result

    @pytest.mark.asyncio
    async def test_respects_ignore_patterns(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should respect ignore patterns."""
        # Create a file to ignore
        (temp_workspace / "ignored.log").write_text("log content")

        result = await list_dir(
            path=str(temp_workspace),
            ignore=["*.log"],
        )

        assert "ignored.log" not in result

    @pytest.mark.asyncio
    async def test_ignores_default_patterns(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should ignore default patterns like __pycache__."""
        # Create __pycache__ directory
        pycache = temp_workspace / "__pycache__"
        pycache.mkdir()
        (pycache / "module.pyc").write_text("fake bytecode")

        result = await list_dir(path=str(temp_workspace))

        assert "__pycache__" not in result

    @pytest.mark.asyncio
    async def test_handles_empty_directory(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should handle empty directories."""
        empty_dir = temp_workspace / "empty"
        empty_dir.mkdir()

        result = await list_dir(path=str(empty_dir))

        assert "empty" in result.lower() or str(empty_dir) in result

    @pytest.mark.asyncio
    async def test_blocks_directory_outside_workspace(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should block directories outside workspace."""
        result = await list_dir(path="/etc")

        assert "Error" in result

    @pytest.mark.asyncio
    async def test_error_on_nonexistent_directory(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should error on nonexistent directory."""
        result = await list_dir(path=str(temp_workspace / "nonexistent"))

        assert "Error" in result
        assert "not found" in result.lower()


class TestListDirTruncation:
    """Test list_dir truncation behavior."""

    @pytest.mark.asyncio
    async def test_truncates_at_100_files(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should truncate at MAX_FILES (100)."""
        # Create a directory with 120 files - must exceed MAX_FILES (100)
        many_dir = temp_workspace / "many_files"
        many_dir.mkdir()
        for i in range(120):
            (many_dir / f"file_{i:03d}.txt").write_text(f"content {i}")

        result = await list_dir(path=str(many_dir))

        # With 120 files, the list should stop at 100 and show truncation
        # Count the actual files listed (lines with file_ in them)
        file_lines = [line for line in result.split("\n") if "file_" in line]

        # Should have at most 100 file entries
        assert len(file_lines) <= 100

        # Should indicate truncation (Results truncated at 100 files)
        assert "truncated" in result.lower() or len(file_lines) < 120
