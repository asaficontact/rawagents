"""Shell/command execution tools for RawAgents.

Provides Claude Code-compatible shell execution:

- **bash**: Execute shell commands with timeout and security
- **bash_output**: Read output from background processes
- **kill_shell**: Terminate running shell processes

Security:
    All commands are validated via ShellSecurityContext before execution.
    This prevents dangerous commands, injection attacks, and provides
    optional OS-level sandbox integration.

Example:
    >>> from rawagents.tools.builtin.shell import (
    ...     bash, bash_output, kill_shell,
    ...     ShellSecurityContext, set_shell_security_context,
    ... )
    >>>
    >>> # Configure security context
    >>> ctx = ShellSecurityContext(workspace="/home/user/project")
    >>> set_shell_security_context(ctx)
    >>>
    >>> # Execute commands safely
    >>> result = await bash("git status")
"""

from rawagents.tools.builtin.shell._process_manager import ShellSession
from rawagents.tools.builtin.shell._security import (
    CommandSecurityError,
    SandboxNotAvailableError,
    ShellSecurityContext,
    get_shell_security_context,
    is_docker,
    set_shell_security_context,
)
from rawagents.tools.builtin.shell.bash import bash
from rawagents.tools.builtin.shell.bash_output import bash_output
from rawagents.tools.builtin.shell.kill_shell import kill_shell


__all__ = [
    "CommandSecurityError",
    "SandboxNotAvailableError",
    "ShellSecurityContext",
    "ShellSession",
    "bash",
    "bash_output",
    "get_shell_security_context",
    "is_docker",
    "kill_shell",
    "set_shell_security_context",
]
