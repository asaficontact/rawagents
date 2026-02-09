# Shell Command Execution Tools

Async shell command execution with security validation, background process management, and OS-level sandboxing for building Claude Code-compatible AI agents.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Tool Reference](#tool-reference)
  - [bash](#bash)
  - [bash_output](#bash_output)
  - [kill_shell](#kill_shell)
- [Security Architecture](#security-architecture)
  - [Three-Layer Security Model](#three-layer-security-model)
  - [Deny Patterns](#deny-patterns)
  - [Allowlist Mode](#allowlist-mode)
  - [OS-Level Sandbox](#os-level-sandbox)
- [Background Process Management](#background-process-management)
- [Configuration Reference](#configuration-reference)
  - [ShellSecurityContext](#shellsecuritycontext)
  - [Environment Variables](#environment-variables)
  - [Shell Selection](#shell-selection)
- [Working Directory Tracking](#working-directory-tracking)
- [Output Handling](#output-handling)
- [Error Handling](#error-handling)
  - [Error Message Formats](#error-message-formats)
  - [Audit Logging](#audit-logging)
  - [Retry with Recovery](#retry-with-recovery)
- [Module Structure](#module-structure)
- [Testing](#testing)

---

## Overview

The shell tools module provides three async tool functions for executing shell commands within an AI agent framework:

| Tool | Purpose |
|------|---------|
| `bash` | Execute shell commands with timeout, security validation, and output capture |
| `bash_output` | Read output from background processes |
| `kill_shell` | Terminate running shell processes |

All tools follow the `@tool` decorator pattern: `async def`, return `str`, use `Annotated[T, "desc"]` parameters, and return errors as `"Error: ..."` strings rather than raising exceptions.

### Key Features

- **Security validation** -- 159 deny patterns block dangerous commands before execution
- **Three-layer security** -- Pattern matching + permission system + OS-level sandbox
- **Background processes** -- Start long-running commands, retrieve output incrementally, terminate when done
- **Timeout handling** -- Configurable timeouts with graceful SIGTERM/SIGKILL escalation
- **Working directory tracking** -- Persistent `cd` tracking across commands
- **Output truncation** -- Dual truncation (2000 lines / 50KB) with full output saved to temp files
- **Audit logging** -- Structured JSON logging of all executions and security events
- **Async-safe** -- Security context stored in `contextvars.ContextVar` for per-task isolation

---

## Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Agent / LLM                                 │
│                                                                     │
│  await bash("git status")    await bash_output(pid)    kill_shell() │
└──────────┬─────────────────────────┬──────────────────────┬─────────┘
           │                         │                      │
           ▼                         ▼                      ▼
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────────┐
│    bash.py       │   │ bash_output.py   │   │   kill_shell.py      │
│                  │   │                  │   │                      │
│ Security check   │   │ Get new output   │   │ SIGTERM / SIGKILL    │
│ Subprocess exec  │   │ Truncate (50KB)  │   │ Process group kill   │
│ Timeout handling │   │ Status reporting │   │ Registry cleanup     │
│ cd tracking      │   │                  │   │                      │
│ Output truncation│   └────────┬─────────┘   └──────────┬───────────┘
│ Audit logging    │            │                         │
└──────┬───────────┘            │                         │
       │                        ▼                         ▼
       │              ┌──────────────────────────────────────────┐
       │              │        ProcessManager (Singleton)         │
       │              │                                          │
       │              │  register() ──► _collect_output() task   │
       │              │  get_output() ◄── asyncio.Event wait     │
       │              │  kill() ──► os.killpg(SIGTERM/SIGKILL)   │
       │              │  cleanup() ──► force-kill all            │
       │              │                                          │
       │              │  ┌─────────────────────────────────┐     │
       │              │  │ ProcessInfo (per process)        │     │
       │              │  │  pid: int                        │     │
       │              │  │  command: str                    │     │
       │              │  │  started_at: datetime            │     │
       │              │  │  output_buffer: list[str]        │     │
       │              │  │  MAX_BUFFER_LINES: 10,000        │     │
       │              │  │  _new_output_event: asyncio.Event│     │
       │              │  │  last_read_index: int            │     │
       │              │  └─────────────────────────────────┘     │
       │              └──────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│              ShellSecurityContext (ContextVar)                │
│                                                              │
│  ┌────────────────┐  ┌─────────────────┐  ┌──────────────┐  │
│  │ Layer 1:       │  │ Layer 2:        │  │ Layer 3:     │  │
│  │ Command        │  │ Permission      │  │ OS Sandbox   │  │
│  │ Validation     │  │ System          │  │              │  │
│  │                │  │                 │  │ Linux: bwrap │  │
│  │ 100+ deny      │  │ (Integration    │  │ macOS:       │  │
│  │ patterns       │  │  point for      │  │  sandbox-exec│  │
│  │ Allowlist mode │  │  external       │  │ Namespace    │  │
│  │ Metachar check │  │  systems)       │  │  isolation   │  │
│  └────────────────┘  └─────────────────┘  └──────────────┘  │
│                                                              │
│  Working dir tracking  │  Shell selection  │  Timeout mgmt   │
│  cd / cd - / cd ~      │  bash/zsh/sh      │  120s default   │
│  env_file sourcing     │  INCOMPATIBLE set  │  600s maximum   │
└──────────────────────────────────────────────────────────────┘
```

### Request Flow

```
Command Input
      │
      ▼
┌─────────────┐     ┌──────────────┐
│ validate_    │────►│ BLOCKED      │──► "Error: Command blocked..."
│ command()   │ NO  │              │
└──────┬──────┘     └──────────────┘
       │ OK
       ▼
┌─────────────┐
│ validate_   │──► Clamp to [default, max] range
│ timeout()   │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌──────────────┐
│ Sandbox     │ YES │ build_sandbox│──► bwrap/sandbox-exec wrapper
│ enabled?    │────►│ _command()   │
└──────┬──────┘     └──────────────┘
       │ NO
       ▼
┌─────────────┐
│ _build_     │──► source "env_file" && command
│ command_    │
│ with_env()  │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌──────────────┐
│ Background? │ YES │ register()   │──► "Started background process with PID: ..."
│             │────►│ Return PID   │
└──────┬──────┘     └──────────────┘
       │ NO
       ▼
┌─────────────────────┐
│ asyncio.wait_for(   │
│   communicate(),    │     ┌─────────────────────────────┐
│   timeout=N         │────►│ TimeoutError:               │
│ )                   │     │  1. SIGTERM to process group │
└──────┬──────────────┘     │  2. Wait 5s                 │
       │                    │  3. SIGKILL if still alive   │
       │ OK                 └─────────────────────────────┘
       ▼
┌──────────────────┐
│ Decode UTF-8     │
│ Truncate output  │──► If truncated: save full output to temp file
│ Track cd         │
│ Audit log        │
└──────┬───────────┘
       │
       ▼
  Return output string
```

---

## Quick Start

```python
from rawagents.tools.builtin.shell import (
    bash,
    bash_output,
    kill_shell,
    ShellSecurityContext,
    set_shell_security_context,
)

# 1. Configure security context
ctx = ShellSecurityContext(workspace="/home/user/project")
set_shell_security_context(ctx)

# 2. Execute commands
result = await bash("git status")
print(result)  # "On branch main\nnothing to commit..."

# 3. Handle errors (returned as strings, not exceptions)
result = await bash("nonexistent_command")
print(result)  # "Error: Command failed with exit code 127\n..."

# 4. Background processes
result = await bash("npm run dev", run_in_background=True)
# "Started background process with PID: 12345"
pid = result.split("PID: ")[1].strip()

output = await bash_output(pid=pid, timeout=5000)
# "Listening on port 3000\n\nProcess status: running"

await kill_shell(pid=pid)
# "Process 12345 terminated successfully"
```

---

## Tool Reference

### `bash`

Execute a shell command with security validation, timeout handling, and output capture.

```python
@tool
async def bash(
    command: Annotated[str, "The shell command to execute"],
    description: Annotated[str | None, "Description of what this command does"] = None,
    timeout: Annotated[int | None, "Timeout in milliseconds (max 600000)"] = None,
    run_in_background: Annotated[bool, "Run command in background, return PID"] = False,
    dangerously_disable_sandbox: Annotated[bool, "Override sandbox mode (use with extreme caution)"] = False,
) -> str:
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `command` | `str` | required | Shell command to execute. Validated against deny patterns. |
| `description` | `str \| None` | `None` | Human-readable description for audit purposes. |
| `timeout` | `int \| None` | `None` | Timeout in milliseconds. Defaults to 120,000 (2 min), max 600,000 (10 min). |
| `run_in_background` | `bool` | `False` | Return PID immediately; use `bash_output`/`kill_shell` to manage. |
| `dangerously_disable_sandbox` | `bool` | `False` | Skip OS-level sandbox even when enabled. Command validation still applies. |

#### Return Values

| Scenario | Format |
|----------|--------|
| Success with output | `"<stripped output>"` |
| Success, no output | `"(no output)"` |
| Non-zero exit code | `"Error: Command failed with exit code {N}\n{output}"` |
| Timeout | `"Error: Command timed out after {N} seconds"` |
| Security blocked | `"Error: Command blocked: matches dangerous pattern '{p}'"` |
| Background started | `"Started background process with PID: {pid}"` |
| Truncated output | Output + `"\n\n... (output truncated at 2000 lines / 50KB)\nFull output saved to: {path}"` |

#### Examples

```python
# Simple command
result = await bash("echo hello")
# "hello"

# Multi-line output
result = await bash("echo line1; echo line2; echo line3")
# "line1\nline2\nline3"

# Error handling
result = await bash("false")
# "Error: Command failed with exit code 1\n"

# Timeout
result = await bash("sleep 100", timeout=500)
# "Error: Command timed out after 0.5 seconds"

# Background process
result = await bash("python -m http.server 8000", run_in_background=True)
# "Started background process with PID: 54321"

# With description (for audit logs)
result = await bash("git push origin main", description="Deploy to production")
```

---

### `bash_output`

Read output from a background process started with `bash(run_in_background=True)`.

```python
@tool
async def bash_output(
    pid: Annotated[str, "Process ID of the background command"],
    timeout: Annotated[int | None, "Timeout in ms to wait for new output"] = 5000,
) -> str:
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pid` | `str` | required | Process ID from `bash(run_in_background=True)`. |
| `timeout` | `int \| None` | `5000` | Max wait time (ms) for new output. Returns immediately when output arrives. |

#### Return Values

| Scenario | Format |
|----------|--------|
| Has new output (running) | `"{output}\n\nProcess status: running"` |
| Has new output (done) | `"{output}\n\nProcess status: completed (exit code {N})"` |
| No new output (running) | `"Process status: running"` |
| No new output (done) | `"Process status: completed (exit code {N})"` |
| Output exceeds 50KB | Output truncated + `"\n... (output truncated at 50KB)"` appended, then status |
| Unknown PID | `"Error: Process not found"` |

The timeout uses **event-based waiting** -- it returns as soon as new output is available rather than sleeping the full duration.

Only **new output since the last read** is returned. An internal `last_read_index` cursor tracks what has been consumed.

#### Example

```python
import asyncio

# Start a background process
result = await bash("for i in 1 2 3 4 5; do echo item$i; sleep 0.2; done",
                    run_in_background=True)
pid = result.split("PID: ")[1].strip()

# Wait and read incrementally
await asyncio.sleep(0.5)
output = await bash_output(pid=pid, timeout=2000)
# "item1\nitem2\nitem3\n\nProcess status: running"

# Read more
output = await bash_output(pid=pid, timeout=2000)
# "item4\nitem5\n\nProcess status: completed (exit code 0)"
```

---

### `kill_shell`

Terminate a running shell process.

```python
@tool
async def kill_shell(
    pid: Annotated[str, "Process ID to terminate"],
    force: Annotated[bool, "Use SIGKILL instead of SIGTERM"] = False,
) -> str:
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pid` | `str` | required | Process ID to terminate. |
| `force` | `bool` | `False` | `False`: SIGTERM with 5s grace, then SIGKILL. `True`: Immediate SIGKILL. |

#### Return Values

| Scenario | Format |
|----------|--------|
| Success | `"Process {pid} terminated successfully"` |
| Unknown PID | `"Error: Process {pid} not found"` |
| Already dead | `"Process {pid} already terminated"` |
| OS error | `"Error: Failed to kill process {pid}: {error}"` |

All signals target the **entire process group** via `os.killpg()`, ensuring child processes are also terminated.

#### Termination Flow

```
kill_shell(pid, force=False)          kill_shell(pid, force=True)
         │                                      │
         ▼                                      ▼
   SIGTERM to group                       SIGKILL to group
         │                                      │
         ▼                                      ▼
   Wait up to 5s                          process.wait()
         │                                      │
    ┌────┴────┐                                 ▼
    │ Exited? │                           Remove from registry
    └────┬────┘
    YES  │  NO
    │    │
    │    ▼
    │  SIGKILL to group
    │    │
    │    ▼
    │  process.wait()
    │    │
    ▼    ▼
  Remove from registry
```

---

## Security Architecture

### Three-Layer Security Model

The shell tools implement defense-in-depth with three independent security layers:

```
┌─────────────────────────────────────────────────┐
│              Incoming Command                    │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────┐
│  LAYER 1: Command Validation                     │
│                                                  │
│  - 159 deny patterns (glob matching)            │
│  - Shell metacharacter heuristic                 │
│  - Segment-by-segment injection analysis         │
│  - Optional allowlist-only mode                  │
│                                                  │
│  Blocks: rm -rf, sudo, fork bombs, reverse       │
│  shells, crypto miners, privilege escalation     │
│                                                  │
│  ► Fast, always-on, zero-cost                    │
└──────────────────────┬───────────────────────────┘
                       │ PASS
                       ▼
┌──────────────────────────────────────────────────┐
│  LAYER 2: Permission System (Integration Point)  │
│                                                  │
│  External systems can hook in to provide:        │
│  - User-level command approval                   │
│  - Role-based access control                     │
│  - Interactive confirmation prompts              │
│                                                  │
│  ► Extensible, agent-framework dependent         │
└──────────────────────┬───────────────────────────┘
                       │ PASS
                       ▼
┌──────────────────────────────────────────────────┐
│  LAYER 3: OS-Level Sandbox                       │
│                                                  │
│  Linux: bubblewrap (bwrap)                       │
│  - Namespace isolation (PID, mount, network)     │
│  - Read-only filesystem with workspace writable  │
│  - --die-with-parent for cleanup                 │
│                                                  │
│  macOS: sandbox-exec (Seatbelt)                  │
│  - Profile-based deny/allow rules                │
│  - Blocks sensitive paths (~/.ssh, ~/.aws, etc.) │
│  - Network isolation optional                    │
│                                                  │
│  ► Kernel-enforced, strongest isolation           │
└──────────────────────┬───────────────────────────┘
                       │ PASS
                       ▼
                 Command Executes
```

### Deny Patterns

The default deny list contains 159 patterns across 17 categories:

| Category | Examples |
|----------|----------|
| Destructive file operations | `rm -rf /`, `rm -rf ~`, `rm -rf .`, `rmdir /*` |
| Disk and partition operations | `mkfs*`, `dd if=*`, `fdisk*`, `shred *` |
| Privilege escalation | `sudo *`, `su -*`, `doas *`, `chmod +s *`, `chmod u+s *` |
| System modification | `systemctl disable*`, `systemctl mask*`, `service * stop`, `chown -R * /*` |
| Dangerous git operations | `git push --force*`, `git push -f*`, `git reset --hard*`, `git clean -f*` |
| Fork bombs and resource exhaustion | `:(){ :\|:& };:`, `while true; do*`, `yes \|*` |
| Credential exfiltration | `cat ~/.ssh/*`, `cat /etc/shadow`, `cat ~/.aws/*`, `cat *id_rsa*` |
| Network exfiltration | `*\| curl *`, `*\| wget *`, `*\| nc *`, `*> /dev/tcp/*` |
| Pipe-to-shell attacks | `curl * \| bash`, `curl *\|bash`, `wget *\|sh` |
| Chained command injection | `*; rm -rf *`, `*&& sudo *`, `*\|\| sudo *` |
| Command substitution injection | `*$(rm *)*`, `*$(sudo *)*`, `` *`rm *`* `` |
| Environment variable injection | `*="$(rm *"*`, `*='$(rm *'*` |
| Reverse shells | `*/dev/tcp/*`, `*bash -i*`, `*python*socket*connect*`, `*nc -e*` |
| Crypto mining | `*xmrig*`, `*minerd*`, `*cpuminer*`, `*stratum+tcp*`, `*nicehash*` |
| Scheduled tasks / persistence | `crontab -r*`, `crontab -e*`, `at *`, `echo * >> ~/.bashrc` |
| Container escape | `*nsenter*`, `*docker run*--privileged*`, `mount *proc*` |
| Output redirection to system files | `*> /etc/passwd*`, `*> /etc/shadow*`, `*>> ~/.ssh/authorized_keys*` |

#### Pattern Matching Logic

1. **Full match:** `fnmatch.fnmatch(normalized_command, pattern)` -- for patterns like `rm -rf /`
2. **Search match:** For patterns starting with `*`, also searches within the command using `fnmatch.fnmatch(command, pattern)` -- catches embedded dangerous substrings
3. **Segment analysis:** Splits command on shell metacharacters (`;`, `&&`, `||`, `|`, `&`) and validates each segment independently -- catches chained injection

### Allowlist Mode

When `allow_patterns` is non-empty, the security context operates in allowlist-only mode:

```python
ctx = ShellSecurityContext(
    workspace="/project",
    allow_patterns=["git *", "npm *", "python -m pytest*"],
)
set_shell_security_context(ctx)

await bash("git status")       # OK
await bash("npm test")         # OK
await bash("curl example.com") # "Error: Command not in allowlist"
```

### OS-Level Sandbox

Enable with `enable_sandbox=True`. Requires platform-specific tools:

| Platform | Tool | Package |
|----------|------|---------|
| Linux | `bwrap` (bubblewrap) | `bubblewrap` |
| macOS | `sandbox-exec` | Built-in (Seatbelt) |
| Windows | Not supported | -- |

```python
ctx = ShellSecurityContext(
    workspace="/project",
    enable_sandbox=True,
    sandbox_allow_network=False,            # Block network access
    sandbox_allow_write_paths=["/tmp/out"], # Additional writable paths
    sandbox_deny_read_paths=["~/.ssh"],     # Block reading sensitive files
)
```

**Default denied read paths:** `~/.ssh`, `~/.gnupg`, `~/.aws`, `~/.config/gcloud`, `~/.kube`, `~/.netrc`, `~/.gitconfig`, `~/.docker/config.json`

---

## Background Process Management

### Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│                    Background Process Lifecycle              │
│                                                             │
│  ┌───────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │  START    │    │  RUNNING     │    │  TERMINATED      │  │
│  │           │───►│              │───►│                  │  │
│  │ bash(     │    │ Output       │    │ kill_shell()     │  │
│  │  cmd,     │    │ collected    │    │ or natural exit  │  │
│  │  run_in_  │    │ in buffer    │    │                  │  │
│  │  backgrnd │    │              │    │ Removed from     │  │
│  │  =True)   │    │ bash_output()│    │ registry         │  │
│  │           │    │ reads new    │    │                  │  │
│  │ Returns   │    │ output       │    │                  │  │
│  │ PID       │    │              │    │                  │  │
│  └───────────┘    └──────────────┘    └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### ProcessManager (Singleton)

The `ProcessManager` is a **module-level singleton** (not a `ContextVar`) because OS processes are global -- a process started in one coroutine must be killable from another.

| Method | Description |
|--------|-------------|
| `register(process, command)` | Register a new process, start output collection, return PID |
| `get_output(pid, timeout)` | Wait for new output (event-based), return `(output, status)` |
| `kill(pid, force)` | Terminate process with SIGTERM/SIGKILL escalation |
| `cleanup()` | Force-kill all tracked processes |

### Output Buffer

Each background process has an output buffer with a **10,000-line cap** (FIFO eviction):

```
Output Buffer (ProcessInfo)
┌─────────────────────────────┐
│ line 1                      │  ◄── Oldest (evicted first when > 10,000)
│ line 2                      │
│ ...                         │
│ line N ◄── last_read_index  │  ◄── Consumer cursor
│ line N+1                    │  ◄── New output (returned by get_output)
│ line N+2                    │
│ ...                         │
│ line M                      │  ◄── Latest
└─────────────────────────────┘
     MAX_BUFFER_LINES = 10,000
```

When the buffer exceeds 10,000 lines, the oldest lines are deleted and `last_read_index` is adjusted. The `asyncio.Event` is signaled on each new line, enabling `bash_output()` to return immediately when output is available.

---

## Configuration Reference

### ShellSecurityContext

All configuration is centralized in the `ShellSecurityContext` dataclass, stored in a `contextvars.ContextVar` for async-task isolation.

#### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `workspace` | `str \| None` | `None` | Root directory for command execution |
| `deny_patterns` | `list[str]` | 159 defaults | Shell glob patterns for blocked commands |
| `allow_patterns` | `list[str]` | `[]` | If non-empty, only matching commands allowed |
| `max_timeout` | `int` | `600000` (10 min) | Maximum allowed timeout in ms |
| `default_timeout` | `int` | `120000` (2 min) | Default timeout when none specified |
| `shell_path` | `str \| None` | `None` | Explicit shell binary path |
| `env_file` | `str \| None` | `None` | Shell script sourced before each command |
| `maintain_project_working_dir` | `bool` | `False` | Reset cwd to workspace after each command |
| `enable_sandbox` | `bool` | `False` | Enable OS-level sandbox wrapping |
| `sandbox_allow_network` | `bool` | `False` | Allow network access in sandbox |
| `sandbox_allow_write_paths` | `list[str]` | `[]` | Additional writable paths in sandbox |
| `sandbox_deny_read_paths` | `list[str]` | sensitive defaults | Paths blocked from reading in sandbox |

#### Context Management

```python
from rawagents.tools.builtin.shell import (
    ShellSecurityContext,
    set_shell_security_context,
    get_shell_security_context,
)

# Set context for the current async task
ctx = ShellSecurityContext(workspace="/project")
set_shell_security_context(ctx)

# Retrieve current context
ctx = get_shell_security_context()
# If none set, creates a permissive default with DeprecationWarning
```

### Environment Variables

| Variable | Purpose | Overrides |
|----------|---------|-----------|
| `RAWAGENTS_BASH_DEFAULT_TIMEOUT_MS` | Override default timeout | `default_timeout` |
| `RAWAGENTS_BASH_MAX_TIMEOUT_MS` | Override maximum timeout | `max_timeout` |
| `RAWAGENTS_ENV_FILE` | Fallback env file path | `env_file` (if not set) |

### Shell Selection

The shell binary is selected with the following priority:

```
1. Explicit shell_path (if set)
         │
         ▼ (not set)
2. $SHELL environment variable
   ├── If compatible (bash, zsh, sh, dash, etc.) → use it
   └── If incompatible (fish, nu, xonsh, elvish, ion, murex)
       → emit UserWarning, fall through
         │
         ▼
3. /bin/zsh (macOS only, if exists)
         │
         ▼
4. /bin/bash (if exists)
         │
         ▼
5. /bin/sh (last resort)
```

**Incompatible shells** (non-POSIX syntax): `fish`, `nu`, `nushell`, `xonsh`, `elvish`, `ion`, `murex`

---

## Working Directory Tracking

The shell tools track `cd` commands across executions, maintaining a persistent working directory:

```python
ctx = ShellSecurityContext(workspace="/project")
set_shell_security_context(ctx)

await bash("cd src")           # Tracks: /project/src
await bash("ls")               # Runs in: /project/src
await bash("cd ../tests")      # Tracks: /project/tests
await bash("cd -")             # Tracks: /project/src (previous directory)
await bash("cd ~")             # Tracks: /home/user
await bash("cd /nonexistent")  # Failed cd (exit code != 0): no update
```

### Supported `cd` Patterns

| Pattern | Behavior |
|---------|----------|
| `cd` | Go to `~` (home) |
| `cd /absolute/path` | Set to absolute path |
| `cd relative/path` | Resolve relative to current directory |
| `cd ~` / `cd ~/subdir` | Expand home directory |
| `cd -` | Return to previous directory |
| `cd "path with spaces"` | Handles quoted paths |
| `cd /path && other` | Extracts cd target from chained commands |

### Rules

- **Only updates on success** -- a failed `cd` (exit code != 0) does not change the tracked directory
- **Previous directory saved** -- enables `cd -` support
- **`maintain_project_working_dir`** -- when `True`, resets to workspace after each command regardless of `cd`

---

## Output Handling

### Dual Truncation

Output is truncated using two independent limits, applied in order:

```
Raw stdout bytes
      │
      ▼ decode UTF-8 (errors="replace")
      │
      ▼ Split into lines
      │
  Lines > 2000?  ──YES──►  Keep first 2000 lines
      │
      │ NO
      ▼
  Bytes > 50KB?  ──YES──►  Trim to 50KB at line boundary
      │
      │ NO
      ▼
  Return output

  If any truncation occurred:
  ┌─────────────────────────────────────┐
  │ Save full output to temp file:      │
  │ /tmp/rawagents_bash_XXXXXXXX.txt    │
  │                                     │
  │ Append notice:                      │
  │ "... (output truncated at 2000      │
  │  lines / 50KB)                      │
  │ Full output saved to: /tmp/..."     │
  └─────────────────────────────────────┘
```

| Constant | Value | Applied to |
|----------|-------|------------|
| `MAX_OUTPUT_LINES` | 2,000 | `bash()` |
| `MAX_OUTPUT_BYTES` | 50 KB (51,200 bytes) | `bash()` and `bash_output()` |
| `MAX_BUFFER_LINES` | 10,000 | Background process buffer |

---

## Error Handling

### Error Message Formats

All tools return errors as strings (never raise exceptions to the caller):

| Condition | Format |
|-----------|--------|
| Command blocked (full match) | `"Error: Command blocked: matches dangerous pattern '{pattern}'"` |
| Command blocked (search match) | `"Error: Command blocked: contains dangerous pattern '{pattern}'"` |
| Command blocked (chained injection) | `"Error: Command blocked: segment '{segment}' matches dangerous pattern"` |
| Command not in allowlist | `"Error: Command not in allowlist"` |
| Empty command | `"Error: Empty command is not allowed"` |
| Non-zero exit code | `"Error: Command failed with exit code {N}\n{output}"` |
| Timeout | `"Error: Command timed out after {N} seconds"` |
| General exception | `"Error: Failed to execute command: {exception}"` |
| Process not found (bash_output) | `"Error: Process not found"` |
| Process not found (kill_shell) | `"Error: Process {pid} not found"` |

### Structured Errors

The `ShellError` dataclass provides structured error information for programmatic error handling:

```python
from rawagents.tools.builtin.shell._errors import ShellError, ErrorSeverity

error = ShellError(
    severity=ErrorSeverity.ERROR,
    message="Command failed",
    command="npm install",
    exit_code=1,
    stderr="EACCES: permission denied",
    suggestion="Check file permissions or try a different directory",
)

print(error.to_user_message())
# Error: Command failed
# Exit code: 1
# Details: EACCES: permission denied
# Suggestion: Check file permissions or try a different directory
```

**Severity levels:** `INFO`, `WARNING`, `ERROR`, `SECURITY`

Note: `to_user_message()` truncates `stderr` to 500 characters to keep error reports concise.

### Error Suggestions

The `suggest_fix()` function matches common error patterns:

| Stderr Pattern | Suggestion |
|----------------|------------|
| `"command not found"` | `"Check if the command is installed and in PATH"` |
| `"permission denied"` | `"Check file permissions or try a different directory"` |
| `"no such file or directory"` | `"Verify the path exists"` |
| `"disk quota exceeded"` | `"Free up disk space"` |
| `"cannot allocate memory"` | `"Close other applications or increase memory"` |
| `"connection refused"` | `"Check if the service is running"` |
| `"timeout"` | `"Try increasing the timeout or running in background"` |

### Audit Logging

Configure structured JSON audit logging:

```python
from pathlib import Path
from rawagents.tools.builtin.shell._errors import configure_audit_logging

configure_audit_logging(
    log_file=Path("~/.rawagents/shell_audit.log").expanduser(),
)
```

Events logged:

| Event | Level | Fields |
|-------|-------|--------|
| `command_executed` | INFO | command, working_dir, exit_code, duration_ms, truncated |
| `security_blocked` | WARNING | command, reason, pattern |
| `background_started` | INFO | pid, command |

All entries include ISO 8601 timestamps and commands are truncated to 200 characters.

### Retry with Recovery

Execute commands with automatic retry for transient failures:

```python
from rawagents.tools.builtin.shell._errors import execute_with_recovery

output, error = await execute_with_recovery(
    "git fetch origin",
    max_retries=2,      # Up to 3 attempts total
    retry_delay=1.0,    # 1 second between retries
)

if error:
    print(error.to_user_message())
```

**Non-retryable errors** (break immediately): `"permission denied"`, `"command not found"`

---

## Module Structure

```
src/rawagents/tools/builtin/shell/
├── __init__.py             # Package exports (9 public names)
├── bash.py                 # bash() tool + cd tracking helpers
├── bash_output.py          # bash_output() tool
├── kill_shell.py           # kill_shell() tool
├── _security.py            # ShellSecurityContext, deny patterns, sandbox
├── _process_manager.py     # ProcessInfo, ProcessManager (singleton)
├── _utils.py               # stream_output(), stream_with_timeout()
├── _errors.py              # ShellError, audit logging, recovery
└── README.md               # This file

tests/tools/builtin/shell/
├── __init__.py
├── conftest.py             # Shared fixtures (4 fixtures)
├── test_security.py        # Security validation tests (23 tests)
├── test_bash.py            # Bash execution tests (37 tests)
├── test_bash_output.py     # Output retrieval tests (5 tests)
├── test_kill_shell.py      # Process termination tests (5 tests)
├── test_process_manager.py # Process manager tests (11 tests)
└── test_edge_cases.py      # Edge case tests (18 tests)
```

### Exports (`__init__.py`)

| Name | Type | Description |
|------|------|-------------|
| `bash` | tool function | Execute shell commands |
| `bash_output` | tool function | Read background process output |
| `kill_shell` | tool function | Terminate shell processes |
| `ShellSecurityContext` | dataclass | Security and execution configuration |
| `CommandSecurityError` | exception | Raised when command is blocked |
| `SandboxNotAvailableError` | exception | Raised when sandbox tools are missing |
| `set_shell_security_context` | function | Install security context for current async task |
| `get_shell_security_context` | function | Retrieve current security context |
| `is_docker` | function | Detect Docker container environment |

### Internal Modules

| Module | Purpose | Key Classes/Functions |
|--------|---------|----------------------|
| `_security.py` | Security enforcement | `ShellSecurityContext`, `_DEFAULT_DENY_PATTERNS`, sandbox builders |
| `_process_manager.py` | Background process registry | `ProcessInfo`, `ProcessManager`, `get_process_manager()` |
| `_utils.py` | Streaming utilities | `stream_output()`, `stream_with_timeout()` |
| `_errors.py` | Error handling and logging | `ShellError`, `ShellAuditLogger`, `execute_with_recovery()` |

### Dependencies

- **External:** None (stdlib only)
- **Internal:** `rawagents.tools.tool` (the `@tool` decorator)
- **Python:** >= 3.11 (uses `TimeoutError` directly, `types.UnionType`)

---

## Testing

### Running Tests

```bash
# All shell tests
pytest tests/tools/builtin/shell/ -v

# Specific test file
pytest tests/tools/builtin/shell/test_bash.py -v

# Specific test class
pytest tests/tools/builtin/shell/test_security.py::TestDangerousCommands -v
```

### Test Summary

**99 test functions (124+ with parametrized expansion), 0 failures**

| File | Tests | Coverage |
|------|-------|----------|
| `test_security.py` | 23 (expands via `@pytest.mark.parametrize`) | Deny patterns, injection, allowlist, sandbox, shell selection, working dir, timeout |
| `test_bash.py` | 37 | Execution, errors, timeout, background, truncation, working dir, env file, cd parsing |
| `test_bash_output.py` | 5 | Output retrieval, status, timeout, truncation, not found |
| `test_kill_shell.py` | 5 | Graceful/force kill, not found, already dead, full lifecycle |
| `test_process_manager.py` | 11 | ProcessInfo, register, output, kill, buffer eviction, singleton, streaming |
| `test_edge_cases.py` | 18 | Unicode, concurrency, zombies, Docker, cd parsing, chained injection, env file, streaming |

### Fixtures

| Fixture | Purpose |
|---------|---------|
| `temp_workspace` | Temporary directory with `test.sh` script |
| `shell_context` | `ShellSecurityContext` installed via `set_shell_security_context()` |
| `sandboxed_context` | Context with sandbox enabled (skips if tools unavailable) |
| `process_manager` | Fresh `ProcessManager` with auto-cleanup |
