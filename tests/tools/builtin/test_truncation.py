"""Tests for the shared truncation module."""

from __future__ import annotations

from rawagents.tools.builtin._truncation import TruncationResult, truncate_output


class TestTruncateOutput:
    """Test the shared truncate_output() function."""

    def test_no_truncation_small_output(self) -> None:
        """Small output should not be truncated."""
        result = truncate_output("hello\nworld")
        assert result.was_truncated is False
        assert result.content == "hello\nworld"
        assert result.original_lines == 2
        assert result.lines_kept == 2

    def test_line_truncation(self) -> None:
        """Output exceeding max_lines should be truncated."""
        output = "\n".join(f"line {i}" for i in range(100))
        result = truncate_output(output, max_lines=10)
        assert result.was_truncated is True
        assert result.lines_kept == 10
        assert result.original_lines == 100
        assert "line 9" in result.content
        assert "line 10" not in result.content

    def test_byte_truncation(self) -> None:
        """Output exceeding max_bytes should be truncated."""
        output = "x" * 200 + "\n" + "y" * 200
        result = truncate_output(output, max_bytes=250)
        assert result.was_truncated is True
        assert len(result.content.encode("utf-8")) <= 250

    def test_dual_truncation_both_limits(self) -> None:
        """Both line and byte limits should apply."""
        # 500 lines, each ~100 chars
        output = "\n".join("a" * 100 for _ in range(500))
        result = truncate_output(output, max_lines=50, max_bytes=1024)
        assert result.was_truncated is True
        # Should respect both limits
        assert result.content.count("\n") < 500

    def test_empty_output(self) -> None:
        """Empty output should return empty result."""
        result = truncate_output("")
        assert result.was_truncated is False
        assert result.content == ""
        assert result.original_lines == 0
        assert result.lines_kept == 0

    def test_preserves_line_boundary(self) -> None:
        """Byte truncation should cut at line boundary."""
        output = "short\n" + "x" * 200
        result = truncate_output(output, max_bytes=50)
        assert result.was_truncated is True
        # Should cut at newline, keeping "short"
        assert result.content == "short"

    def test_truncation_result_metadata(self) -> None:
        """TruncationResult should have correct metadata."""
        output = "\n".join(f"line {i}" for i in range(50))
        result = truncate_output(output, max_lines=20)
        assert isinstance(result, TruncationResult)
        assert result.was_truncated is True
        assert result.original_lines == 50
        assert result.lines_kept == 20
