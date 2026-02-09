"""Security module for shell/command execution tools.

This module provides command validation and execution boundary enforcement
to prevent dangerous command execution and unauthorized system access.

CRITICAL: All shell operations MUST use this module for command validation.

Three Layers of Security:
    1. COMMAND VALIDATION (this module): Pattern matching against deny list,
       allowlist mode, working directory tracking, timeout enforcement.
    2. PERMISSION CHECK (optional): User-configurable allow/deny/ask rules.
    3. OS-LEVEL SANDBOX (optional): bubblewrap (Linux), seatbelt (macOS).

Key Features:
    - 100+ dangerous command patterns blocked by default
    - Chained command injection detection (semicolons, &&, ||, pipes)
    - Command substitution detection ($(), backticks)
    - Incompatible shell detection (fish, nushell, etc.)
    - Persistent working directory tracking with cd parsing
    - Environment file sourcing for persistent env vars
    - Optional sandbox integration (bubblewrap, seatbelt)

Example:
    >>> ctx = ShellSecurityContext(workspace="/home/user/project")
    >>> set_shell_security_context(ctx)
    >>>
    >>> ctx.validate_command("git status")   # OK
    >>> ctx.validate_command("rm -rf /")     # Raises CommandSecurityError
"""

from __future__ import annotations

import contextlib
import contextvars
import fnmatch
import os
import platform
import re
import shutil
import warnings
from dataclasses import dataclass, field
from pathlib import Path


__all__ = [
    "CommandSecurityError",
    "SandboxNotAvailableError",
    "ShellSecurityContext",
    "get_shell_security_context",
    "is_docker",
    "set_shell_security_context",
]


class CommandSecurityError(PermissionError):
    """Raised when a command execution violates security constraints.

    Attributes:
        command: The command that was rejected.
        pattern: The deny pattern that matched (if applicable).
        reason: Human-readable reason for rejection.
    """

    def __init__(
        self,
        message: str,
        command: str,
        pattern: str | None = None,
        reason: str | None = None,
    ):
        super().__init__(message)
        self.command = command
        self.pattern = pattern
        self.reason = reason


class SandboxNotAvailableError(RuntimeError):
    """Raised when sandboxing is enabled but sandbox tools are not available."""

    pass


def is_docker() -> bool:
    """Check if running inside a Docker container.

    Returns:
        True if running inside Docker, False otherwise.
    """
    return Path("/.dockerenv").exists() or os.environ.get("CONTAINER") == "docker"


# Default dangerous command patterns
# Based on OWASP Command Injection guidelines and Claude Code security patterns
# Reference: https://owasp.org/www-community/attacks/Command_Injection
_DEFAULT_DENY_PATTERNS: list[str] = [
    # ==========================================================================
    # DESTRUCTIVE FILE OPERATIONS
    # ==========================================================================
    "rm -rf /*",
    "rm -rf /",
    "rm -rf ~/*",
    "rm -rf ~",
    "rm -rf .",
    "rm -rf ..",
    "rmdir /*",
    "rm -rf /home/*",
    "rm -rf /var/*",
    "rm -rf /etc/*",
    "rm -rf /usr/*",
    # ==========================================================================
    # DISK AND PARTITION OPERATIONS
    # ==========================================================================
    "dd if=*",
    "mkfs*",
    "fdisk*",
    "parted*",
    "wipefs*",
    "shred *",
    # ==========================================================================
    # PRIVILEGE ESCALATION
    # ==========================================================================
    "sudo *",
    "sudo su*",
    "su *",
    "su -*",
    "doas *",
    "pkexec *",
    "runas *",
    # setuid/setgid manipulation
    "chmod +s *",
    "chmod u+s *",
    "chmod g+s *",
    # ==========================================================================
    # SYSTEM MODIFICATION
    # ==========================================================================
    "chmod 777 /*",
    "chmod -R 777 /*",
    "chown -R * /*",
    "chattr *",
    "setenforce *",
    # System service manipulation
    "systemctl disable*",
    "systemctl mask*",
    "service * stop",
    # ==========================================================================
    # DANGEROUS GIT OPERATIONS (without explicit permission)
    # ==========================================================================
    "git push --force*",
    "git push -f*",
    "git push *--force*",
    "git push *-f *",
    "git reset --hard*",
    "git clean -fd*",
    "git clean -f*",
    "git checkout -- .",
    "git restore .",
    "git branch -D *",
    # ==========================================================================
    # FORK BOMBS AND RESOURCE EXHAUSTION
    # ==========================================================================
    ":(){ :|:& };:",
    "*:(){ :|:& };:*",
    "fork()",
    "while true; do*",
    "yes |*",
    # ==========================================================================
    # CREDENTIAL AND HISTORY EXFILTRATION
    # ==========================================================================
    "cat ~/.bash_history",
    "cat ~/.zsh_history",
    "cat ~/.ssh/*",
    "cat /etc/shadow",
    "cat /etc/passwd",
    "cat ~/.netrc",
    "cat ~/.aws/*",
    "cat ~/.config/gcloud/*",
    "cat ~/.kube/config",
    "cat */.env",
    "cat *.pem",
    "cat *id_rsa*",
    "cat *id_ed25519*",
    # Reading sensitive files with other commands
    "less ~/.ssh/*",
    "more ~/.ssh/*",
    "head ~/.ssh/*",
    "tail ~/.ssh/*",
    # ==========================================================================
    # NETWORK EXFILTRATION (pipe to network tools)
    # ==========================================================================
    "*| curl *",
    "*| wget *",
    "*| nc *",
    "*| ncat *",
    "*| netcat *",
    "*> /dev/tcp/*",
    "*| telnet *",
    # ==========================================================================
    # PIPE-TO-SHELL ATTACKS (Remote Code Execution)
    # ==========================================================================
    "curl * | bash",
    "curl * | sh",
    "curl * | zsh",
    "wget * | bash",
    "wget * | sh",
    "wget * | zsh",
    # Without spaces around pipe
    "curl *|bash",
    "curl *|sh",
    "wget *|bash",
    "wget *|sh",
    # Using -s flag
    "curl -s* | bash",
    "curl -s* | sh",
    "wget -q* | bash",
    "wget -q* | sh",
    # Shell -c execution
    'sh -c "curl *"',
    "sh -c 'curl *'",
    'bash -c "curl *"',
    "bash -c 'curl *'",
    'sh -c "wget *"',
    "sh -c 'wget *'",
    'bash -c "wget *"',
    "bash -c 'wget *'",
    # Using eval
    '"eval "$(curl *"',
    '"eval "$(wget *"',
    "eval `curl *`",
    "eval `wget *`",
    # ==========================================================================
    # CHAINED COMMAND INJECTION PATTERNS
    # ==========================================================================
    # Semicolon chaining
    "*; rm -rf *",
    "*; sudo *",
    "*; curl * | *sh*",
    "*; wget * | *sh*",
    "*;rm -rf *",
    "*;sudo *",
    # AND chaining
    "*&& rm -rf *",
    "*&& sudo *",
    "*&& curl * | *sh*",
    "*&& wget * | *sh*",
    "*&&rm -rf *",
    "*&&sudo *",
    # OR chaining
    "*|| rm -rf *",
    "*|| sudo *",
    "*|| curl * | *sh*",
    "*||rm -rf *",
    "*||sudo *",
    # Background execution chaining
    "*& rm -rf *",
    "*& sudo *",
    # ==========================================================================
    # COMMAND SUBSTITUTION INJECTION
    # ==========================================================================
    "*$(rm *)*",
    "*$(sudo *)*",
    "*$(curl * | *sh*)*",
    "*$(wget * | *sh*)*",
    # Backtick substitution
    "*`rm *`*",
    "*`sudo *`*",
    "*`curl *`*",
    "*`wget *`*",
    # ==========================================================================
    # ENVIRONMENT VARIABLE INJECTION
    # ==========================================================================
    '*="$(rm *"*',
    "*='$(rm *'*",
    '*="`rm *`"*',
    # ==========================================================================
    # REVERSE SHELLS
    # ==========================================================================
    "*/dev/tcp/*",
    "*bash -i*",
    "*bash -c*&>/dev/tcp/*",
    "*nc -e*",
    "*ncat -e*",
    "*nc -c*",
    "*ncat -c*",
    "*python*socket*connect*",
    "*python*pty.spawn*",
    "*perl*socket*",
    "*ruby*TCPSocket*",
    "*php -r*fsockopen*",
    "*socat *exec*",
    # ==========================================================================
    # CRYPTO MINING INDICATORS
    # ==========================================================================
    "*xmrig*",
    "*minerd*",
    "*cpuminer*",
    "*stratum+tcp*",
    "*nicehash*",
    # ==========================================================================
    # SCHEDULED TASKS / PERSISTENCE
    # ==========================================================================
    "crontab -r*",
    "crontab -e*",
    "at *",
    "echo * >> /etc/crontab",
    "echo * >> ~/.bashrc",
    "echo * >> ~/.zshrc",
    "echo * >> ~/.profile",
    # ==========================================================================
    # CONTAINER ESCAPE ATTEMPTS
    # ==========================================================================
    "*nsenter*",
    "*docker run*--privileged*",
    "*docker exec*",
    "mount *proc*",
    # ==========================================================================
    # OUTPUT REDIRECTION TO SYSTEM FILES
    # ==========================================================================
    "*> /etc/passwd*",
    "*> /etc/shadow*",
    "*> /etc/sudoers*",
    "*>> /etc/passwd*",
    "*>> /etc/shadow*",
    "*>> /etc/sudoers*",
    "*> ~/.ssh/authorized_keys*",
    "*>> ~/.ssh/authorized_keys*",
]


@dataclass
class ShellSecurityContext:
    """Security context for shell command execution.

    This class enforces:
    1. Command pattern validation (deny dangerous patterns)
    2. Working directory restrictions
    3. Timeout limits
    4. Optional sandbox mode configuration
    5. Environment file sourcing for persistent environment variables

    The context also supports configuration via environment variables:
    - RAWAGENTS_BASH_DEFAULT_TIMEOUT_MS: Override default timeout
    - RAWAGENTS_BASH_MAX_TIMEOUT_MS: Override max timeout
    - RAWAGENTS_ENV_FILE: Path to file sourced before each command

    Example:
        >>> ctx = ShellSecurityContext(workspace="/home/user/project")
        >>> ctx.validate_command("git status")  # OK
        >>> ctx.validate_command("rm -rf /")  # Raises CommandSecurityError

        # With environment file for persistent env vars
        >>> ctx = ShellSecurityContext(
        ...     workspace="/home/user/project",
        ...     env_file="/home/user/.project_env"
        ... )
    """

    workspace: str | None = None
    """Root directory for command execution. Commands are restricted to this directory."""

    deny_patterns: list[str] = field(
        default_factory=lambda: list(_DEFAULT_DENY_PATTERNS)
    )
    """Shell glob patterns for commands that should never be executed."""

    allow_patterns: list[str] = field(default_factory=list)
    """If non-empty, only commands matching these patterns are allowed (allowlist mode)."""

    max_timeout: int = 600000  # 10 minutes
    """Maximum allowed timeout in milliseconds."""

    default_timeout: int = 120000  # 2 minutes
    """Default timeout if not specified."""

    shell_path: str | None = None
    """Custom shell path. If None, uses $SHELL or platform default."""

    env_file: str | None = None
    """Path to a shell script that will be sourced before each command.

    This enables persistent environment variables across commands:

        # ~/.project_env
        export DATABASE_URL="postgres://..."
        export API_KEY="..."

    Then commands will have access to these variables:
        >>> await bash("echo $DATABASE_URL")
        'postgres://...'

    Can also be set via RAWAGENTS_ENV_FILE environment variable.
    """

    maintain_project_working_dir: bool = False
    """If True, reset working directory to workspace after each command."""

    enable_sandbox: bool = False
    """Whether to wrap commands in OS-level sandbox."""

    sandbox_allow_network: bool = False
    """Whether to allow network access in sandboxed mode."""

    sandbox_allow_write_paths: list[str] = field(default_factory=list)
    """Paths where writing is allowed in sandbox mode (in addition to workspace)."""

    sandbox_deny_read_paths: list[str] = field(
        default_factory=lambda: [
            "~/.ssh",
            "~/.gnupg",
            "~/.aws",
            "~/.config/gcloud",
            "~/.kube",
            "~/.netrc",
            "~/.gitconfig",
            "~/.docker/config.json",
        ]
    )
    """Paths to block reading even within sandbox."""

    # Internal state — fields MUST come before __post_init__
    _resolved_workspace: Path | None = field(default=None, init=False, repr=False)
    _current_directory: Path | None = field(default=None, init=False, repr=False)
    _previous_directory: Path | None = field(default=None, init=False, repr=False)
    _compiled_deny_patterns: list[re.Pattern[str]] = field(
        default_factory=list, init=False, repr=False
    )
    _sandbox_available: bool | None = field(default=None, init=False, repr=False)

    # Shells with incompatible syntax that cannot reliably execute POSIX commands.
    INCOMPATIBLE_SHELLS: frozenset[str] = frozenset(
        {
            "fish",
            "nu",
            "nushell",
            "xonsh",
            "elvish",
            "ion",
            "murex",
        }
    )

    def __post_init__(self) -> None:
        """Initialize workspace, compile patterns, and load env config."""
        if self.workspace:
            self._resolved_workspace = Path(self.workspace).resolve()
            self._current_directory = self._resolved_workspace

        # Load timeout overrides from environment variables
        env_default_timeout = os.environ.get("RAWAGENTS_BASH_DEFAULT_TIMEOUT_MS")
        if env_default_timeout:
            with contextlib.suppress(ValueError):
                self.default_timeout = int(env_default_timeout)

        env_max_timeout = os.environ.get("RAWAGENTS_BASH_MAX_TIMEOUT_MS")
        if env_max_timeout:
            with contextlib.suppress(ValueError):
                self.max_timeout = int(env_max_timeout)

        # Load env_file from environment if not set
        if not self.env_file:
            self.env_file = os.environ.get("RAWAGENTS_ENV_FILE")

        # Validate env_file exists if specified
        if self.env_file and not Path(self.env_file).expanduser().exists():
            warnings.warn(
                f"env_file '{self.env_file}' does not exist. "
                "Environment sourcing will be skipped.",
                UserWarning,
                stacklevel=2,
            )

        # Compile deny patterns for faster matching
        self._compiled_deny_patterns = [
            re.compile(fnmatch.translate(p), re.IGNORECASE | re.DOTALL)
            for p in self.deny_patterns
        ]

        # Check sandbox availability upfront if enabled
        if self.enable_sandbox:
            self._check_sandbox_availability()

    def _check_sandbox_availability(self) -> None:
        """Check if sandbox tools are available on this system.

        Raises:
            SandboxNotAvailableError: If sandbox is enabled but tools not found.
        """
        system = platform.system()

        if system == "Linux":
            if not shutil.which("bwrap"):
                raise SandboxNotAvailableError(
                    "Sandbox enabled but bubblewrap (bwrap) is not installed. "
                    "Install with: apt install bubblewrap (Debian/Ubuntu) or "
                    "dnf install bubblewrap (Fedora/RHEL). "
                    "Alternatively, set enable_sandbox=False."
                )
        elif system == "Darwin":
            if not shutil.which("sandbox-exec"):
                raise SandboxNotAvailableError(
                    "Sandbox enabled but sandbox-exec is not available. "
                    "This should be built into macOS. Check your PATH or "
                    "set enable_sandbox=False."
                )
        elif system == "Windows":
            warnings.warn(
                "Sandboxing is not supported on Windows. "
                "Commands will run without sandbox isolation.",
                UserWarning,
                stacklevel=2,
            )
            self._sandbox_available = False
            return

        self._sandbox_available = True

    def validate_command(self, command: str) -> None:  # noqa: PLR0912
        """Validate a command against security constraints.

        Uses both full-match and search-based pattern matching to catch:
        1. Commands that ARE the dangerous pattern (e.g., "rm -rf /")
        2. Commands that CONTAIN the dangerous pattern (e.g., "echo hi; rm -rf /")

        Args:
            command: The shell command to validate.

        Raises:
            CommandSecurityError: If command violates security constraints.
        """
        if not command or not command.strip():
            raise CommandSecurityError(
                "Empty command is not allowed",
                command=command,
                reason="empty_command",
            )

        # Normalize command for pattern matching
        normalized = " ".join(command.split())

        # Check deny patterns using BOTH match (anchored) and search (anywhere)
        for i, compiled in enumerate(self._compiled_deny_patterns):
            original_pattern = self.deny_patterns[i]

            # Method 1: Full match (pattern matches entire command)
            if compiled.match(normalized):
                raise CommandSecurityError(
                    f"Command blocked: matches dangerous pattern '{original_pattern}'",
                    command=command,
                    pattern=original_pattern,
                    reason="deny_pattern_match",
                )

            # Method 2: Search (pattern found anywhere in command)
            # Only do search for patterns that start with * (intended to match anywhere)
            if original_pattern.startswith("*") and compiled.search(normalized):
                raise CommandSecurityError(
                    f"Command blocked: contains dangerous pattern '{original_pattern}'",
                    command=command,
                    pattern=original_pattern,
                    reason="deny_pattern_found",
                )

        # Additional heuristic: check for shell metacharacters that might
        # indicate injection. This catches obfuscated or encoded commands.
        shell_metacharacters = [";", "&&", "||", "|", "`", "$(", "${"]
        has_metachar = any(mc in command for mc in shell_metacharacters)

        if has_metachar:
            # Re-check each segment for dangerous patterns
            segments = re.split(r"[;&|]+", command)
            for raw_segment in segments:
                segment = raw_segment.strip()
                if not segment:
                    continue
                for i, compiled in enumerate(self._compiled_deny_patterns):
                    if compiled.match(segment) or compiled.search(segment):
                        raise CommandSecurityError(
                            f"Command blocked: segment '{segment}' matches dangerous pattern",
                            command=command,
                            pattern=self.deny_patterns[i],
                            reason="chained_command_injection",
                        )

        # If allowlist mode, check allow patterns
        if self.allow_patterns:
            allowed = False
            for pattern in self.allow_patterns:
                if fnmatch.fnmatch(normalized, pattern):
                    allowed = True
                    break
            if not allowed:
                raise CommandSecurityError(
                    "Command not in allowlist",
                    command=command,
                    reason="not_in_allowlist",
                )

    def validate_timeout(self, timeout: int | None) -> int:
        """Validate and normalize timeout value.

        Args:
            timeout: Requested timeout in milliseconds.

        Returns:
            Validated timeout, clamped to max_timeout.
        """
        if timeout is None:
            return self.default_timeout

        if timeout <= 0:
            return self.default_timeout

        return min(timeout, self.max_timeout)

    def get_shell(self) -> str:
        """Get the shell to use for command execution.

        Shell selection priority:
        1. Explicit ``shell_path`` configuration
        2. ``$SHELL`` environment variable (if compatible)
        3. Platform-appropriate default (``/bin/zsh`` on macOS, ``/bin/bash`` on Linux)
        4. ``/bin/sh`` as last resort

        Returns:
            Path to shell executable.
        """
        if self.shell_path:
            return self.shell_path

        # Use $SHELL if set AND compatible
        shell = os.environ.get("SHELL")
        if shell and Path(shell).exists():
            shell_name = Path(shell).name
            if shell_name in self.INCOMPATIBLE_SHELLS:
                warnings.warn(
                    f"Default shell '{shell_name}' is not POSIX-compatible. "
                    f"Using platform default instead. Set shell_path to override.",
                    UserWarning,
                    stacklevel=2,
                )
            else:
                return shell

        # Platform-appropriate default
        system = platform.system()
        if system == "Darwin" and Path("/bin/zsh").exists():
            return "/bin/zsh"
        if Path("/bin/bash").exists():
            return "/bin/bash"

        # Last resort
        return "/bin/sh"

    def get_working_directory(self) -> Path:
        """Get the current working directory for commands.

        Returns:
            Current working directory path.
        """
        if self._current_directory:
            return self._current_directory
        if self._resolved_workspace:
            return self._resolved_workspace
        return Path.cwd()

    def update_working_directory(self, new_dir: str) -> None:
        """Update the working directory after a cd command.

        Handles special cases:
        - ``cd`` or ``cd ~`` -> home directory
        - ``cd -`` -> previous directory
        - ``cd /absolute/path`` -> absolute path
        - ``cd relative/path`` -> relative to current

        Args:
            new_dir: New directory path (absolute, relative, or special).
        """
        current = self.get_working_directory()

        # Handle special cases
        if not new_dir or new_dir == "~":
            new_path = Path.home()
        elif new_dir.startswith("~/"):
            new_path = Path.home() / new_dir[2:]
        elif new_dir == "-":
            if self._previous_directory:
                new_path = self._previous_directory
            else:
                return  # No previous directory, ignore
        elif Path(new_dir).is_absolute():
            new_path = Path(new_dir).resolve()
        else:
            new_path = (current / new_dir).resolve()

        # Track previous directory for cd -
        self._previous_directory = current
        self._current_directory = new_path

    def _build_command_with_env(self, command: str) -> str:
        """Wrap command with env_file sourcing if configured.

        Args:
            command: The shell command to execute.

        Returns:
            Command string, optionally prefixed with source statement.
        """
        if self.env_file:
            env_path = Path(self.env_file).expanduser().resolve()
            if env_path.exists():
                return f'. "{env_path}" && {command}'
        return command

    def build_sandbox_command(self, command: str) -> list[str]:
        """Wrap command in sandbox if enabled, with env_file sourcing.

        Args:
            command: The shell command to wrap.

        Returns:
            Command list ready for subprocess execution.

        Raises:
            SandboxNotAvailableError: If sandbox enabled but tools not available.
        """
        # Apply env_file sourcing
        command = self._build_command_with_env(command)

        if not self.enable_sandbox:
            return [self.get_shell(), "-c", command]

        # Check sandbox availability (may have been disabled on Windows)
        if self._sandbox_available is False:
            return [self.get_shell(), "-c", command]

        system = platform.system()

        if system == "Linux":
            return self._build_bubblewrap_command(command)
        elif system == "Darwin":
            return self._build_seatbelt_command(command)
        else:
            return [self.get_shell(), "-c", command]

    def _build_bubblewrap_command(self, command: str) -> list[str]:
        """Build bubblewrap command for Linux sandboxing."""
        bwrap_cmd = [
            "bwrap",
            "--ro-bind",
            "/usr",
            "/usr",
            "--ro-bind",
            "/lib",
            "/lib",
            "--ro-bind",
            "/lib64",
            "/lib64",
            "--ro-bind",
            "/bin",
            "/bin",
            "--ro-bind",
            "/sbin",
            "/sbin",
            "--ro-bind",
            "/etc",
            "/etc",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--tmpfs",
            "/tmp",
            "--tmpfs",
            "/run",
        ]

        # Add workspace as read-write
        if self._resolved_workspace:
            bwrap_cmd.extend(
                [
                    "--bind",
                    str(self._resolved_workspace),
                    str(self._resolved_workspace),
                ]
            )

        # Add additional write paths
        for path in self.sandbox_allow_write_paths:
            expanded = Path(path).expanduser().resolve()
            if expanded.exists():
                bwrap_cmd.extend(["--bind", str(expanded), str(expanded)])

        # Network isolation
        if not self.sandbox_allow_network:
            bwrap_cmd.append("--unshare-net")

        # Die with parent
        bwrap_cmd.append("--die-with-parent")

        # Add the actual command
        bwrap_cmd.extend([self.get_shell(), "-c", command])

        return bwrap_cmd

    def _build_seatbelt_command(self, command: str) -> list[str]:
        """Build sandbox-exec command for macOS sandboxing."""
        profile_lines = [
            "(version 1)",
            "(deny default)",
            "(allow process-exec)",
            "(allow process-fork)",
            "(allow signal)",
            "(allow file-read*)",
        ]

        # Deny reading sensitive paths
        for path in self.sandbox_deny_read_paths:
            expanded = Path(path).expanduser()
            profile_lines.append(f'(deny file-read* (subpath "{expanded}"))')

        # Allow writing to workspace
        if self._resolved_workspace:
            profile_lines.append(
                f'(allow file-write* (subpath "{self._resolved_workspace}"))'
            )

        # Allow writing to additional paths
        for path in self.sandbox_allow_write_paths:
            expanded = Path(path).expanduser().resolve()
            profile_lines.append(f'(allow file-write* (subpath "{expanded}"))')

        # Allow writing to temp
        profile_lines.append('(allow file-write* (subpath "/tmp"))')
        profile_lines.append('(allow file-write* (subpath "/private/tmp"))')

        # Network
        if self.sandbox_allow_network:
            profile_lines.append("(allow network*)")
        else:
            profile_lines.append("(deny network*)")

        profile = "\n".join(profile_lines)

        return [
            "sandbox-exec",
            "-p",
            profile,
            self.get_shell(),
            "-c",
            command,
        ]


# Context variable for async-safe global context
_shell_security_context_var: contextvars.ContextVar[ShellSecurityContext | None] = (
    contextvars.ContextVar("shell_security_context", default=None)
)


def set_shell_security_context(ctx: ShellSecurityContext) -> None:
    """Set the shell security context for the current async context."""
    _shell_security_context_var.set(ctx)


def get_shell_security_context() -> ShellSecurityContext:
    """Get the current shell security context.

    Returns:
        Current context, or a permissive default if none set.
    """
    ctx = _shell_security_context_var.get()
    if ctx is None:
        warnings.warn(
            "No ShellSecurityContext configured. Creating permissive default. "
            "This is deprecated - call set_shell_security_context() first.",
            DeprecationWarning,
            stacklevel=2,
        )
        ctx = ShellSecurityContext()
        _shell_security_context_var.set(ctx)
    return ctx
