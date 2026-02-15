"""Tests for the glob tool."""

from __future__ import annotations

from pathlib import Path

import pytest

from rawagents.tools.builtin.fs import SecurityContext, glob


class TestGlob:
    """Test the glob tool."""

    @pytest.mark.asyncio
    async def test_finds_files_by_pattern(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should find files matching pattern."""
        result = await glob(pattern="**/*.py", path=str(temp_workspace))

        assert "test.py" in result
        assert "nested.py" in result

    @pytest.mark.asyncio
    async def test_returns_absolute_paths(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should return absolute paths."""
        result = await glob(pattern="*.py", path=str(temp_workspace))

        # Should contain absolute path
        assert str(temp_workspace) in result

    @pytest.mark.asyncio
    async def test_sorts_by_mtime(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should sort results by modification time (newest first)."""
        # Create files with different mtimes
        import time

        old_file = temp_workspace / "old.txt"
        old_file.write_text("old content")
        time.sleep(0.1)

        new_file = temp_workspace / "new.txt"
        new_file.write_text("new content")

        result = await glob(pattern="*.txt", path=str(temp_workspace))

        # new.txt should appear before old.txt
        new_pos = result.find("new.txt")
        old_pos = result.find("old.txt")

        if new_pos != -1 and old_pos != -1:
            assert new_pos < old_pos

    @pytest.mark.asyncio
    async def test_returns_no_files_message(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should return 'No files found' when no matches."""
        result = await glob(pattern="*.nonexistent", path=str(temp_workspace))

        assert "No files found" in result

    @pytest.mark.asyncio
    async def test_handles_recursive_pattern(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should handle ** recursive pattern."""
        result = await glob(pattern="**/*.py", path=str(temp_workspace))

        # Should find nested file
        assert "nested.py" in result

    @pytest.mark.asyncio
    async def test_blocks_search_outside_workspace(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should block searching outside workspace."""
        result = await glob(pattern="*", path="/etc")

        assert "Error" in result

    @pytest.mark.asyncio
    async def test_truncates_results(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should truncate results and show message."""
        # Create many files
        for i in range(150):
            (temp_workspace / f"file_{i:03d}.txt").write_text(f"content {i}")

        result = await glob(pattern="*.txt", path=str(temp_workspace))

        assert "truncated" in result.lower()


class TestGlobStructuredOutput:
    """Test glob structured JSON output."""

    @pytest.mark.asyncio
    async def test_returns_json_when_structured(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should return JSON when structured=True."""
        import json

        result = await glob(pattern="**/*.py", path=str(temp_workspace), structured=True)

        data = json.loads(result)
        assert "count" in data
        assert "truncated" in data
        assert "results" in data
        assert data["count"] >= 1  # At least test.py

    @pytest.mark.asyncio
    async def test_structured_no_matches(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should return JSON with empty results when no matches."""
        import json

        result = await glob(pattern="*.nonexistent", path=str(temp_workspace), structured=True)

        data = json.loads(result)
        assert data["count"] == 0
        assert data["truncated"] is False
        assert data["results"] == []

    @pytest.mark.asyncio
    async def test_structured_truncation_flag(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should set truncated=True in JSON when results exceed limit."""
        import json

        # Create many files
        for i in range(150):
            (temp_workspace / f"struct_file_{i:03d}.txt").write_text(f"content {i}")

        result = await glob(pattern="struct_file_*.txt", path=str(temp_workspace), structured=True)

        data = json.loads(result)
        assert data["truncated"] is True
        assert data["count"] == 100  # MAX_RESULTS limit
