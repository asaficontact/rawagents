"""File system tools for RawAgents.

Provides Claude Code-compatible file operations with security-first design:

- **read**: Read file contents with line numbers (cat -n style)
- **write**: Create or overwrite files
- **edit**: Replace text in files (OpenCode-style matching)
- **list_dir**: List directory tree (Unicode tree style)
- **glob**: Find files by pattern (mtime-sorted)
- **grep**: Search file contents using ripgrep
- **multiedit**: Perform multiple edits atomically
- **apply_patch**: Apply Codex-style patch bundles (V4A format)

Security:
    All tools validate paths via SecurityContext before any operation.
    This prevents path traversal, symlink escape attacks, and access
    to sensitive files.

Example:
    >>> from rawagents.tools.builtin.fs import (
    ...     read, write, edit, list_dir, glob, grep,
    ...     SecurityContext, set_security_context,
    ... )
    >>>
    >>> # Configure security context
    >>> ctx = SecurityContext(workspace="/home/user/project")
    >>> set_security_context(ctx)
    >>>
    >>> # Now use tools safely
    >>> content = await read(file_path="/home/user/project/main.py")
"""

from rawagents.tools.builtin.fs._security import (
    SecurityContext,
    SecurityContextNotSetError,
    WorkspaceSecurityError,
    get_security_context,
    set_security_context,
    validate_path,
)
from rawagents.tools.builtin.fs.apply_patch import apply_patch
from rawagents.tools.builtin.fs.edit import edit
from rawagents.tools.builtin.fs.glob import glob
from rawagents.tools.builtin.fs.grep import grep
from rawagents.tools.builtin.fs.list import list_dir
from rawagents.tools.builtin.fs.multiedit import EditOp, multiedit

# Import all tools
from rawagents.tools.builtin.fs.read import read
from rawagents.tools.builtin.fs.write import write


__all__ = [
    # Security
    "SecurityContext",
    "SecurityContextNotSetError",
    "WorkspaceSecurityError",
    "get_security_context",
    "set_security_context",
    "validate_path",
    # Tools
    "read",
    "write",
    "edit",
    "list_dir",
    "glob",
    "grep",
    "multiedit",
    "EditOp",
    "apply_patch",
]
