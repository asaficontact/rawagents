"""Tests for the kill_shell tool.

Covers:
- Graceful termination (SIGTERM)
- Forced termination (SIGKILL)
- Process not found handling
- Already terminated processes
"""

from __future__ import annotations

import asyncio

from rawagents.tools.builtin.shell._security import ShellSecurityContext
from rawagents.tools.builtin.shell.bash import bash
from rawagents.tools.builtin.shell.kill_shell import kill_shell


class TestKillShell:
    """Test kill_shell tool."""

    async def test_graceful_kill(self, shell_context: ShellSecurityContext) -> None:
        """SIGTERM should terminate the process."""
        result = await bash("sleep 100", run_in_background=True)
        pid = result.split("PID: ")[1].strip()

        kill_result = await kill_shell(pid=pid)
        assert "terminated successfully" in kill_result

    async def test_force_kill(self, shell_context: ShellSecurityContext) -> None:
        """SIGKILL should immediately terminate the process."""
        result = await bash("sleep 100", run_in_background=True)
        pid = result.split("PID: ")[1].strip()

        kill_result = await kill_shell(pid=pid, force=True)
        assert "terminated successfully" in kill_result

    async def test_kill_nonexistent(
        self, shell_context: ShellSecurityContext
    ) -> None:
        """Killing a nonexistent process should return error."""
        result = await kill_shell(pid="99999999")
        assert "not found" in result.lower()

    async def test_kill_already_terminated(
        self, shell_context: ShellSecurityContext
    ) -> None:
        """Killing an already-terminated process should handle gracefully."""
        result = await bash("echo done", run_in_background=True)
        pid = result.split("PID: ")[1].strip()

        # Wait for process to complete
        await asyncio.sleep(0.5)

        kill_result = await kill_shell(pid=pid)
        # Should either say "already terminated" or "terminated successfully"
        assert "terminated" in kill_result.lower()


class TestKillShellLifecycle:
    """Test full lifecycle: start -> output -> kill."""

    async def test_full_lifecycle(
        self, shell_context: ShellSecurityContext
    ) -> None:
        """Test background process lifecycle: start -> read -> kill -> verify."""
        from rawagents.tools.builtin.shell.bash_output import bash_output

        # 1. Start
        result = await bash(
            "for i in $(seq 1 100); do echo line$i; sleep 0.05; done",
            run_in_background=True,
        )
        pid = result.split("PID: ")[1].strip()

        # 2. Read output
        await asyncio.sleep(0.3)
        output = await bash_output(pid=pid, timeout=1000)
        assert "line" in output

        # 3. Kill
        kill_result = await kill_shell(pid=pid)
        assert "terminated" in kill_result.lower()

        # 4. Verify dead
        output = await bash_output(pid=pid)
        assert "not found" in output.lower()
