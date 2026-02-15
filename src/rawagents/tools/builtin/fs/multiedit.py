"""MultiEdit tool for atomic multiple edits.

Implements the OpenCode-compatible multiedit tool with:
- Atomic all-or-nothing semantics
- Rollback on failure
- Sequential edit application
- Security validation via SecurityContext
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel

from rawagents.tools import tool
from rawagents.tools.builtin.fs._locking import file_lock
from rawagents.tools.builtin.fs._replacers import find_and_replace
from rawagents.tools.builtin.fs._security import (
    WorkspaceSecurityError,
    get_security_context,
)
from rawagents.tools.builtin.fs._utils import (
    async_safe_read_text,
    awrite_text,
    require_read_before_edit,
    validate_path_or_error,
)


__all__ = ["EditOp", "multiedit"]


class EditOp(BaseModel):
    """A single edit operation within a multiedit.

    Attributes:
        file_path: The absolute path to the file (must match top-level file_path).
        old_string: The text to replace.
        new_string: The replacement text.
        replace_all: Whether to replace all occurrences (default: False).
    """

    file_path: str
    old_string: str
    new_string: str
    replace_all: bool = False


@tool
async def multiedit(
    file_path: Annotated[str, "The absolute path to the file to modify"],
    edits: Annotated[list[EditOp], "Array of edit operations to perform"],
) -> str:
    """Perform multiple edits on a file atomically.

    All edits are validated and applied together. If any edit fails,
    ALL changes are rolled back and the file is restored to its
    original state. This prevents partial modifications that could
    leave the file in an inconsistent state.

    Security:
        - Path is validated against workspace boundaries
        - File must have been read first (read-before-edit tracking)
        - All edit file_path values must match the top-level file_path

    Atomic Behavior:
        1. Read and preserve original content
        2. Validate all edits can be applied
        3. Apply edits sequentially to a working copy
        4. If any edit fails, return error (file unchanged)
        5. Write final result only if all edits succeed

    Example:
        >>> await read("/project/main.py")

        >>> await multiedit(
        ...     file_path="/project/main.py",
        ...     edits=[
        ...         EditOp(file_path="/project/main.py", old_string="foo", new_string="bar"),
        ...         EditOp(file_path="/project/main.py", old_string="hello", new_string="world"),
        ...     ]
        ... )
        'MultiEdit applied successfully. (2 edits)'
    """
    ctx = get_security_context()

    if not edits:
        return "Error: No edits provided"

    # Validate all edits reference the same file
    for i, edit in enumerate(edits):
        if edit.file_path != file_path:
            return (
                f"Error: Edit {i} has file_path '{edit.file_path}' but "
                f"top-level file_path is '{file_path}'. All edits must target the same file."
            )

    # Validate path
    resolved_path, error = validate_path_or_error(ctx, file_path)
    if error:
        return error
    assert resolved_path is not None

    # Check read-before-edit
    error = require_read_before_edit(ctx, resolved_path, file_path)
    if error:
        return error

    # Lock file for TOCTOU protection during read-modify-write
    async with file_lock(resolved_path, exclusive=True):
        # Read original content (this is our rollback point)
        original_content, error = await async_safe_read_text(resolved_path)
        if error:
            return error
        assert original_content is not None

        # Apply edits sequentially to a working copy
        working_content = original_content
        total_replacements = 0

        for i, edit in enumerate(edits):
            # Special case: empty old_string means replace entire content
            if not edit.old_string:
                if edit.new_string == working_content:
                    # No change needed
                    continue
                working_content = edit.new_string
                total_replacements += 1
                continue

            # Validate old_string != new_string
            if edit.old_string == edit.new_string:
                return (
                    f"Error: Edit {i} has identical old_string and new_string. "
                    f"No change would occur."
                )

            # Apply replacement
            result = find_and_replace(
                working_content,
                edit.old_string,
                edit.new_string,
                edit.replace_all,
            )

            if not result.success:
                # Return error with context about which edit failed
                return f"Error: Edit {i} failed: {result.error}"
            assert result.content is not None

            working_content = result.content
            total_replacements += result.match_count

        # Validate content size before writing
        try:
            ctx.validate_content_size(working_content, operation="multiedit")
        except WorkspaceSecurityError as e:
            return f"Error: {e}"

        # All edits applied successfully - write the result
        try:
            await awrite_text(resolved_path, working_content)
        except Exception as e:
            return f"Error: Failed to write file: {e}"

    return f"MultiEdit applied successfully. ({len(edits)} edits, {total_replacements} replacements)"
