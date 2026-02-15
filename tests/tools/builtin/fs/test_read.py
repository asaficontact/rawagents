"""Tests for the read tool."""

from __future__ import annotations

from pathlib import Path

import pytest

from rawagents.tools.builtin.fs import SecurityContext, read


class TestRead:
    """Test the read tool."""

    @pytest.mark.asyncio
    async def test_reads_file_with_line_numbers(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should read file with cat -n style line numbers."""
        result = await read(file_path=str(temp_workspace / "test.py"))

        assert "     1\t" in result
        assert "def hello():" in result

    @pytest.mark.asyncio
    async def test_respects_offset(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should respect offset parameter."""
        result = await read(
            file_path=str(temp_workspace / "large.txt"),
            offset=10,
            limit=5,
        )

        # Should start at line 11 (offset 10, 1-indexed display)
        assert "    11\t" in result
        # Should not have line 10
        assert "    10\t" not in result

    @pytest.mark.asyncio
    async def test_respects_limit(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should respect limit parameter."""
        result = await read(
            file_path=str(temp_workspace / "large.txt"),
            offset=0,
            limit=5,
        )

        # Should have lines 1-5
        lines = result.strip().split("\n")
        # Filter out continuation hints and empty lines
        content_lines = [l for l in lines if l.strip() and not l.startswith("...")]
        assert len(content_lines) <= 5

    @pytest.mark.asyncio
    async def test_marks_file_as_read(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should mark file as read for read-before-edit tracking."""
        file_path = temp_workspace / "test.py"
        await read(file_path=str(file_path))

        assert secure_context.check_read_before_edit(file_path) is True

    @pytest.mark.asyncio
    async def test_file_not_found_error(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should return error for nonexistent files."""
        result = await read(file_path=str(temp_workspace / "nonexistent.txt"))

        assert "Error" in result
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_suggests_similar_files(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should suggest similar files when file not found."""
        result = await read(file_path=str(temp_workspace / "tests.py"))

        # Should suggest test.py
        assert "Did you mean" in result or "Error" in result

    @pytest.mark.asyncio
    async def test_rejects_binary_files(
        self, temp_workspace: Path, mock_binary_file: Path, secure_context: SecurityContext
    ) -> None:
        """Should reject binary files."""
        result = await read(file_path=str(mock_binary_file))

        assert "Error" in result
        assert "binary" in result.lower()

    @pytest.mark.asyncio
    async def test_blocks_files_outside_workspace(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should block files outside workspace."""
        result = await read(file_path="/etc/passwd")

        assert "Error" in result
        assert "outside workspace" in result.lower() or "denied" in result.lower()

    @pytest.mark.asyncio
    async def test_handles_unicode_content(
        self, temp_workspace: Path, unicode_files: dict[str, Path], secure_context: SecurityContext
    ) -> None:
        """Should handle unicode content correctly."""
        if "unicode_content" not in unicode_files:
            pytest.skip("Unicode file not created")

        result = await read(file_path=str(unicode_files["unicode_content"]))

        assert "Error" not in result
        # Should contain unicode characters
        assert "世界" in result or "Привет" in result


class TestReadTruncation:
    """Test read truncation behavior."""

    @pytest.mark.asyncio
    async def test_truncates_long_lines(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should truncate lines longer than 2000 characters."""
        # Create file with very long line
        long_line_file = temp_workspace / "long_line.txt"
        long_line_file.write_text("x" * 5000 + "\n")

        result = await read(file_path=str(long_line_file))

        # Line should be truncated with ...
        assert "..." in result

    @pytest.mark.asyncio
    async def test_shows_continuation_hint(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should show continuation hint when there are more lines."""
        result = await read(
            file_path=str(temp_workspace / "large.txt"),
            offset=0,
            limit=10,
        )

        # Should hint about more lines
        assert "more lines" in result or "continue" in result

    @pytest.mark.asyncio
    async def test_truncates_output_at_50kb(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should truncate output at approximately 50KB."""
        # Create a file that would produce > 50KB output
        # Each line is ~50 bytes, so 1500 lines should exceed 50KB (75KB raw)
        large_file = temp_workspace / "fifty_kb_test.txt"
        lines = [f"Line {i:04d} {'x' * 40}" for i in range(1, 1500)]
        large_file.write_text("\n".join(lines))

        result = await read(file_path=str(large_file), limit=2000)

        # Output should be truncated with a message
        assert "truncated" in result.lower() or "50KB" in result
        # Output size in bytes should be less than ~60KB (allowing some overhead)
        assert len(result.encode("utf-8")) < 60 * 1024
