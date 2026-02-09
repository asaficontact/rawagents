"""Shared test fixtures for shell/command execution tools."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Generator

import pytest

from rawagents.tools.builtin.shell._process_manager import ProcessManager
from rawagents.tools.builtin.shell._security import (
    ShellSecurityContext,
    set_shell_security_context,
)


@pytest.fixture
def temp_workspace() -> Generator[Path, None, None]:
    """Create a temporary workspace directory.

    Yields:
        Path to the temporary workspace with test files:
        - test.sh: Simple shell script
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)

        # Create test files
        test_script = workspace / "test.sh"
        test_script.write_text("#!/bin/bash\necho 'hello'\n")
        test_script.chmod(0o755)

        yield workspace


@pytest.fixture
def shell_context(temp_workspace: Path) -> Generator[ShellSecurityContext, None, None]:
    """Create a shell security context.

    Yields:
        The configured ShellSecurityContext.
    """
    ctx = ShellSecurityContext(workspace=str(temp_workspace))
    set_shell_security_context(ctx)
    yield ctx


@pytest.fixture
def sandboxed_context(
    temp_workspace: Path,
) -> Generator[ShellSecurityContext, None, None]:
    """Create a sandboxed shell context.

    Note: Tests using this fixture may skip on systems without
    sandbox tools (bwrap / sandbox-exec).

    Yields:
        The configured ShellSecurityContext with sandbox enabled.
    """
    try:
        ctx = ShellSecurityContext(
            workspace=str(temp_workspace),
            enable_sandbox=True,
            sandbox_allow_network=False,
        )
    except Exception:
        pytest.skip("Sandbox tools not available on this system")
        return  # unreachable, but satisfies type-checker

    set_shell_security_context(ctx)
    yield ctx


@pytest.fixture
async def process_manager() -> ProcessManager:
    """Get a clean process manager.

    Yields:
        A fresh ProcessManager instance, cleaned up after the test.
    """
    manager = ProcessManager()
    yield manager  # type: ignore[misc]
    await manager.cleanup()
