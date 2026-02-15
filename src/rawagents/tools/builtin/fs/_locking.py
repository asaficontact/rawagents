"""Cross-platform file locking for TOCTOU protection.

This module provides async-friendly file locking to prevent Time-Of-Check
to Time-Of-Use (TOCTOU) race conditions during read-modify-write operations.

The locking mechanism uses:
- fcntl.flock() on Unix/Linux/macOS
- msvcrt.locking() on Windows

Usage:
    >>> async with file_lock(path, exclusive=True):
    ...     content = path.read_text()
    ...     # ... modify content ...
    ...     path.write_text(new_content)
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
from collections.abc import AsyncIterator
from pathlib import Path


__all__ = ["FileLockError", "file_lock"]


class FileLockError(OSError):
    """Raised when file locking fails.

    Attributes:
        path: The path that could not be locked.
        reason: Description of why locking failed.
    """

    def __init__(self, path: Path, reason: str):
        super().__init__(f"Cannot lock {path}: {reason}")
        self.path = path
        self.reason = reason


class _FileLock:
    """Internal file lock implementation.

    Wraps platform-specific locking mechanisms in a unified interface.
    """

    def __init__(self, path: Path, exclusive: bool = True):
        self.path = path
        self.exclusive = exclusive
        self._fd: int | None = None

    def acquire(self) -> None:
        """Acquire the file lock (blocking)."""
        import os

        if not self.path.exists():
            raise FileLockError(self.path, "file does not exist")

        try:
            self._fd = os.open(str(self.path), os.O_RDWR)
        except OSError as e:
            raise FileLockError(self.path, f"cannot open file: {e}") from e

        try:
            if sys.platform == "win32":
                self._lock_windows()
            else:
                self._lock_unix()
        except OSError as e:
            # Clean up fd on failure
            if self._fd is not None:
                os.close(self._fd)
                self._fd = None
            raise FileLockError(self.path, f"locking failed: {e}") from e

    def release(self) -> None:
        """Release the file lock."""
        import os

        if self._fd is None:
            return

        try:
            if sys.platform == "win32":
                self._unlock_windows()
            else:
                self._unlock_unix()
        finally:
            os.close(self._fd)
            self._fd = None

    def _lock_unix(self) -> None:
        """Lock using fcntl on Unix systems."""
        import fcntl

        operation = fcntl.LOCK_EX if self.exclusive else fcntl.LOCK_SH
        fcntl.flock(self._fd, operation)

    def _unlock_unix(self) -> None:
        """Unlock using fcntl on Unix systems."""
        import fcntl

        fcntl.flock(self._fd, fcntl.LOCK_UN)

    def _lock_windows(self) -> None:
        """Lock using msvcrt on Windows."""
        import msvcrt
        import os

        # Get file size for locking entire file
        size = os.fstat(self._fd).st_size
        if size == 0:
            size = 1  # Lock at least 1 byte

        # LK_NBLCK = non-blocking exclusive lock
        # LK_NBRLCK = non-blocking shared lock (read lock)
        mode = msvcrt.LK_NBLCK if self.exclusive else msvcrt.LK_NBRLCK
        msvcrt.locking(self._fd, mode, size)

    def _unlock_windows(self) -> None:
        """Unlock using msvcrt on Windows."""
        import msvcrt
        import os

        size = os.fstat(self._fd).st_size
        if size == 0:
            size = 1
        msvcrt.locking(self._fd, msvcrt.LK_UNLCK, size)


@contextlib.asynccontextmanager
async def file_lock(
    path: Path,
    exclusive: bool = True,
    timeout: float = 5.0,
) -> AsyncIterator[None]:
    """Async context manager for file locking.

    Provides TOCTOU protection by holding a file lock during read-modify-write
    operations. The lock is acquired before entering the context and released
    when exiting.

    Args:
        path: Path to the file to lock. Must exist.
        exclusive: If True (default), acquire an exclusive write lock.
                   If False, acquire a shared read lock.
        timeout: Maximum time to wait for the lock in seconds.

    Yields:
        None - the file can be safely read/modified within the context.

    Raises:
        FileLockError: If the file cannot be locked.
        FileNotFoundError: If the file does not exist.
        asyncio.TimeoutError: If the lock cannot be acquired within timeout.

    Example:
        >>> async with file_lock(Path("myfile.txt"), exclusive=True):
        ...     content = Path("myfile.txt").read_text()
        ...     content = content.replace("old", "new")
        ...     Path("myfile.txt").write_text(content)
    """
    if not path.exists():
        raise FileNotFoundError(f"Cannot lock non-existent file: {path}")

    lock = _FileLock(path, exclusive)

    # Run blocking lock acquisition in thread pool
    loop = asyncio.get_event_loop()
    try:
        await asyncio.wait_for(
            loop.run_in_executor(None, lock.acquire),
            timeout=timeout,
        )
    except TimeoutError:
        raise TimeoutError(f"Timeout waiting for lock on {path}")

    try:
        yield
    finally:
        # Release lock in thread pool
        await loop.run_in_executor(None, lock.release)



