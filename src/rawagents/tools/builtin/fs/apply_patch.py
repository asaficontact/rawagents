"""ApplyPatch tool for Codex-style patch application.

Implements the OpenCode-compatible apply_patch tool with:
- V4A patch format parsing
- Add/Update/Move/Delete operations
- Security validation via SecurityContext
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

from rawagents.tools import tool
from rawagents.tools.builtin.fs._locking import file_lock
from rawagents.tools.builtin.fs._replacers import find_and_replace
from rawagents.tools.builtin.fs._security import (
    SecurityContext,
    WorkspaceSecurityError,
    get_security_context,
)
from rawagents.tools.builtin.fs._utils import (
    amkdir,
    async_safe_read_text,
    aunlink,
    awrite_text,
    require_read_before_edit,
    validate_path_or_error,
)


__all__ = ["apply_patch"]


class HunkType(Enum):
    """Type of patch hunk operation."""

    ADD = "add"
    UPDATE = "update"
    DELETE = "delete"


@dataclass
class PatchHunk:
    """A single hunk in a patch.

    Attributes:
        type: The operation type (add, update, delete).
        file_path: Target file path.
        move_path: New path for move operations (update with move).
        content: New file content (for add/update).
        chunks: List of diff chunks for update operations.
    """

    type: HunkType
    file_path: str
    move_path: Optional[str] = None
    content: Optional[str] = None
    chunks: list[tuple[str, str]] = field(default_factory=list)  # (old_text, new_text)


@dataclass
class ParsedPatch:
    """A parsed patch bundle.

    Attributes:
        hunks: List of patch hunks.
        errors: Any parsing errors encountered.
    """

    hunks: list[PatchHunk] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def parse_patch(patch_text: str) -> ParsedPatch:
    """Parse a Codex V4A style patch.

    Patch format:
        *** Begin Patch
        *** Add File: <path>
        +line1
        +line2
        *** Update File: <path>
        *** Move to: <new-path>  (optional)
        @@ ... @@
        -old line
        +new line
        *** Delete File: <path>
        *** End Patch

    Args:
        patch_text: The patch text to parse.

    Returns:
        ParsedPatch with hunks and any errors.
    """
    result = ParsedPatch()
    lines = patch_text.strip().split("\n")

    if not lines:
        result.errors.append("Empty patch text")
        return result

    # Check for patch markers
    if not lines[0].strip().startswith("*** Begin Patch"):
        result.errors.append("Patch must start with '*** Begin Patch'")
        return result

    if not any(line.strip().startswith("*** End Patch") for line in lines):
        result.errors.append("Patch must end with '*** End Patch'")
        return result

    current_hunk: Optional[PatchHunk] = None
    in_chunk = False
    chunk_old: list[str] = []
    chunk_new: list[str] = []

    i = 1  # Skip "*** Begin Patch"
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # End of patch
        if stripped.startswith("*** End Patch"):
            if current_hunk:
                _finalize_hunk(current_hunk, chunk_old, chunk_new, in_chunk)
                result.hunks.append(current_hunk)
            break

        # Add file
        if stripped.startswith("*** Add File:"):
            if current_hunk:
                _finalize_hunk(current_hunk, chunk_old, chunk_new, in_chunk)
                result.hunks.append(current_hunk)
                chunk_old, chunk_new = [], []
                in_chunk = False

            file_path = stripped[len("*** Add File:") :].strip()
            current_hunk = PatchHunk(type=HunkType.ADD, file_path=file_path)
            current_hunk.content = ""

        # Update file
        elif stripped.startswith("*** Update File:"):
            if current_hunk:
                _finalize_hunk(current_hunk, chunk_old, chunk_new, in_chunk)
                result.hunks.append(current_hunk)
                chunk_old, chunk_new = [], []
                in_chunk = False

            file_path = stripped[len("*** Update File:") :].strip()
            current_hunk = PatchHunk(type=HunkType.UPDATE, file_path=file_path)

        # Move to (part of update)
        elif stripped.startswith("*** Move to:"):
            if current_hunk and current_hunk.type == HunkType.UPDATE:
                current_hunk.move_path = stripped[len("*** Move to:") :].strip()

        # Delete file
        elif stripped.startswith("*** Delete File:"):
            if current_hunk:
                _finalize_hunk(current_hunk, chunk_old, chunk_new, in_chunk)
                result.hunks.append(current_hunk)
                chunk_old, chunk_new = [], []
                in_chunk = False

            file_path = stripped[len("*** Delete File:") :].strip()
            current_hunk = PatchHunk(type=HunkType.DELETE, file_path=file_path)

        # Chunk marker
        elif stripped.startswith("@@"):
            if current_hunk and current_hunk.type == HunkType.UPDATE:
                # Save previous chunk
                if in_chunk and (chunk_old or chunk_new):
                    current_hunk.chunks.append(("\n".join(chunk_old), "\n".join(chunk_new)))
                chunk_old, chunk_new = [], []
                in_chunk = True

        # Content lines
        elif current_hunk:
            if current_hunk.type == HunkType.ADD:
                # Add file: lines start with +
                if line.startswith("+"):
                    if current_hunk.content:
                        current_hunk.content += "\n" + line[1:]
                    else:
                        current_hunk.content = line[1:]
                elif line.startswith(" ") or not line.strip():
                    # Context line or empty
                    if current_hunk.content:
                        current_hunk.content += "\n" + line[1:] if len(line) > 1 else "\n"

            elif current_hunk.type == HunkType.UPDATE and in_chunk:
                # Update chunks
                if line.startswith("-"):
                    chunk_old.append(line[1:])
                elif line.startswith("+"):
                    chunk_new.append(line[1:])
                elif line.startswith(" "):
                    # Context line - goes in both
                    chunk_old.append(line[1:] if len(line) > 1 else "")
                    chunk_new.append(line[1:] if len(line) > 1 else "")

        i += 1

    # Handle any remaining hunk
    if current_hunk and current_hunk not in result.hunks:
        _finalize_hunk(current_hunk, chunk_old, chunk_new, in_chunk)
        result.hunks.append(current_hunk)

    if not result.hunks:
        result.errors.append("No hunks found in patch")

    return result


def _finalize_hunk(
    hunk: PatchHunk,
    chunk_old: list[str],
    chunk_new: list[str],
    in_chunk: bool,
) -> None:
    """Finalize a hunk by saving any pending chunk."""
    if hunk.type == HunkType.UPDATE and in_chunk and (chunk_old or chunk_new):
        hunk.chunks.append(("\n".join(chunk_old), "\n".join(chunk_new)))

    # Ensure add files have trailing newline
    if hunk.type == HunkType.ADD and hunk.content and not hunk.content.endswith("\n"):
        hunk.content += "\n"


@tool
async def apply_patch(
    patch_text: Annotated[str, "The full patch text describing all changes"],
) -> str:
    """Apply a Codex-style patch bundle.

    Patch format (V4A):
        ```
        *** Begin Patch
        *** Add File: src/new.py
        +def hello():
        +    print("hello")
        *** Update File: src/main.py
        @@ ... @@
        -old line
        +new line
        *** Delete File: src/old.py
        *** End Patch
        ```

    Supported Operations:
        - **Add File**: Creates a new file with the given content
        - **Update File**: Modifies existing file using diff chunks
        - **Move to**: Renames/moves a file (used with Update)
        - **Delete File**: Removes a file

    Security:
        - All paths are validated against workspace boundaries
        - Target files for update must exist
        - Parent directories created as needed for add operations

    Behavior:
        - Operations are applied in order
        - All paths are resolved against the workspace
        - Returns summary of changes made

    Example:
        >>> await apply_patch('''*** Begin Patch
        ... *** Add File: src/hello.py
        ... +def hello():
        ... +    print("hello")
        ... *** End Patch''')
        'Success. Updated the following files:\\nA src/hello.py'
    """
    ctx = get_security_context()

    if not patch_text:
        return "Error: patch_text is required"

    if not patch_text.strip():
        return "Error: patch_text is empty"

    # Check for empty patch
    if "*** Begin Patch" in patch_text and "*** End Patch" in patch_text:
        # Find content between markers
        start = patch_text.find("*** Begin Patch")
        end = patch_text.find("*** End Patch")
        between = patch_text[start + len("*** Begin Patch") : end].strip()
        if not between:
            return "Error: patch rejected: empty patch"

    # Parse the patch
    parsed = parse_patch(patch_text)

    if parsed.errors:
        return f"Error: apply_patch verification failed: {'; '.join(parsed.errors)}"

    if not parsed.hunks:
        return "Error: apply_patch verification failed: no hunks found"

    # Resolve paths relative to workspace
    workspace = Path(ctx.workspace) if ctx.workspace else Path.cwd()

    for hunk in parsed.hunks:
        # Make paths absolute relative to workspace
        if not Path(hunk.file_path).is_absolute():
            hunk.file_path = str(workspace / hunk.file_path)
        if hunk.move_path and not Path(hunk.move_path).is_absolute():
            hunk.move_path = str(workspace / hunk.move_path)

    # Validate all paths
    for hunk in parsed.hunks:
        try:
            # For add, check_exists=False; for update/delete, check_exists varies
            ctx.validate_path(hunk.file_path, check_exists=False)

            if hunk.move_path:
                ctx.validate_path(hunk.move_path, check_exists=False)

        except WorkspaceSecurityError as e:
            return f"Error: {e}"

    # Apply hunks
    changes: list[str] = []
    errors: list[str] = []

    for hunk in parsed.hunks:
        try:
            if hunk.type == HunkType.ADD:
                result = await _apply_add(hunk, ctx)
            elif hunk.type == HunkType.UPDATE:
                result = await _apply_update(hunk, ctx)
            elif hunk.type == HunkType.DELETE:
                result = await _apply_delete(hunk, ctx)
            else:
                result = f"Unknown hunk type: {hunk.type}"

            if result.startswith("Error"):
                errors.append(result)
            else:
                changes.append(result)

        except Exception as e:
            errors.append(f"Error applying {hunk.type.value} to {hunk.file_path}: {e}")

    # Build result
    if errors and not changes:
        return "\n".join(errors)

    output_lines = ["Success. Updated the following files:"]
    output_lines.extend(changes)

    if errors:
        output_lines.append("")
        output_lines.extend(errors)

    return "\n".join(output_lines)


async def _apply_add(hunk: PatchHunk, ctx: SecurityContext) -> str:
    """Apply an add file operation."""
    resolved, error = validate_path_or_error(ctx, hunk.file_path, check_exists=False)
    if error:
        return error
    assert resolved is not None

    # Create parent directories
    await amkdir(resolved.parent, parents=True, exist_ok=True)

    # Write content
    content = hunk.content or ""
    if not content.endswith("\n"):
        content += "\n"

    # Validate content size
    try:
        ctx.validate_content_size(content, operation="patch add")
    except WorkspaceSecurityError as e:
        return f"Error: {e}"

    await awrite_text(resolved, content)
    ctx.mark_file_read(resolved)

    # Return relative path from workspace
    try:
        rel_path = resolved.relative_to(Path(ctx.workspace)) if ctx.workspace else resolved
    except ValueError:
        rel_path = resolved

    return f"A {rel_path}"


async def _apply_update(hunk: PatchHunk, ctx: SecurityContext) -> str:
    """Apply an update file operation."""
    resolved, error = validate_path_or_error(ctx, hunk.file_path)
    if error:
        return error
    assert resolved is not None

    error = require_read_before_edit(ctx, resolved, hunk.file_path)
    if error:
        return error

    # Lock file for TOCTOU protection during read-modify-write
    async with file_lock(resolved, exclusive=True):
        # Read current content
        content, error = await async_safe_read_text(resolved)
        if error:
            return error
        assert content is not None

        # Apply chunks using replacement strategies
        failed_chunks: list[tuple[int, str]] = []
        for idx, (old_text, new_text) in enumerate(hunk.chunks):
            result = find_and_replace(content, old_text, new_text, replace_all=False)
            if result.success:
                assert result.content is not None
                content = result.content
            else:
                failed_chunks.append((idx, result.error or "unknown error"))

        if failed_chunks:
            details = "; ".join(f"chunk {i}: {e}" for i, e in failed_chunks)
            return f"Error: Failed to apply {len(failed_chunks)} chunk(s) to {hunk.file_path}: {details}"

        # Handle move
        target_path = resolved
        if hunk.move_path:
            try:
                target_path = ctx.validate_path(hunk.move_path, check_exists=False)
            except WorkspaceSecurityError as e:
                return f"Error: {e}"

            await amkdir(target_path.parent, parents=True, exist_ok=True)

        # Validate content size
        try:
            ctx.validate_content_size(content, operation="patch update")
        except WorkspaceSecurityError as e:
            return f"Error: {e}"

        # Write content to target
        await awrite_text(target_path, content)
        ctx.mark_file_read(target_path)

        # Delete original if moved
        if hunk.move_path and resolved != target_path:
            await aunlink(resolved)

    # Return relative path
    try:
        rel_path = target_path.relative_to(Path(ctx.workspace)) if ctx.workspace else target_path
    except ValueError:
        rel_path = target_path

    return f"M {rel_path}"


async def _apply_delete(hunk: PatchHunk, ctx: SecurityContext) -> str:
    """Apply a delete file operation."""
    resolved, error = validate_path_or_error(ctx, hunk.file_path)
    if error:
        return error
    assert resolved is not None

    error = require_read_before_edit(ctx, resolved, hunk.file_path)
    if error:
        return error

    # Lock file for TOCTOU protection during delete
    async with file_lock(resolved, exclusive=True):
        await aunlink(resolved)

    # Return relative path
    try:
        rel_path = resolved.relative_to(Path(ctx.workspace)) if ctx.workspace else resolved
    except ValueError:
        rel_path = resolved

    return f"D {rel_path}"
