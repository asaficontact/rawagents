"""Tests for the process manager.

Covers:
- ProcessInfo properties (is_running, exit_code)
- ProcessManager lifecycle (register, get_output, kill, cleanup)
- Buffer eviction (MAX_BUFFER_LINES enforcement)
- Singleton pattern (get_process_manager)
- Stream output utilities
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from rawagents.tools.builtin.shell._process_manager import (
    ProcessInfo,
    ProcessManager,
    get_process_manager,
)


class TestProcessInfo:
    """Test ProcessInfo dataclass properties."""

    async def test_is_running(self) -> None:
        """Running process should report is_running=True."""
        process = await asyncio.create_subprocess_shell(
            "sleep 10",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
        )
        info = ProcessInfo(pid=process.pid, process=process, command="sleep 10")

        assert info.is_running is True
        assert info.exit_code is None

        # Clean up
        process.terminate()
        await process.wait()

    async def test_completed_process(self) -> None:
        """Completed process should report is_running=False."""
        process = await asyncio.create_subprocess_shell(
            "echo done",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        await process.wait()

        info = ProcessInfo(pid=process.pid, process=process, command="echo done")

        assert info.is_running is False
        assert info.exit_code == 0


class TestProcessManager:
    """Test ProcessManager operations."""

    async def test_register_returns_pid(self, process_manager: ProcessManager) -> None:
        process = await asyncio.create_subprocess_shell(
            "sleep 5",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
        )
        pid = await process_manager.register(process, "sleep 5")
        assert pid == str(process.pid)

    async def test_get_output(self, process_manager: ProcessManager) -> None:
        process = await asyncio.create_subprocess_shell(
            "echo hello; echo world",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
        )
        pid = await process_manager.register(process, "echo hello; echo world")

        # Wait for output to be collected
        await asyncio.sleep(0.5)

        output, status = await process_manager.get_output(pid, timeout=2000)
        assert "hello" in output
        assert "world" in output

    async def test_get_output_not_found(self, process_manager: ProcessManager) -> None:
        output, status = await process_manager.get_output("99999999")
        assert "not found" in status.lower()

    async def test_kill(self, process_manager: ProcessManager) -> None:
        process = await asyncio.create_subprocess_shell(
            "sleep 100",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
        )
        pid = await process_manager.register(process, "sleep 100")

        result = await process_manager.kill(pid)
        assert "terminated successfully" in result

    async def test_cleanup(self, process_manager: ProcessManager) -> None:
        """cleanup should kill all tracked processes."""
        process1 = await asyncio.create_subprocess_shell(
            "sleep 100",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
        )
        process2 = await asyncio.create_subprocess_shell(
            "sleep 100",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
        )
        await process_manager.register(process1, "sleep 100")
        await process_manager.register(process2, "sleep 100")

        await process_manager.cleanup()

        # Both should be dead
        assert process1.returncode is not None
        assert process2.returncode is not None


class TestBufferEviction:
    """Test output buffer size enforcement."""

    async def test_buffer_bounded(self, process_manager: ProcessManager) -> None:
        """Buffer should not exceed MAX_BUFFER_LINES."""
        # Generate more lines than the buffer limit
        line_count = ProcessInfo.MAX_BUFFER_LINES + 100
        process = await asyncio.create_subprocess_shell(
            f"seq 1 {line_count}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
        )
        pid = await process_manager.register(process, f"seq 1 {line_count}")

        # Wait for all output
        await asyncio.sleep(3)

        # Check buffer size
        info = process_manager._processes.get(pid)
        if info:
            assert len(info.output_buffer) <= ProcessInfo.MAX_BUFFER_LINES


class TestSingleton:
    """Test get_process_manager singleton."""

    def test_returns_same_instance(self) -> None:
        pm1 = get_process_manager()
        pm2 = get_process_manager()
        assert pm1 is pm2


class TestShellSession:
    """Test named shell session support."""

    async def test_create_session(self, process_manager: ProcessManager) -> None:
        """get_or_create_session should return a new session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session = await process_manager.get_or_create_session("test", tmpdir)
            assert session.name == "test"
            assert session.is_alive
            await process_manager.close_session("test")

    async def test_reuse_existing_session(
        self, process_manager: ProcessManager
    ) -> None:
        """get_or_create_session should reuse an alive session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            s1 = await process_manager.get_or_create_session("reuse", tmpdir)
            s2 = await process_manager.get_or_create_session("reuse", tmpdir)
            assert s1 is s2
            await process_manager.close_session("reuse")

    async def test_recreate_dead_session(self, process_manager: ProcessManager) -> None:
        """Dead session should be replaced by a new one."""
        with tempfile.TemporaryDirectory() as tmpdir:
            s1 = await process_manager.get_or_create_session("dead", tmpdir)
            # Kill the process
            s1.process.terminate()
            await s1.process.wait()
            assert not s1.is_alive

            s2 = await process_manager.get_or_create_session("dead", tmpdir)
            assert s2 is not s1
            assert s2.is_alive
            await process_manager.close_session("dead")

    async def test_execute_in_session(self, process_manager: ProcessManager) -> None:
        """execute_in_session should run command and return output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session = await process_manager.get_or_create_session("exec", tmpdir)
            output, exit_code = await process_manager.execute_in_session(
                session, "echo hello"
            )
            assert exit_code == 0
            assert "hello" in output
            await process_manager.close_session("exec")

    async def test_session_preserves_working_dir(
        self, process_manager: ProcessManager
    ) -> None:
        """cd in a session should persist for subsequent commands."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir) / "sub"
            subdir.mkdir()

            session = await process_manager.get_or_create_session("cd", tmpdir)
            await process_manager.execute_in_session(session, f"cd {subdir}")
            output, code = await process_manager.execute_in_session(session, "pwd")
            assert code == 0
            # macOS: /var -> /private/var, so compare both resolved forms
            assert (
                str(subdir) in output
                or str(subdir.resolve()) in output
                or str(Path(output.strip()).resolve()) == str(subdir.resolve())
            )
            await process_manager.close_session("cd")

    async def test_session_preserves_env_vars(
        self, process_manager: ProcessManager
    ) -> None:
        """Exported env vars should persist across commands in a session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session = await process_manager.get_or_create_session("env", tmpdir)
            await process_manager.execute_in_session(
                session, "export MY_TEST_VAR=hello123"
            )
            output, code = await process_manager.execute_in_session(
                session, "echo $MY_TEST_VAR"
            )
            assert code == 0
            assert "hello123" in output
            await process_manager.close_session("env")

    async def test_close_session(self, process_manager: ProcessManager) -> None:
        """close_session should terminate the process."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session = await process_manager.get_or_create_session("close", tmpdir)
            result = await process_manager.close_session("close")
            assert "closed" in result.lower()
            assert not session.is_alive

    async def test_close_nonexistent_session(
        self, process_manager: ProcessManager
    ) -> None:
        """close_session on unknown name should return not found."""
        result = await process_manager.close_session("nonexistent")
        assert "not found" in result.lower()

    async def test_list_sessions(self, process_manager: ProcessManager) -> None:
        """list_sessions should return name->alive mapping."""
        with tempfile.TemporaryDirectory() as tmpdir:
            await process_manager.get_or_create_session("s1", tmpdir)
            await process_manager.get_or_create_session("s2", tmpdir)

            listing = process_manager.list_sessions()
            assert "s1" in listing
            assert "s2" in listing
            assert listing["s1"] is True
            assert listing["s2"] is True

            await process_manager.close_session("s1")
            await process_manager.close_session("s2")

    async def test_cleanup_closes_sessions(
        self, process_manager: ProcessManager
    ) -> None:
        """cleanup should close all sessions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            s1 = await process_manager.get_or_create_session("c1", tmpdir)
            s2 = await process_manager.get_or_create_session("c2", tmpdir)

            await process_manager.cleanup()

            assert not s1.is_alive
            assert not s2.is_alive
            assert len(process_manager.list_sessions()) == 0


class TestStreamOutput:
    """Test streaming output utilities."""

    async def test_stream_output(self) -> None:
        from rawagents.tools.builtin.shell._utils import stream_output

        process = await asyncio.create_subprocess_shell(
            "echo line1; echo line2; echo line3",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        lines: list[str] = []
        async for line in stream_output(process):
            lines.append(line)

        assert "line1" in lines
        assert "line2" in lines
        assert "line3" in lines

    async def test_stream_with_callback(self) -> None:
        from rawagents.tools.builtin.shell._utils import stream_output

        process = await asyncio.create_subprocess_shell(
            "echo a; echo b",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        callback_lines: list[str] = []
        async for _ in stream_output(process, on_line=callback_lines.append):
            pass

        assert len(callback_lines) >= 2

    async def test_stream_with_timeout(self) -> None:
        from rawagents.tools.builtin.shell._utils import stream_with_timeout

        process = await asyncio.create_subprocess_shell(
            "echo fast; sleep 100",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        lines, timed_out = await stream_with_timeout(process, 0.5)
        assert timed_out is True
        assert any("fast" in line for line in lines)

        # Clean up
        process.terminate()
        await process.wait()
