"""Real-time output streaming for shell commands.

Based on asyncio best practices:
- Reference: https://docs.python.org/3/library/asyncio-subprocess.html
- Avoids deadlocks by consuming output continuously
- Supports callbacks for real-time processing
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable


__all__ = ["stream_output", "stream_with_timeout"]


async def stream_output(
    process: asyncio.subprocess.Process,
    on_line: Callable[[str], None] | None = None,
) -> AsyncIterator[str]:
    """Stream output from a subprocess line by line.

    Args:
        process: The asyncio subprocess.
        on_line: Optional callback invoked for each line (for real-time UI updates).

    Yields:
        Each line of output as it becomes available.

    Example:
        >>> process = await asyncio.create_subprocess_shell(
        ...     "npm run build",
        ...     stdout=asyncio.subprocess.PIPE,
        ...     stderr=asyncio.subprocess.STDOUT,
        ... )
        >>> async for line in stream_output(process, on_line=print):
        ...     pass  # Lines already printed by callback
    """
    if process.stdout is None:
        return

    while True:
        line = await process.stdout.readline()
        if not line:
            break

        decoded = line.decode("utf-8", errors="replace").rstrip("\n\r")

        if on_line:
            on_line(decoded)

        yield decoded


async def stream_with_timeout(
    process: asyncio.subprocess.Process,
    timeout_seconds: float,
    on_line: Callable[[str], None] | None = None,
) -> tuple[list[str], bool]:
    """Stream output with a timeout.

    Args:
        process: The asyncio subprocess.
        timeout_seconds: Maximum time to wait.
        on_line: Optional callback for each line.

    Returns:
        Tuple of (collected_lines, timed_out).

    Example:
        >>> lines, timed_out = await stream_with_timeout(process, 30.0)
        >>> if timed_out:
        ...     print("Command timed out!")
    """
    lines: list[str] = []
    timed_out = False

    async def collect() -> None:
        async for line in stream_output(process, on_line):
            lines.append(line)

    try:
        await asyncio.wait_for(
            asyncio.gather(collect(), process.wait()),
            timeout=timeout_seconds,
        )
    except TimeoutError:
        timed_out = True

    return lines, timed_out
