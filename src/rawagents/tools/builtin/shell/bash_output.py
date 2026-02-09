"""BashOutput tool for reading background process output.

Retrieves new output from a background process started with
``bash(command, run_in_background=True)``.
"""

from __future__ import annotations

from typing import Annotated

from rawagents.tools import tool
from rawagents.tools.builtin.shell._process_manager import get_process_manager


__all__ = ["bash_output"]

MAX_OUTPUT_BYTES = 50 * 1024  # 50KB output limit


@tool
async def bash_output(
    pid: Annotated[str, "Process ID of the background command"],
    timeout: Annotated[int | None, "Timeout in ms to wait for new output"] = 5000,
) -> str:
    """Read output from a background bash command.

    Returns new output since the last read, along with process status.

    Args:
        pid: Process ID returned by ``bash(run_in_background=True)``.
        timeout: Maximum time to wait for new output in milliseconds.

    Returns:
        New output and process status, or error message.

    Example:
        >>> await bash_output(pid="12345", timeout=10000)
        'Compiling...\\n\\nProcess status: running'
    """
    manager = get_process_manager()
    output, status = await manager.get_output(pid, timeout=timeout or 5000)

    # Truncate output if too large
    if len(output.encode("utf-8")) > MAX_OUTPUT_BYTES:
        output = output[:MAX_OUTPUT_BYTES].rsplit("\n", 1)[0]
        output += "\n... (output truncated at 50KB)"

    if output.strip():
        return f"{output.rstrip()}\n\n{status}"
    else:
        return status
