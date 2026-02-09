"""Security tests for shell/command execution tools.

These tests verify that the security module properly prevents:
1. Dangerous command execution
2. Command injection attacks
3. Working directory management
4. Sandbox command generation
5. Shell selection logic
6. Timeout validation
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rawagents.tools.builtin.shell._security import (
    CommandSecurityError,
    ShellSecurityContext,
    set_shell_security_context,
)


class TestDangerousCommands:
    """Test protection against dangerous commands."""

    @pytest.mark.parametrize(
        "command",
        [
            "rm -rf /",
            "rm -rf /*",
            "rm -rf ~",
            "rm -rf .",
            "dd if=/dev/zero of=/dev/sda",
            ":(){ :|:& };:",  # Fork bomb
            "git push --force origin main",
            "git reset --hard HEAD~10",
            "sudo rm -rf /tmp",
            "chmod +s /usr/bin/bash",
        ],
    )
    async def test_blocks_dangerous_commands(
        self, shell_context: ShellSecurityContext, command: str
    ) -> None:
        ctx = ShellSecurityContext(workspace="/tmp/test")
        set_shell_security_context(ctx)

        with pytest.raises(CommandSecurityError) as exc:
            ctx.validate_command(command)

        assert "blocked" in str(exc.value).lower()

    async def test_allows_safe_commands(
        self, shell_context: ShellSecurityContext
    ) -> None:
        ctx = ShellSecurityContext(workspace="/tmp/test")
        set_shell_security_context(ctx)

        # These should NOT raise
        ctx.validate_command("git status")
        ctx.validate_command("ls -la")
        ctx.validate_command("echo 'hello world'")
        ctx.validate_command("npm test")
        ctx.validate_command("python -m pytest")

    async def test_empty_command_rejected(self) -> None:
        ctx = ShellSecurityContext(workspace="/tmp/test")
        with pytest.raises(CommandSecurityError, match="Empty command"):
            ctx.validate_command("")

    async def test_whitespace_only_rejected(self) -> None:
        ctx = ShellSecurityContext(workspace="/tmp/test")
        with pytest.raises(CommandSecurityError, match="Empty command"):
            ctx.validate_command("   ")


class TestCommandInjection:
    """Test protection against command injection."""

    @pytest.mark.parametrize(
        "command",
        [
            "echo hello; rm -rf /",
            "echo hello && rm -rf /",
            "echo hello || rm -rf /",
            "$(rm -rf /)",
            "`rm -rf /`",
            "echo hello > /etc/passwd",
        ],
    )
    async def test_injection_patterns(self, command: str) -> None:
        """Commands containing injection patterns should be blocked."""
        ctx = ShellSecurityContext(
            workspace="/tmp/test",
            deny_patterns=["*rm -rf /*", "*> /etc/*"],
        )
        set_shell_security_context(ctx)

        with pytest.raises(CommandSecurityError):
            ctx.validate_command(command)


class TestAllowlistMode:
    """Test allowlist-only execution mode."""

    async def test_allowlist_rejects_unlisted(self) -> None:
        ctx = ShellSecurityContext(
            workspace="/tmp/test",
            allow_patterns=["git *", "npm test"],
        )
        set_shell_security_context(ctx)

        # Allowed
        ctx.validate_command("git status")
        ctx.validate_command("npm test")

        # Not allowed
        with pytest.raises(CommandSecurityError) as exc:
            ctx.validate_command("curl https://example.com")

        assert "not in allowlist" in str(exc.value)


class TestSandboxIntegration:
    """Test sandbox command generation."""

    def test_sandbox_command_generation(self) -> None:
        """Sandbox command should include wrapper."""
        try:
            ctx = ShellSecurityContext(
                workspace="/home/user/project",
                enable_sandbox=True,
                sandbox_allow_network=False,
            )
        except Exception:
            pytest.skip("Sandbox tools not available")
            return

        cmd = ctx.build_sandbox_command("git status")

        assert "bwrap" in cmd[0] or "sandbox-exec" in cmd[0]

    def test_sandbox_denies_sensitive_paths(self) -> None:
        """Sandbox profile should include denied paths."""
        try:
            ctx = ShellSecurityContext(
                workspace="/home/user/project",
                enable_sandbox=True,
                sandbox_deny_read_paths=["~/.ssh", "~/.aws"],
            )
        except Exception:
            pytest.skip("Sandbox tools not available")
            return

        cmd = ctx.build_sandbox_command("cat ~/.ssh/id_rsa")

        # Command should be wrapped in sandbox that denies this
        assert len(cmd) > 3  # Has sandbox wrapper

    def test_no_sandbox_when_disabled(self) -> None:
        """When sandbox is disabled, command should run directly."""
        ctx = ShellSecurityContext(
            workspace="/tmp/test",
            enable_sandbox=False,
        )

        cmd = ctx.build_sandbox_command("echo hello")

        # Should just be [shell, -c, command]
        assert len(cmd) == 3
        assert cmd[1] == "-c"


class TestShellSelection:
    """Test shell detection and selection logic."""

    def test_explicit_shell_path(self) -> None:
        ctx = ShellSecurityContext(shell_path="/bin/sh")
        assert ctx.get_shell() == "/bin/sh"

    def test_platform_default(self) -> None:
        ctx = ShellSecurityContext()
        shell = ctx.get_shell()
        # Should be a valid shell path
        assert shell.startswith("/")

    def test_incompatible_shell_warning(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Incompatible shells should trigger a warning."""
        # Create a fake fish executable so the Path.exists() check passes
        fake_fish = tmp_path / "fish"
        fake_fish.write_text("#!/bin/sh\n")
        fake_fish.chmod(0o755)

        monkeypatch.setenv("SHELL", str(fake_fish))

        ctx = ShellSecurityContext()
        with pytest.warns(UserWarning, match="not POSIX-compatible"):
            shell = ctx.get_shell()

        # Should fall back to platform default, not fish
        assert "fish" not in shell


class TestWorkingDirectory:
    """Test working directory tracking."""

    def test_initial_workspace(self, tmp_path: Path) -> None:
        ctx = ShellSecurityContext(workspace=str(tmp_path))
        assert ctx.get_working_directory() == tmp_path.resolve()

    def test_cd_absolute(self, tmp_path: Path) -> None:
        target = tmp_path / "target"
        target.mkdir()
        ctx = ShellSecurityContext(workspace=str(tmp_path))
        ctx.update_working_directory(str(target))
        assert ctx.get_working_directory() == target.resolve()

    def test_cd_relative(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        ctx = ShellSecurityContext(workspace=str(tmp_path))
        ctx.update_working_directory("src")
        assert ctx.get_working_directory() == (tmp_path / "src").resolve()

    def test_cd_home(self, tmp_path: Path) -> None:
        ctx = ShellSecurityContext(workspace=str(tmp_path))
        ctx.update_working_directory("~")
        assert ctx.get_working_directory() == Path.home()

    def test_cd_dash_previous(self, tmp_path: Path) -> None:
        target = tmp_path / "other"
        target.mkdir()
        ctx = ShellSecurityContext(workspace=str(tmp_path))
        ctx.update_working_directory(str(target))
        ctx.update_working_directory("-")
        assert ctx.get_working_directory() == tmp_path.resolve()

    def test_cd_dash_no_previous(self, tmp_path: Path) -> None:
        ctx = ShellSecurityContext(workspace=str(tmp_path))
        # No previous directory — cd - should be a no-op
        ctx.update_working_directory("-")
        assert ctx.get_working_directory() == tmp_path.resolve()


class TestTimeout:
    """Test timeout validation."""

    def test_default_timeout(self) -> None:
        ctx = ShellSecurityContext()
        assert ctx.validate_timeout(None) == 120000

    def test_custom_timeout(self) -> None:
        ctx = ShellSecurityContext()
        assert ctx.validate_timeout(5000) == 5000

    def test_max_timeout_clamped(self) -> None:
        ctx = ShellSecurityContext(max_timeout=600000)
        assert ctx.validate_timeout(999999) == 600000

    def test_negative_timeout_uses_default(self) -> None:
        ctx = ShellSecurityContext()
        assert ctx.validate_timeout(-1) == 120000

    def test_zero_timeout_uses_default(self) -> None:
        ctx = ShellSecurityContext()
        assert ctx.validate_timeout(0) == 120000
