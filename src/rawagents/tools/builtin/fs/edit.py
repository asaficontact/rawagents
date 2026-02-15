"""Edit tool for modifying file contents.

Implements the OpenCode-compatible edit tool with:
- Multiple fallback matching strategies
- Read-before-edit safety
- Replace all support
- Security validation via SecurityContext
"""

from __future__ import annotations

from typing import Annotated

from rawagents.tools import tool
from rawagents.tools.builtin.fs._locking import file_lock
from rawagents.tools.builtin.fs._replacers import find_and_replace
from rawagents.tools.builtin.fs._security import (
    WorkspaceSecurityError,
    get_security_context,
)
from rawagents.tools.builtin.fs._utils import (
    amkdir,
    async_safe_read_text,
    awrite_text,
    require_read_before_edit,
    validate_path_or_error,
)


__all__ = ["edit"]


@tool
async def edit(
    file_path: Annotated[str, "The absolute path to the file to modify"],
    old_string: Annotated[str, "The text to replace"],
    new_string: Annotated[str, "The replacement text (must differ from old_string)"],
    replace_all: Annotated[bool, "Replace all occurrences (default: False)"] = False,
) -> str:
    """Modify file contents by replacing old_string with new_string.

    Uses multiple matching strategies to reduce brittle failures from
    minor formatting differences in LLM-generated oldString values:

    1. **SimpleReplacer**: Exact string match (fastest)
    2. **LineTrimmedReplacer**: Ignores leading/trailing whitespace per line
    3. **BlockAnchorReplacer**: Uses first/last line as anchors
    4. **WhitespaceNormalizedReplacer**: Collapses whitespace differences
    5. **IndentationFlexibleReplacer**: Allows different indentation levels

    Security:
        - Path is validated against workspace boundaries
        - File must have been read first (read-before-edit tracking)

    Special Cases:
        - If old_string is empty, creates/overwrites file with new_string
        - If replace_all=True, replaces all occurrences
        - If replace_all=False and multiple matches found, returns error

    Errors:
        - "old_string not found in content" - no match found
        - "Found N matches for old_string..." - multiple matches, not replacing all

    Example:
        >>> # First read the file
        >>> await read("/project/main.py")

        >>> # Then edit it
        >>> await edit(
        ...     file_path="/project/main.py",
        ...     old_string="def hello():\\n    pass",
        ...     new_string="def hello():\\n    print('Hello!')",
        ... )
        'Edit applied successfully.'

        >>> # Replace all occurrences
        >>> await edit(
        ...     file_path="/project/main.py",
        ...     old_string="foo",
        ...     new_string="bar",
        ...     replace_all=True,
        ... )
        'Edit applied successfully. (3 replacements)'
    """
    ctx = get_security_context()

    # Special case: empty old_string means create/overwrite
    if not old_string:
        resolved_path, error = validate_path_or_error(ctx, file_path, check_exists=False)
        if error:
            return error
        assert resolved_path is not None

        # Create parent directories
        try:
            await amkdir(resolved_path.parent, parents=True, exist_ok=True)
        except Exception as e:
            return f"Error: Failed to create directory: {e}"

        # Validate content size
        try:
            ctx.validate_content_size(new_string, operation="edit (create)")
        except WorkspaceSecurityError as e:
            return f"Error: {e}"

        # Write new content
        try:
            await awrite_text(resolved_path, new_string)
        except Exception as e:
            return f"Error: Failed to write file: {e}"

        ctx.mark_file_read(resolved_path)
        return "Edit applied successfully. (created new file)"

    # Normal case: file must exist and be read first
    resolved_path, error = validate_path_or_error(ctx, file_path)
    if error:
        return error
    assert resolved_path is not None

    error = require_read_before_edit(ctx, resolved_path, file_path)
    if error:
        return error

    # Lock file for TOCTOU protection during read-modify-write
    async with file_lock(resolved_path, exclusive=True):
        # Read current content
        content, error = await async_safe_read_text(resolved_path)
        if error:
            return error
        assert content is not None

        # Perform replacement using multiple strategies
        result = find_and_replace(content, old_string, new_string, replace_all)

        if not result.success:
            return f"Error: {result.error}"
        assert result.content is not None

        # Validate content size before writing
        try:
            ctx.validate_content_size(result.content, operation="edit")
        except WorkspaceSecurityError as e:
            return f"Error: {e}"

        # Write updated content
        try:
            await awrite_text(resolved_path, result.content)
        except Exception as e:
            return f"Error: Failed to write file: {e}"

    # Refresh mtime so subsequent edits don't trigger stale-file detection
    ctx.mark_file_read(resolved_path)

    # Format success message
    msg = "Edit applied successfully."
    if result.match_count > 1:
        msg = f"Edit applied successfully. ({result.match_count} replacements)"
    if result.strategy == "fuzzy":
        msg += " (applied via fuzzy matching — verify the result)"
    return msg
