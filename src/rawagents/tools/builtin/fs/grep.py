"""Grep tool for searching file contents.

Implements the OpenCode-compatible grep tool with:
- Regex pattern matching
- Results sorted by file modification time (newest first)
- Optional file pattern filtering
- Security validation via SecurityContext
"""

from __future__ import annotations

import asyncio
import fnmatch
import functools
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Annotated, Optional

from rawagents.tools import tool
from rawagents.tools.builtin.fs._security import (
    SecurityContext,
    WorkspaceSecurityError,
    get_security_context,
)
from rawagents.tools.builtin.fs._utils import (
    get_file_mtime,
    truncate_line,
    validate_path_or_error,
)


__all__ = ["grep"]

MAX_MATCHES = 100
MAX_LINE_LENGTH = 2000


@functools.lru_cache(maxsize=1)
def _is_ripgrep_available() -> bool:
    """Check if ripgrep is installed (cached, checked only once)."""
    try:
        subprocess.run(
            ["rg", "--version"],
            capture_output=True,
            check=True,
            timeout=2,
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


@tool
async def grep(
    pattern: Annotated[str, "The regex pattern to search for in file contents"],
    path: Annotated[
        Optional[str],
        "Directory to search in. Defaults to current working directory.",
    ] = None,
    include: Annotated[
        Optional[str],
        'File pattern to include (e.g., "*.py", "*.{ts,tsx}")',
    ] = None,
    structured: Annotated[
        bool,
        "If True, return JSON with count, truncated flag, and grouped results.",
    ] = False,
) -> str:
    """Search file contents using regex patterns.

    Searches for a regex pattern in files and returns matches grouped by file.
    Results are sorted by file modification time (newest files first).

    Security:
        - Search directory must be within workspace
        - All matched files are validated against workspace

    Behavior:
        - Uses Python's re module (or ripgrep if available)
        - Respects .gitignore patterns
        - Skips binary files automatically
        - Limited to 100 matches (truncated message if exceeded)
        - Match lines truncated at 2000 characters

    Output Format:
        ```
        Found N matches

        /path/to/file.py:
         Line 42: <matching line text>
         Line 43: <matching line text>

        /path/to/other.py:
         Line 10: <matching line text>
        ```

    Example:
        >>> await grep("def.*hello", path="/project/src", include="*.py")

        >>> await grep("TODO|FIXME")
    """
    ctx = get_security_context()

    if not pattern:
        return "Error: pattern is required"

    # Compile regex to validate it
    try:
        regex = re.compile(pattern)
    except re.error as e:
        return f"Error: Invalid regex pattern: {e}"

    # Determine search directory
    if path is None:
        if ctx.workspace:
            search_dir = Path(ctx.workspace)
        else:
            search_dir = Path.cwd()
    else:
        search_dir = Path(path)

    # Validate search directory
    resolved_search, error = validate_path_or_error(ctx, str(search_dir))
    if error:
        return error
    assert resolved_search is not None

    if not resolved_search.is_dir():
        return f"Error: Not a directory: {path}"

    # Try using ripgrep first, fall back to Python implementation
    result = await _grep_with_ripgrep(resolved_search, pattern, include, ctx, structured)
    if result is not None:
        return result

    # Fall back to Python implementation
    return await _grep_with_python(resolved_search, regex, include, ctx, structured)


async def _grep_with_ripgrep(
    search_dir: Path,
    pattern: str,
    include: Optional[str],
    ctx: SecurityContext,
    structured: bool = False,
) -> Optional[str]:
    """Try to use ripgrep for searching.

    Args:
        search_dir: Directory to search.
        pattern: Regex pattern.
        include: File pattern filter.
        ctx: Security context.
        structured: If True, return JSON output.

    Returns:
        Search results or None if ripgrep not available.
    """
    if not _is_ripgrep_available():
        return None

    # Build ripgrep command
    cmd = [
        "rg",
        "-nH",  # Line numbers, filename
        "--hidden",  # Search hidden files
        "--no-messages",  # Suppress warnings
        "--field-match-separator=|",  # Use | as separator
        "--regexp",
        pattern,
    ]

    if include:
        cmd.extend(["--glob", include])

    cmd.append(str(search_dir))

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=30
            )
        except asyncio.TimeoutError:
            proc.kill()
            return "Error: Search timed out"

        result_stdout = stdout_bytes.decode("utf-8", errors="replace")
        result_stderr = stderr_bytes.decode("utf-8", errors="replace")
        returncode = proc.returncode
    except FileNotFoundError:
        return None  # Fall back to Python
    except Exception:
        return None  # Fall back to Python

    if returncode == 1:
        # No matches
        return "No files found"
    elif returncode == 2:
        # Some errors but may have output
        if not result_stdout:
            return "No files found"
        # Continue with partial results
    elif returncode not in (0, 1, 2):
        return f"Error: ripgrep failed: {result_stderr}"

    # Parse ripgrep output
    matches: list[tuple[float, str, int, str]] = []  # (mtime, file, line_num, text)
    skipped_paths = False

    for line in result_stdout.strip().split("\n"):
        if not line:
            continue

        # Parse: filepath|linenum|text
        parts = line.split("|", 2)
        if len(parts) < 3:
            continue

        filepath, line_num_str, text = parts
        try:
            line_num = int(line_num_str)
        except ValueError:
            continue

        # Validate path is within workspace
        try:
            ctx.validate_path(filepath, check_exists=True)
        except (WorkspaceSecurityError, FileNotFoundError):
            skipped_paths = True
            continue

        mtime = get_file_mtime(Path(filepath))
        matches.append((mtime, filepath, line_num, text))

        if len(matches) >= MAX_MATCHES:
            break

    return _format_grep_output(matches, len(matches) >= MAX_MATCHES, skipped_paths, structured)


async def _grep_with_python(
    search_dir: Path,
    regex: re.Pattern,
    include: Optional[str],
    ctx: SecurityContext,
    structured: bool = False,
) -> str:
    """Search using Python implementation.

    Args:
        search_dir: Directory to search.
        regex: Compiled regex pattern.
        include: File pattern filter.
        ctx: Security context.
        structured: If True, return JSON output.

    Returns:
        Search results.
    """
    def _search_sync() -> tuple[list[tuple[float, str, int, str]], bool, bool]:
        """Run the Python grep search synchronously (for thread pool)."""
        _matches: list[tuple[float, str, int, str]] = []
        _skipped = False
        _truncated = False

        for root, dirs, files in os.walk(search_dir):
            # Skip hidden and common ignore directories
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".")
                and d not in ("node_modules", "__pycache__", ".venv", "venv")
            ]

            for filename in files:
                if include and not fnmatch.fnmatch(filename, include):
                    continue

                filepath = Path(root) / filename

                try:
                    ctx.validate_path(str(filepath), check_exists=True)
                except (WorkspaceSecurityError, FileNotFoundError):
                    _skipped = True
                    continue

                if ctx.is_binary_file(filepath):
                    continue

                try:
                    content = filepath.read_text(encoding="utf-8", errors="ignore")
                except (IOError, OSError, PermissionError):
                    continue

                mtime = get_file_mtime(filepath)

                for line_num, line in enumerate(content.split("\n"), 1):
                    if regex.search(line):
                        _matches.append((mtime, str(filepath), line_num, line))

                        if len(_matches) >= MAX_MATCHES:
                            return _matches, _skipped, True

        return _matches, _skipped, False

    matches, skipped_paths, truncated = await asyncio.to_thread(_search_sync)
    return _format_grep_output(matches, truncated, skipped_paths, structured)


def _format_grep_output(
    matches: list[tuple[float, str, int, str]],
    truncated: bool,
    skipped_paths: bool,
    structured: bool = False,
) -> str:
    """Format grep results.

    Args:
        matches: List of (mtime, filepath, line_num, text) tuples.
        truncated: Whether results were truncated.
        skipped_paths: Whether some paths were skipped.
        structured: If True, return JSON output.

    Returns:
        Formatted output string.
    """
    if not matches:
        if structured:
            return json.dumps({
                "count": 0,
                "truncated": False,
                "skipped_paths": skipped_paths,
                "files": {},
            })
        return "No files found"

    # Sort by mtime descending
    matches.sort(key=lambda x: x[0], reverse=True)

    # Group by file
    file_groups: dict[str, list[tuple[int, str]]] = {}
    for _, filepath, line_num, text in matches:
        if filepath not in file_groups:
            file_groups[filepath] = []
        file_groups[filepath].append((line_num, text))

    if structured:
        # Build structured JSON output
        files_dict: dict[str, list[dict[str, object]]] = {}
        for filepath, file_matches in file_groups.items():
            files_dict[filepath] = [
                {"line": line_num, "text": truncate_line(text.strip(), MAX_LINE_LENGTH)}
                for line_num, text in file_matches
            ]

        return json.dumps({
            "count": len(matches),
            "truncated": truncated,
            "skipped_paths": skipped_paths,
            "files": files_dict,
        })

    # Build text output
    lines = [f"Found {len(matches)} matches", ""]

    for filepath, file_matches in file_groups.items():
        lines.append(f"{filepath}:")
        for line_num, text in file_matches:
            truncated_text = truncate_line(text.strip(), MAX_LINE_LENGTH)
            lines.append(f" Line {line_num}: {truncated_text}")
        lines.append("")

    if truncated:
        lines.append("(Results are truncated. Consider using a more specific path or pattern.)")

    if skipped_paths:
        lines.append("(Some paths were inaccessible and skipped)")

    return "\n".join(lines)
