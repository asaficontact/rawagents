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

import pytest

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

    async def test_register_returns_pid(
        self, process_manager: ProcessManager
    ) -> None:
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

    async def test_get_output_not_found(
        self, process_manager: ProcessManager
    ) -> None:
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
