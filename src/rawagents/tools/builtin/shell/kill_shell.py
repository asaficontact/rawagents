"""KillShell tool for terminating background processes.

Terminates a running shell process started with
``bash(command, run_in_background=True)``.
"""

from __future__ import annotations

from typing import Annotated

from rawagents.tools import tool
from rawagents.tools.builtin.shell._process_manager import get_process_manager


__all__ = ["kill_shell"]


@tool
async def kill_shell(
    pid: Annotated[str, "Process ID to terminate"],
    force: Annotated[bool, "Use SIGKILL instead of SIGTERM"] = False,
) -> str:
    """Terminate a running shell process.

    Default behaviour sends SIGTERM for graceful shutdown. If the process
    does not exit within 5 seconds, SIGKILL is sent automatically.

    Use ``force=True`` for immediate SIGKILL termination.

    Args:
        pid: Process ID to terminate.
        force: If True, use SIGKILL instead of SIGTERM.

    Returns:
        Result message indicating success or error.

    Example:
        >>> await kill_shell(pid="12345")
        'Process 12345 terminated successfully'

        >>> await kill_shell(pid="12345", force=True)
        'Process 12345 terminated successfully'
    """
    manager = get_process_manager()
    return await manager.kill(pid, force=force)
