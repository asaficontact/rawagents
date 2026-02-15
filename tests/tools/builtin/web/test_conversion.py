"""Tests for HTML to markdown/text conversion."""

from __future__ import annotations

import pytest

from rawagents.tools.builtin.web._conversion import convert_html_to_format


class TestHTMLConversion:
    """Test HTML conversion to various formats."""

    async def test_html_to_markdown(self) -> None:
        """HTML should convert to markdown with ATX headings."""
        html = "<h1>Title</h1><p>Hello <strong>world</strong></p>"
        result = convert_html_to_format(html, "markdown")
        assert "# Title" in result
        assert "**world**" in result

    async def test_html_to_text(self) -> None:
        """HTML should convert to plain text with tags stripped."""
        html = "<h1>Title</h1><p>Hello <strong>world</strong></p>"
        result = convert_html_to_format(html, "text")
        assert "<" not in result
        assert "Title" in result
        assert "world" in result

    async def test_html_passthrough(self) -> None:
        """HTML format should return the input unchanged."""
        html = "<h1>Title</h1><p>Content</p>"
        result = convert_html_to_format(html, "html")
        assert result == html

    async def test_strip_scripts_and_styles(self) -> None:
        """Script and style tags should be stripped in text mode."""
        html = (
            "<html><head><style>body{}</style></head>"
            "<body><script>alert('x')</script><p>Safe</p></body></html>"
        )
        result = convert_html_to_format(html, "text")
        assert "alert" not in result
        assert "body{}" not in result
        assert "Safe" in result

    async def test_collapse_whitespace(self) -> None:
        """Multiple whitespace should be collapsed in text mode."""
        html = "<p>Hello    world</p>  <p>  Test  </p>"
        result = convert_html_to_format(html, "text")
        # Should not have multiple consecutive spaces
        assert "    " not in result

    async def test_unknown_format_raises(self) -> None:
        """Unknown format should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown format"):
            convert_html_to_format("<p>test</p>", "xml")  # type: ignore[arg-type]

    async def test_empty_html(self) -> None:
        """Empty string input should return empty string."""
        result = convert_html_to_format("", "markdown")
        assert result == ""
