"""Shared utilities for file system tools.

This module provides common functions used across multiple tools:
- Output formatting (cat -n style)
- File type detection
- Similar file suggestions
- Line truncation
"""

from __future__ import annotations

import asyncio
import difflib
import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING, Iterable


if TYPE_CHECKING:
    from rawagents.tools.builtin.fs._security import SecurityContext

__all__ = [
    "format_cat_n",
    "truncate_line",
    "suggest_similar_files",
    "get_file_mtime",
    "is_media_file",
    "detect_binary",
    "validate_path_or_error",
    "require_read_before_edit",
    "safe_read_text",
    "aread_text",
    "awrite_text",
    "amkdir",
    "aunlink",
    "aexists",
    "async_safe_read_text",
]


def format_cat_n(
    lines: Iterable[str],
    start_line: int = 1,
    max_line_length: int = 2000,
) -> str:
    """Format lines in cat -n style with right-aligned line numbers.

    Output format:
        "     1\\tFirst line\\n"
        "     2\\tSecond line\\n"

    The line number is right-aligned in a 6-character field,
    followed by a tab character, then the line content.

    Args:
        lines: Iterable of line strings (may or may not have newlines).
        start_line: The starting line number (1-indexed).
        max_line_length: Maximum length per line before truncation.

    Returns:
        Formatted string with line numbers.

    Example:
        >>> format_cat_n(["def hello():", "    pass"])
        '     1\\tdef hello():\\n     2\\t    pass\\n'
    """
    output_parts: list[str] = []

    for i, line in enumerate(lines):
        line_num = start_line + i

        # Ensure line ends with newline (strip existing to avoid double)
        line = line.rstrip("\n\r")

        # Truncate long lines
        if len(line) > max_line_length:
            line = line[:max_line_length] + "..."

        # Format: 6-char right-aligned number, tab, content, newline
        output_parts.append(f"{line_num:>6}\t{line}\n")

    return "".join(output_parts)


def truncate_line(line: str, max_length: int = 2000) -> str:
    """Truncate a line if it exceeds the maximum length.

    Args:
        line: The line to truncate.
        max_length: Maximum allowed length.

    Returns:
        Original line if within limit, truncated with "..." otherwise.
    """
    if len(line) <= max_length:
        return line
    return line[:max_length] + "..."


def detect_binary(path: Path, sample_size: int = 8192) -> bool:
    """Detect if a file is binary by sampling its contents.

    A file is considered binary if it contains:
    - Null bytes (\\x00)
    - More than 30% non-printable characters

    Args:
        path: Path to the file to check.
        sample_size: Number of bytes to sample.

    Returns:
        True if the file appears to be binary.
    """
    try:
        with open(path, "rb") as f:
            chunk = f.read(sample_size)
            if not chunk:
                return False

            # Null bytes indicate binary
            if b"\x00" in chunk:
                return True

            # Check ratio of non-printable bytes
            # Text characters: printable ASCII + common control chars
            text_chars = bytearray(
                {7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7F}
            )
            non_text = sum(1 for b in chunk if b not in text_chars)
            return non_text / len(chunk) > 0.30

    except (IOError, OSError):
        return False


def suggest_similar_files(
    target_name: str,
    parent_dir: Path,
    max_suggestions: int = 3,
    cutoff: float = 0.4,
) -> list[str]:
    """Suggest similar filenames when a file is not found.

    Uses difflib's SequenceMatcher for case-insensitive similarity.

    Args:
        target_name: The filename that was not found.
        parent_dir: The directory to search for similar files.
        max_suggestions: Maximum number of suggestions to return.
        cutoff: Minimum similarity ratio (0-1) to include.

    Returns:
        List of similar filenames, sorted by similarity.

    Example:
        >>> suggest_similar_files("main.py", Path("./src"))
        ['Main.py', 'main.pyx', 'mian.py']
    """
    if not parent_dir.exists() or not parent_dir.is_dir():
        return []

    target_lower = target_name.lower()
    candidates: list[tuple[float, str]] = []

    try:
        for entry in parent_dir.iterdir():
            if entry.is_file():
                name = entry.name
                # Case-insensitive similarity
                ratio = difflib.SequenceMatcher(
                    None, target_lower, name.lower()
                ).ratio()
                if ratio >= cutoff:
                    candidates.append((ratio, name))
    except PermissionError:
        return []

    # Sort by similarity descending, take top N
    candidates.sort(key=lambda x: x[0], reverse=True)
    return [name for _, name in candidates[:max_suggestions]]


def get_file_mtime(path: Path) -> float:
    """Get the modification time of a file.

    Args:
        path: Path to the file.

    Returns:
        Modification time as a Unix timestamp, or 0 if unavailable.
    """
    try:
        return path.stat().st_mtime
    except (OSError, IOError):
        return 0.0


def is_media_file(path: Path) -> bool:
    """Check if a file is an image or PDF.

    Args:
        path: Path to check.

    Returns:
        True if the file is image/* (except SVG) or application/pdf.
    """
    mime_type, _ = mimetypes.guess_type(str(path))
    if mime_type is None:
        return False

    # Image (excluding SVG which is text-based)
    if mime_type.startswith("image/") and mime_type != "image/svg+xml":
        return True

    # PDF
    if mime_type == "application/pdf":
        return True

    return False


def validate_path_or_error(
    ctx: SecurityContext,
    path: str,
    *,
    check_exists: bool = True,
) -> tuple[Path | None, str | None]:
    """Validate a path, returning (resolved_path, None) or (None, error_string).

    Eliminates duplicated try/except blocks across tool files.

    Args:
        ctx: The security context.
        path: The path to validate.
        check_exists: Whether the file must exist.

    Returns:
        Tuple of (resolved_path, None) on success or (None, error_string) on failure.
    """
    from rawagents.tools.builtin.fs._security import WorkspaceSecurityError

    try:
        return ctx.validate_path(path, check_exists=check_exists), None
    except WorkspaceSecurityError as e:
        return None, f"Error: {e}"
    except FileNotFoundError:
        suggestions = suggest_similar_files(Path(path).name, Path(path).parent)
        hint = f" Did you mean: {', '.join(suggestions[:3])}?" if suggestions else ""
        return None, f"Error: File not found: {path}.{hint}"


def require_read_before_edit(
    ctx: SecurityContext,
    resolved_path: Path,
    display_path: str,
) -> str | None:
    """Check read-before-edit requirement.

    Returns error string if file wasn't read, None if OK.

    Args:
        ctx: The security context.
        resolved_path: The resolved path to check.
        display_path: The display path for error messages.

    Returns:
        Error string or None.
    """
    if not ctx.check_read_before_edit(resolved_path):
        return (
            f"Error: File '{display_path}' was not read in this session. "
            f"Please read the file first before editing it."
        )
    return None


def safe_read_text(path: Path) -> tuple[str | None, str | None]:
    """Read a file with UTF-8 -> latin-1 fallback.

    Returns (content, None) on success or (None, error_string) on failure.

    Args:
        path: The file to read.

    Returns:
        Tuple of (content, None) or (None, error_string).
    """
    try:
        return path.read_text(encoding="utf-8"), None
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="latin-1"), None
        except (UnicodeDecodeError, UnicodeError):
            return None, f"Error: Cannot decode file: {path}"


async def aread_text(path: Path, encoding: str = "utf-8") -> str:
    """Read file text in a thread pool to avoid blocking the event loop."""
    return await asyncio.to_thread(path.read_text, encoding=encoding)


async def awrite_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Write file text in a thread pool to avoid blocking the event loop."""
    await asyncio.to_thread(path.write_text, content, encoding=encoding)


async def amkdir(path: Path, parents: bool = False, exist_ok: bool = False) -> None:
    """Create directory in a thread pool to avoid blocking the event loop."""
    await asyncio.to_thread(path.mkdir, parents=parents, exist_ok=exist_ok)


async def aunlink(path: Path) -> None:
    """Delete file in a thread pool to avoid blocking the event loop."""
    await asyncio.to_thread(path.unlink)


async def aexists(path: Path) -> bool:
    """Check file existence in a thread pool to avoid blocking the event loop."""
    return await asyncio.to_thread(path.exists)


async def async_safe_read_text(path: Path) -> tuple[str | None, str | None]:
    """Async version of safe_read_text with UTF-8 -> latin-1 fallback.

    Returns (content, None) on success or (None, error_string) on failure.
    """
    try:
        return await aread_text(path, encoding="utf-8"), None
    except UnicodeDecodeError:
        try:
            return await aread_text(path, encoding="latin-1"), None
        except (UnicodeDecodeError, UnicodeError):
            return None, f"Error: Cannot decode file: {path}"



