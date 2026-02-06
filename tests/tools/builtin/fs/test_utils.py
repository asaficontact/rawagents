"""Tests for file system utilities."""

from __future__ import annotations

from pathlib import Path

import pytest

from rawagents.tools.builtin.fs._utils import (
    detect_binary,
    format_cat_n,
    get_file_mtime,
    is_media_file,
    suggest_similar_files,
    truncate_line,
)


class TestFormatCatN:
    """Test cat -n style formatting."""

    def test_basic_formatting(self) -> None:
        """Basic lines should be formatted with numbers."""
        lines = ["def hello():", "    pass"]
        result = format_cat_n(lines)

        assert "     1\tdef hello():\n" in result
        assert "     2\t    pass\n" in result

    def test_custom_start_line(self) -> None:
        """Start line should be configurable."""
        lines = ["line one", "line two"]
        result = format_cat_n(lines, start_line=100)

        assert "   100\t" in result
        assert "   101\t" in result

    def test_handles_empty_lines(self) -> None:
        """Empty lines should be formatted."""
        lines = ["first", "", "third"]
        result = format_cat_n(lines)

        assert "     1\tfirst\n" in result
        assert "     2\t\n" in result
        assert "     3\tthird\n" in result

    def test_truncates_long_lines(self) -> None:
        """Long lines should be truncated."""
        long_line = "x" * 3000
        result = format_cat_n([long_line], max_line_length=100)

        assert "..." in result
        assert len(result.split("\t")[1].strip()) < 200

    def test_preserves_indentation(self) -> None:
        """Indentation should be preserved."""
        lines = ["def foo():", "    if True:", "        pass"]
        result = format_cat_n(lines)

        assert "    if True:" in result
        assert "        pass" in result

    def test_handles_lines_with_newlines(self) -> None:
        """Lines already ending with newlines should work."""
        lines = ["line1\n", "line2\n"]
        result = format_cat_n(lines)

        # Should not have double newlines
        assert "\n\n" not in result
        assert result.count("\n") == 2


class TestTruncateLine:
    """Test line truncation."""

    def test_no_truncation_for_short_lines(self) -> None:
        """Short lines should not be truncated."""
        line = "short line"
        result = truncate_line(line, max_length=100)
        assert result == line

    def test_truncates_long_lines(self) -> None:
        """Long lines should be truncated with ellipsis."""
        line = "a" * 100
        result = truncate_line(line, max_length=50)

        assert len(result) == 53  # 50 + "..."
        assert result.endswith("...")

    def test_exact_length_not_truncated(self) -> None:
        """Lines exactly at limit should not be truncated."""
        line = "a" * 100
        result = truncate_line(line, max_length=100)
        assert result == line


class TestDetectBinary:
    """Test binary file detection."""

    def test_detects_null_bytes(self, temp_workspace: Path) -> None:
        """Files with null bytes should be detected as binary."""
        binary_file = temp_workspace / "null.bin"
        binary_file.write_bytes(b"hello\x00world")

        assert detect_binary(binary_file) is True

    def test_detects_high_non_printable_ratio(self, temp_workspace: Path) -> None:
        """Files with many non-printable chars should be binary."""
        binary_file = temp_workspace / "nonprint.bin"
        # More than 30% non-printable
        content = bytes(range(256))
        binary_file.write_bytes(content)

        assert detect_binary(binary_file) is True

    def test_text_files_not_binary(self, temp_workspace: Path) -> None:
        """Normal text files should not be detected as binary."""
        text_file = temp_workspace / "text.txt"
        text_file.write_text("Hello, world!\nThis is text.\n")

        assert detect_binary(text_file) is False

    def test_empty_file_not_binary(self, temp_workspace: Path) -> None:
        """Empty files should not be binary."""
        empty_file = temp_workspace / "empty.txt"
        empty_file.write_text("")

        assert detect_binary(empty_file) is False


class TestSuggestSimilarFiles:
    """Test similar file suggestions."""

    def test_finds_similar_names(self, temp_workspace: Path) -> None:
        """Should suggest files with similar names."""
        # temp_workspace has test.py
        suggestions = suggest_similar_files("tests.py", temp_workspace)

        assert "test.py" in suggestions

    def test_case_insensitive(self, temp_workspace: Path) -> None:
        """Search should be case insensitive."""
        # Create a file with different case
        (temp_workspace / "MainFile.py").write_text("# main")

        suggestions = suggest_similar_files("mainfile.py", temp_workspace)
        assert "MainFile.py" in suggestions

    def test_limits_suggestions(self, temp_workspace: Path) -> None:
        """Should not return more than max suggestions."""
        # Create many similar files
        for i in range(10):
            (temp_workspace / f"file{i}.txt").write_text(f"file {i}")

        suggestions = suggest_similar_files("file.txt", temp_workspace, max_suggestions=3)
        assert len(suggestions) <= 3

    def test_empty_for_no_matches(self, temp_workspace: Path) -> None:
        """Should return empty list when no similar files exist."""
        suggestions = suggest_similar_files("xyz123.abc", temp_workspace)
        assert suggestions == []

    def test_handles_nonexistent_directory(self) -> None:
        """Should handle nonexistent directories gracefully."""
        suggestions = suggest_similar_files("test.py", Path("/nonexistent/path"))
        assert suggestions == []


class TestGetFileMtime:
    """Test file modification time retrieval."""

    def test_returns_mtime(self, temp_workspace: Path) -> None:
        """Should return modification time."""
        test_file = temp_workspace / "test.py"
        mtime = get_file_mtime(test_file)

        assert mtime > 0

    def test_returns_zero_for_nonexistent(self) -> None:
        """Should return 0 for nonexistent files."""
        mtime = get_file_mtime(Path("/nonexistent/file.txt"))
        assert mtime == 0.0


class TestIsMediaFile:
    """Test media file detection."""

    @pytest.mark.parametrize(
        "filename,expected",
        [
            ("image.png", True),
            ("photo.jpg", True),
            ("picture.jpeg", True),
            ("animation.gif", True),
            ("image.webp", True),
            ("document.pdf", True),
            ("vector.svg", False),  # SVG is text
            ("code.py", False),
            ("readme.txt", False),
            ("data.json", False),
        ],
    )
    def test_media_detection(
        self, temp_workspace: Path, filename: str, expected: bool
    ) -> None:
        """Various file types should be correctly identified."""
        file_path = temp_workspace / filename
        file_path.write_bytes(b"fake content")

        assert is_media_file(file_path) == expected
