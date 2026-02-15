"""Process manager for tracking background shell processes.

This module provides a registry for background processes, enabling:
- Output retrieval for running processes
- Process termination
- Cleanup of completed processes
"""

from __future__ import annotations

import asyncio
import os
import signal
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar


__all__ = ["ProcessInfo", "ProcessManager", "ShellSession", "get_process_manager"]


@dataclass
class ProcessInfo:
    """Information about a tracked process."""

    pid: int
    process: asyncio.subprocess.Process
    command: str
    started_at: datetime = field(default_factory=datetime.now)
    output_buffer: list[str] = field(default_factory=list)
    last_read_index: int = 0

    MAX_BUFFER_LINES: ClassVar[int] = 10_000  # Prevent unbounded memory growth

    _new_output_event: asyncio.Event = field(
        default_factory=asyncio.Event, init=False, repr=False
    )
    _collect_task: asyncio.Task[None] | None = field(
        default=None, init=False, repr=False
    )

    @property
    def is_running(self) -> bool:
        """Check if process is still running."""
        return self.process.returncode is None

    @property
    def exit_code(self) -> int | None:
        """Get exit code if process has completed."""
        return self.process.returncode


@dataclass
class ShellSession:
    """A persistent interactive shell session.

    Allows commands to share environment state (cd, env vars, venv).
    Uses sentinel-based output detection to know when a command finishes.

    Attributes:
        name: User-chosen session name (e.g., "build", "test").
        process: The underlying shell subprocess.
        lock: Per-session lock to serialize command execution.
        created_at: When the session was created.
    """

    name: str
    process: asyncio.subprocess.Process
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def is_alive(self) -> bool:
        """Check if the shell process is still running."""
        return self.process.returncode is None


class ProcessManager:
    """Manages background shell processes.

    This class maintains a registry of all background processes started
    by the bash tool, enabling output retrieval and termination.

    Thread-safety: Uses asyncio locks for concurrent access.
    """

    def __init__(self) -> None:
        self._processes: dict[str, ProcessInfo] = {}
        self._sessions: dict[str, ShellSession] = {}
        self._lock = asyncio.Lock()

    async def register(
        self,
        process: asyncio.subprocess.Process,
        command: str,
    ) -> str:
        """Register a new background process.

        Args:
            process: The asyncio subprocess.
            command: The command that was executed.

        Returns:
            Process ID as string.
        """
        pid = str(process.pid)
        async with self._lock:
            self._processes[pid] = ProcessInfo(
                pid=process.pid,
                process=process,
                command=command,
            )

        # Start background task to collect output.
        # We store the reference on the ProcessInfo to prevent GC.
        info = self._processes[pid]
        info._collect_task = asyncio.create_task(self._collect_output(pid))

        return pid

    async def _collect_output(self, pid: str) -> None:
        """Collect output from a background process.

        Signals ``_new_output_event`` on each new line so that
        ``get_output()`` can wake up immediately instead of polling.
        """
        async with self._lock:
            info = self._processes.get(pid)
            if not info:
                return

        try:
            while True:
                if info.process.stdout:
                    line = await info.process.stdout.readline()
                    if not line:
                        break
                    async with self._lock:
                        info.output_buffer.append(
                            line.decode("utf-8", errors="replace")
                        )
                        # Evict oldest lines when buffer exceeds limit
                        if len(info.output_buffer) > info.MAX_BUFFER_LINES:
                            overflow = len(info.output_buffer) - info.MAX_BUFFER_LINES
                            del info.output_buffer[:overflow]
                            info.last_read_index = max(
                                0, info.last_read_index - overflow
                            )
                    # Signal that new output is available
                    info._new_output_event.set()
                else:
                    break
        except Exception:
            pass

        # Wait for process to complete
        await info.process.wait()
        # Final signal so any waiting get_output() call returns immediately
        info._new_output_event.set()

    async def get_output(self, pid: str, timeout: int = 5000) -> tuple[str, str]:
        """Get new output from a process.

        Uses event-based waiting: returns as soon as new output is available
        rather than sleeping for the full timeout duration.

        Args:
            pid: Process ID.
            timeout: Maximum time to wait for new output, in milliseconds.

        Returns:
            Tuple of (new_output, status_message).
        """
        async with self._lock:
            info = self._processes.get(pid)
            if not info:
                return "", "Error: Process not found"

        # Wait for new output OR timeout
        try:
            info._new_output_event.clear()
            await asyncio.wait_for(
                info._new_output_event.wait(), timeout=timeout / 1000
            )
        except TimeoutError:
            pass  # Timeout is fine — return whatever we have

        async with self._lock:
            # Get new output since last read
            new_lines = info.output_buffer[info.last_read_index :]
            info.last_read_index = len(info.output_buffer)

            output = "".join(new_lines)

            # Build status message
            if info.is_running:
                status = "Process status: running"
            else:
                status = f"Process status: completed (exit code {info.exit_code})"

        return output, status

    async def kill(self, pid: str, force: bool = False) -> str:
        """Kill a process.

        Args:
            pid: Process ID.
            force: Use SIGKILL instead of SIGTERM.

        Returns:
            Result message.
        """
        async with self._lock:
            info = self._processes.get(pid)
            if not info:
                return f"Error: Process {pid} not found"

        if not info.is_running:
            async with self._lock:
                del self._processes[pid]
            return f"Process {pid} already terminated"

        try:
            # Kill process group to include children
            pgid = os.getpgid(info.process.pid)

            if force:
                os.killpg(pgid, signal.SIGKILL)
            else:
                os.killpg(pgid, signal.SIGTERM)

                # Wait for graceful shutdown
                try:
                    await asyncio.wait_for(info.process.wait(), timeout=5)
                except TimeoutError:
                    # Force kill if still running
                    os.killpg(pgid, signal.SIGKILL)

            await info.process.wait()

        except ProcessLookupError:
            pass  # Already dead
        except OSError as e:
            return f"Error: Failed to kill process {pid}: {e}"

        async with self._lock:
            if pid in self._processes:
                del self._processes[pid]

        return f"Process {pid} terminated successfully"

    async def get_or_create_session(
        self,
        name: str,
        cwd: str,
        env: dict[str, str] | None = None,
    ) -> ShellSession:
        """Get an existing session or create a new one.

        If a session exists but its process has died, it is replaced.

        Args:
            name: Session name (user-chosen).
            cwd: Working directory for new sessions.
            env: Optional environment variables for new sessions.

        Returns:
            The (possibly new) ShellSession.
        """
        existing = self._sessions.get(name)
        if existing is not None and existing.is_alive:
            return existing

        # Dead or nonexistent — create a new one
        process = await asyncio.create_subprocess_exec(
            "bash", "--norc", "--noprofile",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=cwd,
            env=env,
            start_new_session=True,
        )
        session = ShellSession(name=name, process=process)
        self._sessions[name] = session
        return session

    async def execute_in_session(
        self,
        session: ShellSession,
        command: str,
        timeout_sec: float = 120,
    ) -> tuple[str, int]:
        """Execute a command in a named session using sentinel-based detection.

        The sentinel pattern (borrowed from SWE-ReX) appends a unique marker
        to the command's output so we know exactly when it finishes and what
        exit code it produced.

        Args:
            session: The session to execute in.
            command: The shell command to run.
            timeout_sec: Maximum seconds to wait.

        Returns:
            Tuple of (output, exit_code). exit_code is -1 on timeout.
        """
        sentinel = f"___SENTINEL_{uuid.uuid4().hex[:8]}___"

        async with session.lock:
            assert session.process.stdin is not None
            assert session.process.stdout is not None

            # Send command with sentinel marker that echoes exit code
            full_cmd = f'{command}; echo "{sentinel}$?"\n'
            session.process.stdin.write(full_cmd.encode())
            await session.process.stdin.drain()

            # Read until sentinel appears
            output_lines: list[str] = []
            try:
                async with asyncio.timeout(timeout_sec):
                    while True:
                        line_bytes = await session.process.stdout.readline()
                        if not line_bytes:
                            # Process died
                            return "\n".join(output_lines), -1
                        decoded = line_bytes.decode("utf-8", errors="replace").rstrip("\n")
                        if decoded.startswith(sentinel):
                            exit_code_str = decoded[len(sentinel):]
                            try:
                                exit_code = int(exit_code_str)
                            except ValueError:
                                exit_code = -1
                            return "\n".join(output_lines), exit_code
                        output_lines.append(decoded)
            except TimeoutError:
                return "\n".join(output_lines) + "\n\nError: Command timed out", -1

    async def close_session(self, name: str) -> str:
        """Close a named session.

        Args:
            name: Session name.

        Returns:
            Result message.
        """
        session = self._sessions.pop(name, None)
        if session is None:
            return f"Session '{name}' not found"

        if session.is_alive:
            session.process.terminate()
            try:
                await asyncio.wait_for(session.process.wait(), timeout=5)
            except TimeoutError:
                session.process.kill()
                await session.process.wait()

        return f"Session '{name}' closed"

    def list_sessions(self) -> dict[str, bool]:
        """List all sessions and their alive status.

        Returns:
            Dict mapping session name to is_alive status.
        """
        return {name: session.is_alive for name, session in self._sessions.items()}

    async def cleanup(self) -> None:
        """Clean up all tracked processes and sessions."""
        async with self._lock:
            pids = list(self._processes.keys())

        for pid in pids:
            await self.kill(pid, force=True)

        # Also close all sessions
        session_names = list(self._sessions.keys())
        for name in session_names:
            await self.close_session(name)


# Global process manager instance.
#
# DESIGN DECISION: ProcessManager is intentionally a module-level singleton
# rather than using contextvars.ContextVar (like ShellSecurityContext does).
#
# Rationale: OS processes are inherently global — there is one process table
# shared across all async contexts. A background process started in one
# coroutine must be killable from another.
_process_manager: ProcessManager | None = None


def get_process_manager() -> ProcessManager:
    """Get the global process manager (singleton).

    Returns the same instance across all async contexts, enabling
    cross-coroutine process management.
    """
    global _process_manager  # noqa: PLW0603
    if _process_manager is None:
        _process_manager = ProcessManager()
    return _process_manager
