"""List tool for directory listing.

Implements the OpenCode-compatible list tool with:
- Unicode tree-style output (├──, └──, │)
- .gitignore-like ignore patterns
- Configurable file limits
- Security validation via SecurityContext
"""

from __future__ import annotations

import asyncio
import fnmatch
import os
from pathlib import Path
from typing import Annotated

from rawagents.tools import tool
from rawagents.tools.builtin.fs._security import (
    get_security_context,
)
from rawagents.tools.builtin.fs._utils import validate_path_or_error


__all__ = ["list_dir"]

# Default patterns to ignore (similar to ripgrep/git defaults)
DEFAULT_IGNORE_PATTERNS: frozenset[str] = frozenset(
    {
        ".git",
        ".git/*",
        "node_modules",
        "node_modules/*",
        "__pycache__",
        "__pycache__/*",
        "*.pyc",
        ".venv",
        ".venv/*",
        "venv",
        "venv/*",
        "dist",
        "dist/*",
        "build",
        "build/*",
        ".tox",
        ".tox/*",
        ".pytest_cache",
        ".pytest_cache/*",
        ".mypy_cache",
        ".mypy_cache/*",
        ".ruff_cache",
        ".ruff_cache/*",
        "*.egg-info",
        "*.egg-info/*",
        ".DS_Store",
        "Thumbs.db",
    }
)

MAX_FILES = 100


@tool
async def list_dir(
    path: Annotated[str, "Directory to list. Absolute path recommended."] = ".",
    ignore: Annotated[
        list[str] | None,
        "Glob patterns to ignore (added to defaults)",
    ] = None,
) -> str:
    """List files under a directory with a tree-style output.

    Produces Unicode tree output similar to the `tree` command:
    ```
    /absolute/path/
    ├── src/
    │   └── main.py
    └── tests/
        └── test_main.py
    ```

    Security:
        - Path is validated against workspace boundaries
        - Symlinks are resolved before validation

    Behavior:
        - Respects .gitignore-like patterns
        - Default ignores: .git, node_modules, __pycache__, .venv, etc.
        - Directories shown with trailing /
        - Limited to 100 files (truncated message if exceeded)

    Example:
        >>> await list_dir("/project")
        '/project/\\n├── src/\\n│   └── main.py\\n└── README.md\\n'

        >>> await list_dir("/project", ignore=["*.log", "temp/*"])
    """
    ctx = get_security_context()

    # Resolve the path - use current workspace if "."
    if path == ".":
        if ctx.workspace:
            path = ctx.workspace
        else:
            path = str(Path.cwd())

    # Validate path
    resolved_path, error = validate_path_or_error(ctx, path)
    if error:
        return error
    assert resolved_path is not None

    if not resolved_path.is_dir():
        return f"Error: Not a directory: {path}"

    # Combine default and user ignore patterns
    ignore_patterns = set(DEFAULT_IGNORE_PATTERNS)
    if ignore:
        ignore_patterns.update(ignore)

    # Collect files and directories
    entries: list[tuple[Path, bool]] = []  # (path, is_dir)
    truncated = False

    try:
        walk_result = await asyncio.to_thread(
            _walk_directory, resolved_path, ignore_patterns, MAX_FILES
        )
        for item in walk_result:
            if len(entries) >= MAX_FILES:
                truncated = True
                break
            entries.append(item)
    except PermissionError:
        return f"Error: Permission denied: {path}"

    # Build tree output
    output = _build_tree(resolved_path, entries, truncated)
    return output


def _should_ignore(path: Path, base: Path, patterns: set[str]) -> bool:
    """Check if a path should be ignored based on patterns.

    Args:
        path: The path to check.
        base: The base directory for relative paths.
        patterns: Set of glob patterns to match against.

    Returns:
        True if the path should be ignored.
    """
    name = path.name
    try:
        rel_path = str(path.relative_to(base))
    except ValueError:
        rel_path = str(path)

    for pattern in patterns:
        # Check against filename
        if _matches_pattern(name, pattern):
            return True
        # Check against relative path
        if _matches_pattern(rel_path, pattern):
            return True

    return False


def _matches_pattern(text: str, pattern: str) -> bool:
    """Simple glob pattern matching.

    Args:
        text: The text to match.
        pattern: The glob pattern (* matches any).

    Returns:
        True if the pattern matches.
    """
    return fnmatch.fnmatch(text, pattern) or fnmatch.fnmatch(text, pattern.rstrip("/*"))


def _walk_directory(
    root: Path,
    ignore_patterns: set[str],
    max_count: int,
) -> list[tuple[Path, bool]]:
    """Walk a directory and collect entries.

    Args:
        root: The root directory to walk.
        ignore_patterns: Patterns to ignore.
        max_count: Maximum number of entries to collect.

    Returns:
        List of (path, is_dir) tuples, sorted appropriately.
    """
    entries: list[tuple[Path, bool]] = []
    count = 0

    for dirpath, dirnames, filenames in os.walk(root):
        current_dir = Path(dirpath)

        # Filter out ignored directories (modifies in place for os.walk)
        dirnames[:] = [
            d
            for d in sorted(dirnames)
            if not _should_ignore(current_dir / d, root, ignore_patterns)
        ]

        # Add directories
        for dirname in dirnames:
            if count >= max_count:
                return entries
            dir_path = current_dir / dirname
            entries.append((dir_path, True))
            count += 1

        # Add files
        for filename in sorted(filenames):
            if count >= max_count:
                return entries
            file_path = current_dir / filename
            if not _should_ignore(file_path, root, ignore_patterns):
                entries.append((file_path, False))
                count += 1

    return entries


def _build_tree(
    root: Path,
    entries: list[tuple[Path, bool]],
    truncated: bool,
) -> str:
    """Build a tree-style output string.

    Args:
        root: The root directory.
        entries: List of (path, is_dir) tuples.
        truncated: Whether results were truncated.

    Returns:
        Formatted tree string.
    """
    if not entries:
        result = f"{root}/\n(empty directory)\n"
        return result

    # Build tree structure
    lines: list[str] = [f"{root}/"]

    # Group entries by parent directory
    tree: dict[Path, list[tuple[str, bool]]] = {}
    for path, is_dir in entries:
        parent = path.parent
        name = path.name + ("/" if is_dir else "")
        if parent not in tree:
            tree[parent] = []
        tree[parent].append((name, path))

    # Render tree recursively
    _render_tree(root, tree, lines, "", is_last=True, is_root=True)

    if truncated:
        lines.append("")
        lines.append(f"(Results truncated at {MAX_FILES} files)")

    return "\n".join(lines)


def _render_tree(
    current: Path,
    tree: dict[Path, list[tuple[str, Path]]],
    lines: list[str],
    prefix: str,
    is_last: bool,
    is_root: bool,
) -> None:
    """Recursively render tree structure.

    Args:
        current: Current directory being rendered.
        tree: The tree structure.
        lines: Output lines list (modified in place).
        prefix: Current line prefix for indentation.
        is_last: Whether this is the last item in parent.
        is_root: Whether this is the root directory.
    """
    if current not in tree:
        return

    children = tree[current]
    for i, (name, path) in enumerate(children):
        is_last_child = i == len(children) - 1

        # Determine the connector
        if is_root and i == 0:
            # First item after root - no prefix needed for root level
            connector = "├── " if not is_last_child else "└── "
            new_prefix = "│   " if not is_last_child else "    "
        else:
            connector = "├── " if not is_last_child else "└── "
            new_prefix = prefix + ("│   " if not is_last_child else "    ")

        lines.append(f"{prefix}{connector}{name}")

        # Recurse for directories
        if path.is_dir() and path in tree:
            _render_tree(path, tree, lines, new_prefix, is_last_child, False)
