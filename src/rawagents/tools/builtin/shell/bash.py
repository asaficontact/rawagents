"""Bash tool for executing shell commands.

Implements shell command execution with:
- Async subprocess execution
- Timeout handling with graceful termination
- Background process support
- Security validation via ShellSecurityContext
"""

from __future__ import annotations

import asyncio
import os
import shlex
import signal
import tempfile
import time
from typing import TYPE_CHECKING, Annotated

from rawagents.tools import tool
from rawagents.tools.builtin.shell._errors import get_audit_logger
from rawagents.tools.builtin.shell._process_manager import get_process_manager
from rawagents.tools.builtin.shell._security import (
    CommandSecurityError,
    get_shell_security_context,
)


if TYPE_CHECKING:
    from rawagents.tools.builtin.shell._security import ShellSecurityContext


__all__ = ["bash"]

MAX_OUTPUT_BYTES = 50 * 1024  # 50KB output limit
MAX_OUTPUT_LINES = 2000  # Max lines before truncation


def _extract_cd_target(command: str) -> str | None:
    """Extract the target directory from a cd command.

    Handles various cd patterns:
    - cd (no args, goes to home)
    - cd /absolute/path
    - cd relative/path
    - cd ~, cd ~/subdir
    - cd -, cd $OLDPWD
    - cd "path with spaces"
    - cd 'path with spaces'
    - Chained: cd /path && other_command
    - Chained: cd /path; other_command

    Args:
        command: The shell command string.

    Returns:
        The cd target directory, or None if not a cd command.
    """
    stripped = command.strip()

    # Check if this is a cd command
    if stripped == "cd":
        return "~"

    if not (stripped.startswith("cd ") or stripped.startswith("cd\t")):
        return None

    # Extract the part after "cd "
    rest = stripped[3:].strip()
    if not rest:
        return "~"

    # Handle chained commands - only process up to first command separator
    # We need to be careful with separators inside quotes
    separators = ["&&", "||", ";", "|"]

    # Simple heuristic: find first unquoted separator
    in_single_quote = False
    in_double_quote = False
    target_end = len(rest)

    for i, char in enumerate(rest):
        if char == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
        elif char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
        elif not in_single_quote and not in_double_quote:
            for sep in separators:
                if rest[i:].startswith(sep):
                    target_end = i
                    break
            if target_end != len(rest):
                break

    target = rest[:target_end].strip()

    # Remove surrounding quotes if present
    if (target.startswith('"') and target.endswith('"')) or (
        target.startswith("'") and target.endswith("'")
    ):
        target = target[1:-1]

    return target if target else "~"


def _update_working_directory_from_command(
    ctx: ShellSecurityContext,
    command: str,
    exit_code: int,
) -> None:
    """Update working directory tracking based on command execution.

    Only updates if the command succeeded (exit_code == 0) to avoid
    tracking failed cd attempts.

    Args:
        ctx: The security context to update.
        command: The executed command.
        exit_code: The command's exit code.
    """
    if exit_code != 0:
        return

    cd_target = _extract_cd_target(command)
    if cd_target is not None:
        ctx.update_working_directory(cd_target)


@tool
async def bash(  # noqa: PLR0912, PLR0915
    command: Annotated[str, "The shell command to execute"],
    description: Annotated[  # noqa: ARG001
        str | None, "Description of what this command does"
    ] = None,
    timeout: Annotated[int | None, "Timeout in milliseconds (max 600000)"] = None,
    run_in_background: Annotated[bool, "Run command in background, return PID"] = False,
    dangerously_disable_sandbox: Annotated[
        bool, "Override sandbox mode (use with extreme caution)"
    ] = False,
) -> str:
    """Execute a shell command.

    Executes the given command in a shell (bash by default). The working
    directory persists between commands in the same session.

    Security:
        - Commands are validated against deny patterns
        - Working directory is tracked and can be restricted
        - Optional sandbox integration for OS-level isolation

    Background Mode:
        - Set run_in_background=True for long-running commands
        - Returns process ID immediately
        - Use bash_output() to retrieve output
        - Use kill_shell() to terminate

    Timeout:
        - Default: 120 seconds
        - Maximum: 600 seconds (10 minutes)
        - On timeout: SIGTERM, then SIGKILL after 5 seconds

    Example:
        >>> await bash("git status")
        'On branch main\\nnothing to commit...'

        >>> await bash("npm run dev", run_in_background=True)
        'Started background process with PID: 12345'
    """
    ctx = get_shell_security_context()
    audit = get_audit_logger()
    start_time = time.monotonic()

    # Validate command
    try:
        ctx.validate_command(command)
    except CommandSecurityError as e:
        if audit:
            audit.log_security_event(
                command=command,
                reason=e.reason or "unknown",
                pattern=e.pattern,
            )
        return f"Error: {e}"

    # Validate and normalize timeout
    timeout_ms = ctx.validate_timeout(timeout)
    timeout_sec = timeout_ms / 1000

    # Get execution environment
    cwd = ctx.get_working_directory()
    env = os.environ.copy()

    # Build command (with optional sandbox wrapper)
    use_sandbox = ctx.enable_sandbox and not dangerously_disable_sandbox

    # Sync Python-tracked previous directory so "cd -" works in subprocesses.
    # Shells ignore OLDPWD from the environment; it must be set as a shell
    # variable inside the script for "cd -" to resolve correctly.
    oldpwd_prefix = ""
    if ctx._previous_directory:
        escaped = shlex.quote(str(ctx._previous_directory))
        oldpwd_prefix = f"OLDPWD={escaped}; "

    if use_sandbox:
        cmd_args = ctx.build_sandbox_command(oldpwd_prefix + command)
        shell_command = shlex.join(cmd_args)
    else:
        # Apply env_file sourcing even when not sandboxed
        shell_command = ctx._build_command_with_env(oldpwd_prefix + command)

    try:
        # Create subprocess
        process = await asyncio.create_subprocess_shell(
            shell_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,  # Combine stdout/stderr
            cwd=str(cwd),
            env=env,
            start_new_session=True,  # Enable process group killing
        )

        if run_in_background:
            # Register and return immediately
            manager = get_process_manager()
            pid = await manager.register(process, command)
            if audit:
                audit.log_background_process(pid, command, "started")
            return f"Started background process with PID: {pid}"

        # Wait for completion with timeout
        try:
            stdout, _ = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout_sec,
            )
        except TimeoutError:
            # Graceful termination
            try:
                pgid = os.getpgid(process.pid)
                os.killpg(pgid, signal.SIGTERM)

                # Wait briefly for graceful shutdown
                try:
                    await asyncio.wait_for(process.wait(), timeout=5)
                except TimeoutError:
                    # Force kill
                    os.killpg(pgid, signal.SIGKILL)
                    await process.wait()
            except (ProcessLookupError, OSError):
                pass

            if audit:
                audit.log_execution(
                    command=command,
                    working_dir=str(cwd),
                    exit_code=None,
                    duration_ms=(time.monotonic() - start_time) * 1000,
                )

            return f"Error: Command timed out after {timeout_sec} seconds"

        # Decode output
        output = stdout.decode("utf-8", errors="replace")

        # Truncate if too large (dual truncation: lines AND bytes)
        truncated = False
        lines = output.split("\n")
        if len(lines) > MAX_OUTPUT_LINES:
            output = "\n".join(lines[:MAX_OUTPUT_LINES])
            truncated = True
        if len(output.encode("utf-8")) > MAX_OUTPUT_BYTES:
            output = output[:MAX_OUTPUT_BYTES].rsplit("\n", 1)[0]
            truncated = True

        if truncated:
            # Persist full output to temp file for retrieval
            full_output = stdout.decode("utf-8", errors="replace")
            with tempfile.NamedTemporaryFile(
                mode="w",
                prefix="rawagents_bash_",
                suffix=".txt",
                delete=False,
            ) as f:
                f.write(full_output)
                output_file = f.name

            output += (
                f"\n\n... (output truncated at {MAX_OUTPUT_LINES} lines / "
                f"{MAX_OUTPUT_BYTES // 1024}KB)\n"
                f"Full output saved to: {output_file}"
            )

        # Track working directory changes
        assert process.returncode is not None
        _update_working_directory_from_command(ctx, command, process.returncode)

        # Optionally reset to project directory after each command
        if ctx.maintain_project_working_dir and ctx._resolved_workspace:
            ctx._current_directory = ctx._resolved_workspace

        if audit:
            audit.log_execution(
                command=command,
                working_dir=str(cwd),
                exit_code=process.returncode,
                duration_ms=(time.monotonic() - start_time) * 1000,
                truncated=truncated,
            )

        # Format result
        if process.returncode == 0:
            return output.strip() if output.strip() else "(no output)"
        else:
            return f"Error: Command failed with exit code {process.returncode}\n{output.strip()}"

    except Exception as e:
        return f"Error: Failed to execute command: {e}"
