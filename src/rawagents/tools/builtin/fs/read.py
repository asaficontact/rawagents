"""Read tool for reading file contents.

Implements the OpenCode-compatible read tool with:
- Line numbers in cat -n format
- Offset/limit pagination for large files
- Binary and media file detection
- Security validation via SecurityContext
"""

from __future__ import annotations

import asyncio
import base64
import mimetypes
from pathlib import Path
from typing import Annotated

from rawagents.tools import tool
from rawagents.tools.builtin.fs._security import (
    WorkspaceSecurityError,
    get_security_context,
)
from rawagents.tools.builtin.fs._utils import (
    async_safe_read_text,
    format_cat_n,
    validate_path_or_error,
)


__all__ = ["read"]

# Constants
MAX_OUTPUT_BYTES = 50 * 1024  # 50KB output limit
DEFAULT_LINE_LIMIT = 2000
MAX_LINE_LENGTH = 2000

# Threshold for using streaming reader (10MB)
STREAMING_THRESHOLD = 10 * 1024 * 1024


@tool
async def read(
    file_path: Annotated[str, "The absolute path to the file to read"],
    offset: Annotated[int, "Line number to start reading from (0-indexed)"] = 0,
    limit: Annotated[int, "Maximum number of lines to read"] = DEFAULT_LINE_LIMIT,
) -> str:
    """Read file contents with line numbers.

    Returns the file content in cat -n format with right-aligned line numbers.
    Lines are numbered starting from 1 in the output, with offset being 0-indexed.

    Security:
        - Path is validated against workspace boundaries
        - Symlinks are resolved before validation
        - Sensitive files (.env, credentials) are blocked

    Binary Files:
        - Binary files (detected by extension or content) return an error message

    Media Files:
        - Images and PDFs return base64-encoded content

    Pagination:
        - Default limit is 2000 lines
        - Output is also capped at 50KB
        - If truncated, instructions to continue reading are provided

    Example:
        >>> await read("/project/main.py")
        '     1\\tdef main():\\n     2\\t    pass\\n'

        >>> await read("/project/large.py", offset=100, limit=50)
        # Returns lines 100-149
    """
    ctx = get_security_context()

    # Validate path
    resolved_path, error = validate_path_or_error(ctx, file_path)
    if error:
        return error
    assert resolved_path is not None

    # Check file size
    try:
        ctx.validate_file_size(resolved_path)
    except WorkspaceSecurityError as e:
        return f"Error: {e}"

    # Check for media files (images, PDFs)
    if ctx.is_media_file(resolved_path):
        return _read_media_file(resolved_path)

    # Check for binary files
    if ctx.is_binary_file(resolved_path):
        return f"Error: Cannot read binary file: {file_path}"

    # Check file size to determine read strategy
    try:
        file_size = resolved_path.stat().st_size
    except (OSError, IOError):
        file_size = 0

    # Apply offset and limit bounds
    if offset < 0:
        offset = 0

    # Use streaming reader for large files to avoid loading entire file into memory
    if file_size > STREAMING_THRESHOLD:
        try:
            selected_lines, total_lines = await asyncio.to_thread(
                _read_lines_streaming, resolved_path, offset, limit, "utf-8"
            )
        except UnicodeDecodeError:
            try:
                selected_lines, total_lines = await asyncio.to_thread(
                    _read_lines_streaming, resolved_path, offset, limit, "latin-1"
                )
            except (UnicodeDecodeError, UnicodeError):
                return f"Error: Cannot decode file: {file_path}"
        except (IOError, OSError, PermissionError) as e:
            return f"Error: Failed to read file: {e}"

        if offset >= total_lines:
            return f"Error: Offset {offset} exceeds file length ({total_lines} lines)"
    else:
        # Standard approach for smaller files
        content, read_error = await async_safe_read_text(resolved_path)
        if read_error:
            return read_error
        assert content is not None

        lines = content.split("\n")
        total_lines = len(lines)

        if offset >= total_lines:
            return f"Error: Offset {offset} exceeds file length ({total_lines} lines)"

        selected_lines = lines[offset : offset + limit]

    # Format output with line numbers
    output = format_cat_n(selected_lines, start_line=offset + 1, max_line_length=MAX_LINE_LENGTH)

    # Check output size and truncate if needed
    if len(output.encode("utf-8")) > MAX_OUTPUT_BYTES:
        # Find where to truncate
        output_bytes = output.encode("utf-8")
        truncated_bytes = output_bytes[:MAX_OUTPUT_BYTES]
        # Find last complete line
        last_newline = truncated_bytes.rfind(b"\n")
        if last_newline > 0:
            output = truncated_bytes[:last_newline + 1].decode("utf-8", errors="replace")

        # Add truncation message
        end_line = offset + output.count("\n")
        output += f"\n... (output truncated at 50KB, use offset={end_line} to continue)"

    # Mark file as read for read-before-edit tracking
    ctx.mark_file_read(resolved_path)

    # Add continuation hint if we didn't read everything
    lines_read = len(selected_lines)
    remaining = total_lines - offset - lines_read
    if remaining > 0 and "\n... (output truncated" not in output:
        # Only if we hit the line limit, not byte limit
        if lines_read >= limit:
            output += f"\n... ({remaining} more lines, use offset={offset + lines_read} to continue)"

    return output


def _read_media_file(path: Path) -> str:
    """Read a media file and return as base64 data URL.

    Args:
        path: Path to the media file.

    Returns:
        Base64 data URL or error message.
    """
    try:
        mime_type, _ = mimetypes.guess_type(str(path))
        if mime_type is None:
            mime_type = "application/octet-stream"

        content = path.read_bytes()
        b64 = base64.b64encode(content).decode("ascii")

        # Return in a format that indicates it's an attachment
        return f"[Media file: {path.name}]\ndata:{mime_type};base64,{b64}"

    except Exception as e:
        return f"Error: Failed to read media file: {e}"


def _read_lines_streaming(
    path: Path,
    offset: int,
    limit: int,
    encoding: str = "utf-8",
) -> tuple[list[str], int]:
    """Read specific lines from a file without loading entire content into memory.

    This function is optimized for large files where loading everything into
    memory would be expensive. It reads line by line, skipping to the offset
    and collecting only the requested number of lines.

    Args:
        path: Path to the file to read.
        offset: Number of lines to skip (0-indexed).
        limit: Maximum number of lines to read after offset.
        encoding: File encoding (default: utf-8).

    Returns:
        Tuple of (selected_lines, total_line_count).

    Raises:
        UnicodeDecodeError: If file cannot be decoded.
        IOError/OSError: If file cannot be read.
    """
    selected_lines: list[str] = []
    line_count = 0

    with open(path, "r", encoding=encoding, errors="replace") as f:
        # Skip offset lines
        for _ in range(offset):
            try:
                next(f)
                line_count += 1
            except StopIteration:
                # File has fewer lines than offset
                return [], line_count

        # Read limit lines
        for line in f:
            line_count += 1
            if len(selected_lines) < limit:
                selected_lines.append(line.rstrip("\n\r"))
            # Continue counting remaining lines even after we have enough

    return selected_lines, line_count
