"""Glob tool for finding files by pattern.

Implements the OpenCode-compatible glob tool with:
- Glob pattern matching (**, *, ?)
- Results sorted by modification time (newest first)
- Security validation via SecurityContext
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Optional

from rawagents.tools import tool
from rawagents.tools.builtin.fs._security import (
    WorkspaceSecurityError,
    get_security_context,
)
from rawagents.tools.builtin.fs._utils import get_file_mtime, validate_path_or_error


__all__ = ["glob"]

MAX_RESULTS = 100


@tool
async def glob(
    pattern: Annotated[str, "The glob pattern to match files against"],
    path: Annotated[
        Optional[str],
        "Directory to search in. If not specified, uses current working directory.",
    ] = None,
    structured: Annotated[
        bool,
        "If True, return JSON with count, truncated flag, and results array.",
    ] = False,
) -> str:
    """Find files matching a glob pattern.

    Supports standard glob patterns:
    - `*` matches any characters except path separator
    - `**` matches any characters including path separators (recursive)
    - `?` matches single character
    - `[abc]` matches character classes

    Results are sorted by modification time, newest first.

    Security:
        - All returned paths are validated against workspace boundaries
        - Search directory must be within workspace

    Behavior:
        - Returns absolute paths, one per line
        - Limited to 100 results (truncated message if exceeded)
        - Returns "No files found" if no matches

    Example:
        >>> await glob("**/*.py")
        '/project/src/main.py\\n/project/tests/test_main.py'

        >>> await glob("*.json", path="/project/config")
    """
    ctx = get_security_context()

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

    # Find matching files
    matches: list[tuple[float, Path]] = []  # (mtime, path)
    truncated = False

    try:
        # Use pathlib's glob with ** support
        if "**" in pattern:
            # Recursive glob
            matched_paths = resolved_search.glob(pattern)
        else:
            # Non-recursive - match in directory and subdirs
            matched_paths = resolved_search.glob(pattern)

        for match_path in matched_paths:
            if match_path.is_file():
                # Validate each match is still within workspace
                try:
                    ctx.validate_path(str(match_path), check_exists=True)
                except WorkspaceSecurityError:
                    continue  # Skip files outside workspace

                mtime = get_file_mtime(match_path)
                matches.append((mtime, match_path))

                if len(matches) > MAX_RESULTS:
                    truncated = True
                    break

    except PermissionError:
        return f"Error: Permission denied while searching: {search_dir}"
    except Exception as e:
        return f"Error: Failed to search: {e}"

    if not matches:
        if structured:
            return json.dumps({"count": 0, "truncated": False, "results": []})
        return "No files found"

    # Sort by mtime descending (newest first)
    matches.sort(key=lambda x: x[0], reverse=True)

    # Limit results
    if len(matches) > MAX_RESULTS:
        matches = matches[:MAX_RESULTS]
        truncated = True

    # Format output
    result_paths = [str(p) for _, p in matches]

    if structured:
        return json.dumps({
            "count": len(result_paths),
            "truncated": truncated,
            "results": result_paths,
        })

    output = "\n".join(result_paths)

    if truncated:
        output += "\n\n(Results are truncated. Consider using a more specific path or pattern.)"

    return output
