"""Tests for the bash_output tool.

Covers:
- Output retrieval from background processes
- Process status reporting
- Timeout behavior
- Process not found handling
"""

from __future__ import annotations

import asyncio

import pytest

from rawagents.tools.builtin.shell._security import ShellSecurityContext
from rawagents.tools.builtin.shell.bash import bash
from rawagents.tools.builtin.shell.bash_output import bash_output
from rawagents.tools.builtin.shell.kill_shell import kill_shell


class TestBashOutput:
    """Test bash_output tool."""

    async def test_read_output(self, shell_context: ShellSecurityContext) -> None:
        """Should retrieve output from background process."""
        result = await bash(
            "for i in 1 2 3; do echo line$i; sleep 0.1; done",
            run_in_background=True,
        )
        pid = result.split("PID: ")[1].strip()

        # Wait for some output
        await asyncio.sleep(0.5)

        output = await bash_output(pid=pid, timeout=2000)
        assert "line" in output

        # Clean up
        await kill_shell(pid=pid, force=True)

    async def test_process_status_running(
        self, shell_context: ShellSecurityContext
    ) -> None:
        """Should report running status for active process."""
        result = await bash("sleep 10", run_in_background=True)
        pid = result.split("PID: ")[1].strip()

        output = await bash_output(pid=pid, timeout=500)
        assert "running" in output.lower()

        # Clean up
        await kill_shell(pid=pid, force=True)

    async def test_process_status_completed(
        self, shell_context: ShellSecurityContext
    ) -> None:
        """Should report completed status for finished process."""
        result = await bash("echo done", run_in_background=True)
        pid = result.split("PID: ")[1].strip()

        # Wait for process to complete
        await asyncio.sleep(0.5)

        output = await bash_output(pid=pid, timeout=2000)
        assert "completed" in output.lower()

    async def test_process_not_found(
        self, shell_context: ShellSecurityContext
    ) -> None:
        """Should return error for unknown PID."""
        output = await bash_output(pid="99999999")
        assert "not found" in output.lower()

    async def test_timeout_returns_partial(
        self, shell_context: ShellSecurityContext
    ) -> None:
        """Should return available output even if timeout expires."""
        result = await bash(
            "echo fast; sleep 10",
            run_in_background=True,
        )
        pid = result.split("PID: ")[1].strip()

        # Wait for the fast output
        await asyncio.sleep(0.3)

        output = await bash_output(pid=pid, timeout=500)
        # Should have at least the status
        assert "Process status:" in output or "fast" in output

        # Clean up
        await kill_shell(pid=pid, force=True)
