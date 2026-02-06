"""Tests for the file locking module."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from rawagents.tools.builtin.fs._locking import (
    file_lock,
    FileLockError,
)


class TestFileLock:
    """Test async file locking."""

    @pytest.mark.asyncio
    async def test_acquires_exclusive_lock(
        self, temp_workspace: Path
    ) -> None:
        """Should acquire exclusive lock on file."""
        test_file = temp_workspace / "locktest.txt"
        test_file.write_text("original content")

        async with file_lock(test_file, exclusive=True):
            # Should be able to read and write while holding lock
            content = test_file.read_text()
            test_file.write_text(content + " modified")

        assert "modified" in test_file.read_text()

    @pytest.mark.asyncio
    async def test_raises_on_nonexistent_file(
        self, temp_workspace: Path
    ) -> None:
        """Should raise FileNotFoundError for nonexistent files."""
        nonexistent = temp_workspace / "nonexistent.txt"

        with pytest.raises(FileNotFoundError):
            async with file_lock(nonexistent):
                pass

    @pytest.mark.asyncio
    async def test_releases_lock_on_exit(
        self, temp_workspace: Path
    ) -> None:
        """Should release lock when exiting context."""
        test_file = temp_workspace / "release_test.txt"
        test_file.write_text("content")

        async with file_lock(test_file):
            pass

        # Should be able to lock again after release
        async with file_lock(test_file):
            pass

    @pytest.mark.asyncio
    async def test_releases_lock_on_exception(
        self, temp_workspace: Path
    ) -> None:
        """Should release lock even when exception occurs."""
        test_file = temp_workspace / "exception_test.txt"
        test_file.write_text("content")

        try:
            async with file_lock(test_file):
                raise ValueError("Test error")
        except ValueError:
            pass

        # Should be able to lock again
        async with file_lock(test_file):
            pass


class TestConcurrentLocking:
    """Test concurrent access with file locking."""

    @pytest.mark.asyncio
    async def test_concurrent_writes_are_serialized(
        self, temp_workspace: Path
    ) -> None:
        """Concurrent writers should be serialized by locking."""
        test_file = temp_workspace / "concurrent.txt"
        test_file.write_text("0")

        results: list[str] = []

        async def writer(value: str) -> None:
            async with file_lock(test_file, exclusive=True):
                content = test_file.read_text()
                results.append(f"read:{content}")
                await asyncio.sleep(0.01)  # Simulate work
                test_file.write_text(value)
                results.append(f"wrote:{value}")

        # Launch two concurrent writers
        await asyncio.gather(writer("A"), writer("B"))

        # Both should have completed — final value should be one of them
        final = test_file.read_text()
        assert final in ("A", "B")
        # Should have 4 entries: two reads and two writes
        assert len(results) == 4

    @pytest.mark.asyncio
    async def test_shared_read_locks(
        self, temp_workspace: Path
    ) -> None:
        """Multiple readers should be able to hold shared locks."""
        test_file = temp_workspace / "shared.txt"
        test_file.write_text("shared content")

        read_count = 0

        async def reader() -> str:
            nonlocal read_count
            async with file_lock(test_file, exclusive=False):
                read_count += 1
                return test_file.read_text()

        # Launch multiple concurrent readers
        results = await asyncio.gather(reader(), reader(), reader())

        assert all(r == "shared content" for r in results)
        assert read_count == 3


class TestFileLockError:
    """Test FileLockError class."""

    def test_error_attributes(self) -> None:
        """Should store path and reason."""
        path = Path("/test/path")
        error = FileLockError(path, "test reason")

        assert error.path == path
        assert error.reason == "test reason"
        assert "/test/path" in str(error)
        assert "test reason" in str(error)
