"""Tests for the grep tool."""

from __future__ import annotations

from pathlib import Path

import pytest

from rawagents.tools.builtin.fs import SecurityContext, grep


class TestGrep:
    """Test the grep tool."""

    @pytest.mark.asyncio
    async def test_finds_matching_lines(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should find lines matching pattern."""
        result = await grep(pattern="def.*hello", path=str(temp_workspace))

        assert "def hello" in result
        assert "Found" in result

    @pytest.mark.asyncio
    async def test_shows_line_numbers(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should show line numbers for matches."""
        result = await grep(pattern="hello", path=str(temp_workspace))

        assert "Line" in result

    @pytest.mark.asyncio
    async def test_groups_by_file(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should group matches by file."""
        result = await grep(pattern="pass|class", path=str(temp_workspace))

        # Should show file paths
        assert ".py:" in result or "test.py" in result

    @pytest.mark.asyncio
    async def test_respects_include_filter(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should respect include file pattern filter."""
        # Create a non-Python file with matching content
        txt_file = temp_workspace / "readme.txt"
        txt_file.write_text("def hello\n")

        result = await grep(
            pattern="def",
            path=str(temp_workspace),
            include="*.py",
        )

        # Should find in .py files but not in .txt
        assert "readme.txt" not in result

    @pytest.mark.asyncio
    async def test_returns_no_files_message(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should return 'No files found' when no matches."""
        result = await grep(pattern="xyznonexistent123", path=str(temp_workspace))

        assert "No files found" in result

    @pytest.mark.asyncio
    async def test_validates_regex_pattern(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should validate regex pattern."""
        result = await grep(pattern="[invalid(regex", path=str(temp_workspace))

        assert "Error" in result
        assert "regex" in result.lower() or "pattern" in result.lower()

    @pytest.mark.asyncio
    async def test_requires_pattern(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should require pattern parameter."""
        result = await grep(pattern="", path=str(temp_workspace))

        assert "Error" in result
        assert "required" in result.lower()

    @pytest.mark.asyncio
    async def test_blocks_search_outside_workspace(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should block searching outside workspace."""
        result = await grep(pattern="root", path="/etc")

        assert "Error" in result

    @pytest.mark.asyncio
    async def test_truncates_long_lines(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should truncate long matching lines."""
        # Create file with very long line
        long_file = temp_workspace / "long.txt"
        long_file.write_text("match_here " + "x" * 5000 + "\n")

        result = await grep(pattern="match_here", path=str(temp_workspace))

        # Line should be truncated
        assert "..." in result or len(result) < 6000


class TestGrepTruncation:
    """Test grep truncation behavior."""

    @pytest.mark.asyncio
    async def test_truncates_at_100_matches(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should truncate at MAX_MATCHES (100)."""
        # Create a file with 150 matching lines
        many_matches = temp_workspace / "many_matches.txt"
        lines = [f"MATCH_PATTERN line {i}" for i in range(150)]
        many_matches.write_text("\n".join(lines))

        result = await grep(pattern="MATCH_PATTERN", path=str(temp_workspace))

        # Should indicate truncation
        assert "truncated" in result.lower()
        # Should mention 100 matches or limiting
        assert "Found 100 matches" in result or "100" in result


class TestGrepStructuredOutput:
    """Test grep structured JSON output."""

    @pytest.mark.asyncio
    async def test_returns_json_when_structured(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should return JSON when structured=True."""
        import json

        result = await grep(
            pattern="def.*hello",
            path=str(temp_workspace),
            structured=True,
        )

        data = json.loads(result)
        assert "count" in data
        assert "truncated" in data
        assert "files" in data
        assert data["count"] >= 1

    @pytest.mark.asyncio
    async def test_structured_no_matches(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should return JSON with empty files when no matches."""
        import json

        result = await grep(
            pattern="xyznonexistent123",
            path=str(temp_workspace),
            structured=True,
        )

        data = json.loads(result)
        assert data["count"] == 0
        assert data["files"] == {}

    @pytest.mark.asyncio
    async def test_structured_groups_by_file(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should group results by file in JSON output."""
        import json

        result = await grep(
            pattern="pass|class",
            path=str(temp_workspace),
            structured=True,
        )

        data = json.loads(result)
        # Should have file paths as keys
        assert isinstance(data["files"], dict)
        # Each file should have list of matches
        for file_path, matches in data["files"].items():
            assert isinstance(matches, list)
            for match in matches:
                assert "line" in match
                assert "text" in match
