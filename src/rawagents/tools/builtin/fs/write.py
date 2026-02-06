"""Write tool for creating/overwriting files.

Implements the OpenCode-compatible write tool with:
- Read-before-edit safety (existing files must be read first)
- Automatic parent directory creation
- Security validation via SecurityContext
"""

from __future__ import annotations

from typing import Annotated

from rawagents.tools import tool
from rawagents.tools.builtin.fs._locking import file_lock
from rawagents.tools.builtin.fs._security import (
    WorkspaceSecurityError,
    get_security_context,
)
from rawagents.tools.builtin.fs._utils import (
    aexists,
    amkdir,
    awrite_text,
    validate_path_or_error,
)


__all__ = ["write"]


@tool
async def write(
    file_path: Annotated[str, "The absolute path to the file to write"],
    content: Annotated[str, "Content to write to the file"],
) -> str:
    """Create or overwrite a file with the given content.

    Security:
        - Path is validated against workspace boundaries
        - Existing files must have been read first (read-before-edit tracking)
        - New files can be created without prior read

    Behavior:
        - Creates parent directories if they don't exist
        - Overwrites entire file contents
        - Returns "Wrote file successfully." on success

    Read-Before-Edit:
        For safety, existing files must be read in the current session
        before they can be overwritten. This prevents accidental data loss
        from blind overwrites. New files (that don't exist) can be written
        without a prior read.

    Example:
        >>> # Read first for existing files
        >>> await read("/project/config.json")
        >>> await write("/project/config.json", '{"key": "value"}')
        'Wrote file successfully.'

        >>> # New files don't need read first
        >>> await write("/project/new_file.py", "print('hello')")
        'Wrote file successfully.'
    """
    ctx = get_security_context()

    # Validate path (check_exists=False since we might be creating)
    resolved_path, error = validate_path_or_error(ctx, file_path, check_exists=False)
    if error:
        return error
    assert resolved_path is not None

    # Validate content size
    try:
        ctx.validate_content_size(content, operation="write")
    except WorkspaceSecurityError as e:
        return f"Error: {e}"

    # Check if file exists (determines locking and read-before-edit)
    if await aexists(resolved_path):
        if not ctx.check_read_before_edit(resolved_path):
            return (
                f"Error: File '{file_path}' exists but was not read in this session. "
                f"Please read the file first before overwriting it."
            )

        # Lock existing file for TOCTOU protection
        async with file_lock(resolved_path, exclusive=True):
            try:
                await awrite_text(resolved_path, content)
            except PermissionError:
                return f"Error: Permission denied writing to: {file_path}"
            except Exception as e:
                return f"Error: Failed to write file: {e}"
    else:
        # New file: create parent directories and write
        try:
            await amkdir(resolved_path.parent, parents=True, exist_ok=True)
        except PermissionError:
            return f"Error: Permission denied creating directory: {resolved_path.parent}"
        except Exception as e:
            return f"Error: Failed to create directory: {e}"

        try:
            await awrite_text(resolved_path, content)
        except PermissionError:
            return f"Error: Permission denied writing to: {file_path}"
        except Exception as e:
            return f"Error: Failed to write file: {e}"

    # Mark as read so subsequent edits work
    ctx.mark_file_read(resolved_path)

    return "Wrote file successfully."
