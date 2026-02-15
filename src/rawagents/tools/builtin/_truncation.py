"""Shared output truncation for tools that produce large output.

Eliminates duplicated truncation logic across bash.py and read.py by providing
a single, consistent truncation function with metadata.
"""

from __future__ import annotations

from dataclasses import dataclass


__all__ = ["TruncationResult", "truncate_output"]


@dataclass
class TruncationResult:
    """Result of truncating output.

    Attributes:
        content: The (possibly truncated) output text.
        was_truncated: Whether any truncation was applied.
        lines_kept: Number of lines in the returned content.
        original_lines: Total number of lines in the original output.
    """

    content: str
    was_truncated: bool
    lines_kept: int
    original_lines: int


def truncate_output(
    output: str,
    *,
    max_lines: int = 2000,
    max_bytes: int = 50 * 1024,
) -> TruncationResult:
    """Truncate output by line count and/or byte size.

    Applies two-pass truncation:
    1. Line truncation — keep at most ``max_lines`` lines.
    2. Byte truncation — keep at most ``max_bytes`` bytes, cutting at
       the last newline boundary to avoid splitting a line.

    Args:
        output: The raw output string.
        max_lines: Maximum number of lines to keep.
        max_bytes: Maximum byte size to keep (UTF-8).

    Returns:
        TruncationResult with truncated content and metadata.
    """
    if not output:
        return TruncationResult(
            content="",
            was_truncated=False,
            lines_kept=0,
            original_lines=0,
        )

    lines = output.split("\n")
    original_lines = len(lines)
    truncated = False

    # Step 1: Line truncation
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        truncated = True

    result = "\n".join(lines)

    # Step 2: Byte truncation — cut at last newline boundary
    if len(result.encode("utf-8")) > max_bytes:
        result_bytes = result.encode("utf-8")[:max_bytes]
        last_newline = result_bytes.rfind(b"\n")
        if last_newline > 0:
            result = result_bytes[:last_newline].decode("utf-8", errors="replace")
        else:
            result = result_bytes.decode("utf-8", errors="replace")
        truncated = True

    lines_kept = result.count("\n") + 1 if result else 0

    return TruncationResult(
        content=result,
        was_truncated=truncated,
        lines_kept=lines_kept,
        original_lines=original_lines,
    )
