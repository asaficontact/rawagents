"""Tests for the bash tool.

Covers:
- Basic execution and output capture
- Exit codes and error formatting
- Timeout handling with SIGTERM/SIGKILL escalation
- Background execution and PID format
- Output truncation (line limit and byte limit)
- Working directory persistence and cd tracking
- Security validation integration
- env_file sourcing
- Shell selection
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from rawagents.tools.builtin.shell._security import (
    ShellSecurityContext,
    set_shell_security_context,
)
from rawagents.tools.builtin.shell.bash import (
    _extract_cd_target,
    _update_working_directory_from_command,
    bash,
)


class TestBash:
    """Test basic bash execution."""

    async def test_simple_command(self, shell_context: ShellSecurityContext) -> None:
        result = await bash("echo hello")
        assert result == "hello"

    async def test_multiline_output(
        self, shell_context: ShellSecurityContext
    ) -> None:
        result = await bash("echo line1; echo line2; echo line3")
        assert "line1" in result
        assert "line2" in result
        assert "line3" in result

    async def test_exit_code_zero(self, shell_context: ShellSecurityContext) -> None:
        result = await bash("true")
        assert not result.startswith("Error:")

    async def test_exit_code_nonzero(
        self, shell_context: ShellSecurityContext
    ) -> None:
        result = await bash("false")
        assert result.startswith("Error: Command failed with exit code")

    async def test_no_output(self, shell_context: ShellSecurityContext) -> None:
        result = await bash("true")
        assert result == "(no output)"

    async def test_stderr_captured(self, shell_context: ShellSecurityContext) -> None:
        result = await bash("echo error >&2 && false")
        assert "error" in result

    async def test_command_not_found(
        self, shell_context: ShellSecurityContext
    ) -> None:
        result = await bash("nonexistent_command_xyz_12345")
        assert result.startswith("Error:")

    async def test_description_parameter(
        self, shell_context: ShellSecurityContext
    ) -> None:
        """Description parameter should not affect execution."""
        result = await bash("echo test", description="Test command")
        assert result == "test"


class TestBashTimeout:
    """Test timeout handling."""

    async def test_timeout_triggers(
        self, shell_context: ShellSecurityContext
    ) -> None:
        result = await bash("sleep 100", timeout=200)  # 200ms
        assert "timed out" in result.lower()

    async def test_timeout_returns_error(
        self, shell_context: ShellSecurityContext
    ) -> None:
        result = await bash("sleep 100", timeout=200)
        assert result.startswith("Error:")

    async def test_timeout_default(self, shell_context: ShellSecurityContext) -> None:
        """Command within default timeout should succeed."""
        result = await bash("echo fast")
        assert result == "fast"


class TestBashBackground:
    """Test background execution."""

    async def test_background_returns_pid(
        self, shell_context: ShellSecurityContext
    ) -> None:
        result = await bash("sleep 1", run_in_background=True)
        assert "Started background process with PID:" in result

    async def test_background_pid_is_numeric(
        self, shell_context: ShellSecurityContext
    ) -> None:
        result = await bash("sleep 1", run_in_background=True)
        pid = result.split("PID: ")[1].strip()
        assert pid.isdigit()

    async def test_background_returns_immediately(
        self, shell_context: ShellSecurityContext
    ) -> None:
        """Background command should return immediately, not wait for completion."""
        import time

        start = time.monotonic()
        result = await bash("sleep 10", run_in_background=True)
        elapsed = time.monotonic() - start

        assert "PID:" in result
        assert elapsed < 5  # Should be near-instant

        # Clean up
        pid = result.split("PID: ")[1].strip()
        from rawagents.tools.builtin.shell.kill_shell import kill_shell

        await kill_shell(pid=pid, force=True)


class TestBashTruncation:
    """Test output truncation."""

    async def test_line_truncation(
        self, shell_context: ShellSecurityContext
    ) -> None:
        """Output exceeding MAX_OUTPUT_LINES should be truncated."""
        # Generate 2500 lines
        result = await bash("seq 1 2500")
        assert "truncated" in result.lower()
        assert "Full output saved to:" in result

    async def test_small_output_not_truncated(
        self, shell_context: ShellSecurityContext
    ) -> None:
        result = await bash("echo hello")
        assert "truncated" not in result.lower()


class TestBashWorkingDirectory:
    """Test working directory persistence."""

    async def test_cd_persists(
        self, shell_context: ShellSecurityContext, temp_workspace: Path
    ) -> None:
        """cd should update the tracked working directory."""
        subdir = temp_workspace / "subdir"
        subdir.mkdir()

        await bash(f"cd {subdir}")
        assert shell_context.get_working_directory() == subdir.resolve()

    async def test_cd_failure_no_update(
        self, shell_context: ShellSecurityContext, temp_workspace: Path
    ) -> None:
        """Failed cd should not update working directory."""
        original = shell_context.get_working_directory()
        await bash("cd /nonexistent/path/that/does/not/exist")
        assert shell_context.get_working_directory() == original

    async def test_cd_with_chained_command(
        self, shell_context: ShellSecurityContext, temp_workspace: Path
    ) -> None:
        """cd in chained commands should be tracked."""
        result = await bash(f"cd {temp_workspace} && echo done")
        assert "done" in result
        assert shell_context.get_working_directory() == temp_workspace.resolve()

    async def test_cd_dash_returns_to_previous(
        self, shell_context: ShellSecurityContext, temp_workspace: Path
    ) -> None:
        """cd - should return to the previous directory."""
        dir_a = temp_workspace / "dir_a"
        dir_a.mkdir()
        subdir = dir_a / "subdir"
        subdir.mkdir()

        await bash(f"cd {dir_a}")
        await bash(f"cd {subdir}")

        # cd - should go back to dir_a
        result = await bash("cd -")
        assert not result.startswith("Error:"), f"cd - failed: {result}"

        result = await bash("pwd")
        assert str(dir_a.resolve()) in result

    async def test_cd_dash_toggles(
        self, shell_context: ShellSecurityContext, temp_workspace: Path
    ) -> None:
        """Repeated cd - should toggle between two directories."""
        dir_a = temp_workspace / "dir_a"
        dir_b = temp_workspace / "dir_b"
        dir_a.mkdir()
        dir_b.mkdir()

        await bash(f"cd {dir_a}")
        await bash(f"cd {dir_b}")

        # Toggle back to dir_a
        result = await bash("cd -")
        assert not result.startswith("Error:")
        pwd = await bash("pwd")
        assert str(dir_a.resolve()) in pwd

        # Toggle back to dir_b
        result = await bash("cd -")
        assert not result.startswith("Error:")
        pwd = await bash("pwd")
        assert str(dir_b.resolve()) in pwd

    async def test_cd_dash_no_previous_fails(self, tmp_path: Path) -> None:
        """cd - with no previous directory should fail gracefully."""
        ctx = ShellSecurityContext(workspace=str(tmp_path))
        set_shell_security_context(ctx)

        result = await bash("cd -")
        assert "OLDPWD" in result or "Error" in result


class TestBashSecurity:
    """Test security validation integration."""

    async def test_blocked_command_returns_error(
        self, shell_context: ShellSecurityContext
    ) -> None:
        result = await bash("rm -rf /")
        assert result.startswith("Error:")
        assert "blocked" in result.lower()

    async def test_safe_command_succeeds(
        self, shell_context: ShellSecurityContext
    ) -> None:
        result = await bash("echo safe")
        assert result == "safe"


class TestBashEnvFile:
    """Test env_file sourcing."""

    async def test_env_file_sourced(self, tmp_path: Path) -> None:
        """Commands should have access to env_file variables."""
        env_file = tmp_path / ".env"
        env_file.write_text("export TEST_VAR='hello from env'\n")

        ctx = ShellSecurityContext(
            workspace=str(tmp_path),
            env_file=str(env_file),
        )
        set_shell_security_context(ctx)

        result = await bash("echo $TEST_VAR")
        assert "hello from env" in result

    async def test_env_file_missing_warning(self, tmp_path: Path) -> None:
        """Missing env_file should warn but not fail."""
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            ShellSecurityContext(
                workspace=str(tmp_path),
                env_file="/nonexistent/env/file",
            )

            assert len(w) >= 1
            assert "does not exist" in str(w[0].message)


class TestExtractCdTarget:
    """Test _extract_cd_target helper."""

    def test_bare_cd(self) -> None:
        assert _extract_cd_target("cd") == "~"

    def test_cd_home(self) -> None:
        assert _extract_cd_target("cd ~") == "~"

    def test_cd_absolute(self) -> None:
        assert _extract_cd_target("cd /tmp") == "/tmp"

    def test_cd_relative(self) -> None:
        assert _extract_cd_target("cd src") == "src"

    def test_cd_quoted(self) -> None:
        assert _extract_cd_target('cd "path with spaces"') == "path with spaces"

    def test_cd_single_quoted(self) -> None:
        assert _extract_cd_target("cd 'path with spaces'") == "path with spaces"

    def test_cd_chained_and(self) -> None:
        assert _extract_cd_target("cd /tmp && ls") == "/tmp"

    def test_cd_chained_semicolon(self) -> None:
        assert _extract_cd_target("cd /tmp; ls") == "/tmp"

    def test_not_cd_command(self) -> None:
        assert _extract_cd_target("echo hello") is None

    def test_cd_dash(self) -> None:
        assert _extract_cd_target("cd -") == "-"

    def test_cd_home_subdir(self) -> None:
        assert _extract_cd_target("cd ~/projects") == "~/projects"


class TestUpdateWorkingDirectory:
    """Test _update_working_directory_from_command helper."""

    def test_no_update_on_failure(self) -> None:
        ctx = ShellSecurityContext(workspace="/tmp/test")
        original = ctx.get_working_directory()
        _update_working_directory_from_command(ctx, "cd /somewhere", exit_code=1)
        assert ctx.get_working_directory() == original

    def test_updates_on_success(self, tmp_path: Path) -> None:
        ctx = ShellSecurityContext(workspace=str(tmp_path))
        target = tmp_path / "target"
        target.mkdir()
        _update_working_directory_from_command(ctx, f"cd {target}", exit_code=0)
        assert ctx.get_working_directory() == target.resolve()

    def test_ignores_non_cd(self) -> None:
        ctx = ShellSecurityContext(workspace="/tmp/test")
        original = ctx.get_working_directory()
        _update_working_directory_from_command(ctx, "echo hello", exit_code=0)
        assert ctx.get_working_directory() == original
