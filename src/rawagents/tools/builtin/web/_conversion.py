"""HTML to Markdown/Text conversion.

Uses markdownify (Python equivalent of Turndown.js used by Claude Code and OpenCode).
"""

from __future__ import annotations

from typing import Literal


__all__ = ["convert_html_to_format"]


# BUG FIX #4: Plain def (not async def) — no I/O inside.
def convert_html_to_format(
    html: str,
    format: Literal["markdown", "text", "html"],
) -> str:
    """Convert HTML to the desired format."""
    if format == "html":
        return html

    if format == "markdown":
        from markdownify import markdownify as md  # noqa: PLC0415

        content = md(
            html,
            heading_style="ATX",
            strip=["script", "style", "meta", "link"],
        )
        return content.strip()

    if format == "text":
        import html as html_module  # noqa: PLC0415
        import re  # noqa: PLC0415

        text = re.sub(
            r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE
        )
        text = re.sub(
            r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE
        )
        text = re.sub(r"<[^>]+>", "", text)
        text = html_module.unescape(text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    raise ValueError(f"Unknown format: {format}")
