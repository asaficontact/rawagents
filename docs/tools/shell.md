# Shell Tools

The shell module provides **three tools** for executing and managing shell commands: `bash`, `bash_output`, and `kill_shell`. Every command passes through `ShellSecurityContext` before execution, enforcing deny-pattern matching, timeout limits, and optional OS-level sandboxing.

```python
from rawagents.tools.builtin.shell import (
    bash,
    bash_output,
    kill_shell,
    ShellSecurityContext,
    set_shell_security_context,
)
```

The package also re-exports `CommandSecurityError`, `SandboxNotAvailableError`, `ShellSession`, `get_shell_security_context`, and `is_docker`.

---

## Security Context

All shell operations are gated by a `ShellSecurityContext` instance stored in a `contextvars.ContextVar`. The context must be configured before executing any commands.

### Configuration

```python
ctx = ShellSecurityContext(workspace="/home/user/project")
set_shell_security_context(ctx)
```

Retrieve the current context with `get_shell_security_context()`. If no context has been set, a permissive default is created and a `DeprecationWarning` is emitted.

### ShellSecurityContext Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `workspace` | `str \| None` | `None` | Root directory for command execution. Commands are restricted to this directory. |
| `deny_patterns` | `list[str]` | 100+ built-in patterns | Shell glob patterns for commands that should never be executed. |
| `allow_patterns` | `list[str]` | `[]` (empty list) | If non-empty, only commands matching these patterns are allowed (allowlist mode). |
| `max_timeout` | `int` | `600000` (10 minutes) | Maximum allowed timeout in milliseconds. |
| `default_timeout` | `int` | `120000` (2 minutes) | Default timeout when not specified by the caller. |
| `shell_path` | `str \| None` | `None` | Custom shell path. If `None`, uses `$SHELL` or platform default. |
| `env_file` | `str \| None` | `None` | Path to a shell script sourced before each command for persistent environment variables. |
| `maintain_project_working_dir` | `bool` | `False` | If `True`, reset working directory to `workspace` after each command. |
| `enable_sandbox` | `bool` | `False` | Whether to wrap commands in OS-level sandbox. |
| `sandbox_allow_network` | `bool` | `False` | Whether to allow network access in sandboxed mode. |
| `sandbox_allow_write_paths` | `list[str]` | `[]` (empty list) | Paths where writing is allowed in sandbox mode (in addition to workspace). |
| `sandbox_deny_read_paths` | `list[str]` | `["~/.ssh", "~/.gnupg", "~/.aws", "~/.config/gcloud", "~/.kube", "~/.netrc", "~/.gitconfig", "~/.docker/config.json"]` | Paths to block reading even within sandbox. |

Timeouts and the env file path can also be set via environment variables:

| Environment Variable | Overrides |
|---------------------|-----------|
| `RAWAGENTS_BASH_DEFAULT_TIMEOUT_MS` | `default_timeout` |
| `RAWAGENTS_BASH_MAX_TIMEOUT_MS` | `max_timeout` |
| `RAWAGENTS_ENV_FILE` | `env_file` (only when field is `None`) |

### Working Directory Tracking

The context maintains internal state for persistent working directory tracking across commands:

| Internal Field | Type | Description |
|----------------|------|-------------|
| `_current_directory` | `Path \| None` | The current working directory, updated after successful `cd` commands. |
| `_previous_directory` | `Path \| None` | The previous working directory, enabling `cd -` support. |
| `_resolved_workspace` | `Path \| None` | Resolved (absolute) form of `workspace`. |

The `update_working_directory()` method handles `cd`, `cd ~`, `cd ~/subdir`, `cd -`, absolute paths, and relative paths. The `get_working_directory()` method returns `_current_directory`, falling back to `_resolved_workspace`, then `Path.cwd()`.

### Deny Patterns (100+ Blocked Commands)

The default deny list covers the following categories:

| Category | Examples |
|----------|----------|
| Destructive file operations | `rm -rf /`, `rm -rf ~`, `rmdir /*` |
| Disk and partition operations | `dd if=*`, `mkfs*`, `fdisk*`, `shred *` |
| Privilege escalation | `sudo *`, `su *`, `doas *`, `pkexec *`, `chmod +s *` |
| System modification | `chmod 777 /*`, `chown -R * /*`, `systemctl disable*` |
| Dangerous git operations | `git push --force*`, `git reset --hard*`, `git clean -f*`, `git branch -D *` |
| Fork bombs and resource exhaustion | `:(){ :\|:& };:`, `while true; do*`, `yes \|*` |
| Credential and history exfiltration | `cat ~/.ssh/*`, `cat /etc/shadow`, `cat */.env`, `cat *id_rsa*` |
| Network exfiltration | `*\| curl *`, `*\| wget *`, `*\| nc *`, `*> /dev/tcp/*` |
| Pipe-to-shell attacks | `curl * \| bash`, `wget * \| sh`, `eval \`curl *\`` |
| Chained command injection | `*; rm -rf *`, `*&& sudo *`, `*\|\| curl * \| *sh*` |
| Command substitution injection | `*$(rm *)*`, `*\`sudo *\`*` |
| Environment variable injection | `*="$(rm *"*` |
| Reverse shells | `*/dev/tcp/*`, `*bash -i*`, `*nc -e*`, `*python*pty.spawn*` |
| Crypto mining indicators | `*xmrig*`, `*minerd*`, `*stratum+tcp*` |
| Scheduled tasks and persistence | `crontab -r*`, `echo * >> ~/.bashrc` |
| Container escape attempts | `*nsenter*`, `*docker run*--privileged*` |
| Output redirection to system files | `*> /etc/passwd*`, `*>> ~/.ssh/authorized_keys*` |

Patterns are compiled to `re.Pattern` objects via `fnmatch.translate()` with `re.IGNORECASE | re.DOTALL` flags. Validation uses both full-match (anchored) and search-based matching for patterns starting with `*`. Chained commands are also split on `; & |` separators and each segment is individually checked.

### Sandbox Integration

When `enable_sandbox=True`, commands are wrapped in an OS-level sandbox:

| Platform | Tool | Configuration |
|----------|------|---------------|
| Linux | bubblewrap (`bwrap`) | Read-only bind mounts for `/usr`, `/lib`, `/lib64`, `/bin`, `/sbin`, `/etc`; workspace bound read-write; `--unshare-net` when network disabled; `--die-with-parent` |
| macOS | seatbelt (`sandbox-exec`) | `(deny default)` base policy; file reads allowed globally except `sandbox_deny_read_paths`; writes allowed to workspace, `sandbox_allow_write_paths`, `/tmp`, `/private/tmp`; network controlled by `sandbox_allow_network` |
| Windows | Not supported | Warning emitted; commands run without sandbox |

If `enable_sandbox=True` but the sandbox tool is not installed, a `SandboxNotAvailableError` is raised at context initialization.

### Shell Selection

The `get_shell()` method selects a shell in this priority order:

1. Explicit `shell_path` configuration
2. `$SHELL` environment variable (if compatible)
3. Platform default: `/bin/zsh` on macOS, `/bin/bash` on Linux
4. `/bin/sh` as last resort

Incompatible shells that are skipped: `fish`, `nu`, `nushell`, `xonsh`, `elvish`, `ion`, `murex`.

---

## Tool Reference

### bash

Execute a shell command.

```python
@tool
async def bash(
    command: Annotated[str, "The shell command to execute"],
    description: Annotated[str | None, "Description of what this command does"] = None,
    timeout: Annotated[int | None, "Timeout in milliseconds (max 600000)"] = None,
    run_in_background: Annotated[bool, "Run command in background, return PID"] = False,
    dangerously_disable_sandbox: Annotated[
        bool, "Override sandbox mode (use with extreme caution)"
    ] = False,
    session: Annotated[
        str | None,
        "Named shell session for persistent state (cd, env vars, venv)"
    ] = None,
) -> str:
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `command` | `str` | (required) | The shell command to execute. |
| `description` | `str \| None` | `None` | Human-readable description of the command. Not used at runtime. |
| `timeout` | `int \| None` | `None` | Timeout in milliseconds. Defaults to `default_timeout` (120000ms). Clamped to `max_timeout` (600000ms). |
| `run_in_background` | `bool` | `False` | If `True`, start the command as a background process and return the PID immediately. |
| `dangerously_disable_sandbox` | `bool` | `False` | Override sandbox mode even when `enable_sandbox=True` on the security context. |
| `session` | `str \| None` | `None` | Named shell session for persistent state. Incompatible with `run_in_background`. |

**Behavior:**

- **Command validation**: Every command is validated against `ShellSecurityContext.deny_patterns` before execution. Blocked commands return an `"Error: ..."` string.
- **Foreground mode** (default): Runs the command, waits for completion, returns combined stdout/stderr.
- **Background mode** (`run_in_background=True`): Starts the command, registers it with `ProcessManager`, and returns `"Started background process with PID: <pid>"`.
- **Session mode** (`session="name"`): Executes the command in a named persistent shell session. Cannot be combined with `run_in_background`.
- **Timeout handling**: On timeout, sends SIGTERM to the process group. If the process does not exit within 5 seconds, SIGKILL is sent. Returns `"Error: Command timed out after <N> seconds"`.
- **Working directory tracking**: After a successful command, `cd` targets are parsed and the security context's working directory is updated. Supports `cd`, `cd ~`, `cd ~/subdir`, `cd -`, absolute paths, relative paths, and `cd` chained with `&&`, `||`, `;`, or `|`.
- **Environment file sourcing**: When `env_file` is configured, each command is prefixed with `. "<env_file>" && <command>`.
- **Output truncation**: Output is truncated at **2000 lines** and/or **50KB** (whichever limit is hit first). When truncated, the full output is saved to a temporary file and the path is included in the response.
- **`maintain_project_working_dir`**: When enabled on the security context, the working directory is reset to `workspace` after each command.
- **Process groups**: Subprocesses are created with `start_new_session=True`, enabling process-group-level signal delivery for reliable cleanup.

**Returns:**

| Condition | Return value |
|-----------|-------------|
| Success with output | The stripped stdout/stderr output |
| Success with no output | `"(no output)"` |
| Non-zero exit code | `"Error: Command failed with exit code <N>\n<output>"` |
| Blocked by security | `"Error: <reason>"` |
| Timeout | `"Error: Command timed out after <N> seconds"` |
| Background mode | `"Started background process with PID: <pid>"` |
| Session + background | `"Error: Background execution is not supported with named sessions."` |

---

### bash_output

Read output from a background bash command.

```python
@tool
async def bash_output(
    pid: Annotated[str, "Process ID of the background command"],
    timeout: Annotated[int | None, "Timeout in ms to wait for new output"] = 5000,
) -> str:
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pid` | `str` | (required) | Process ID returned by `bash(run_in_background=True)`. |
| `timeout` | `int \| None` | `5000` | Maximum time in milliseconds to wait for new output. Falls back to `5000` if `None`. |

**Behavior:**

- Returns new output since the last read, along with the process status (`"Process status: running"` or `"Process status: completed (exit code <N>)"`).
- Output is truncated at **50KB**. When truncated, the message `"... (output truncated at 50KB)"` is appended.
- Uses event-based waiting: returns as soon as new output is available rather than sleeping for the full timeout.

---

### kill_shell

Terminate a running shell process.

```python
@tool
async def kill_shell(
    pid: Annotated[str, "Process ID to terminate"],
    force: Annotated[bool, "Use SIGKILL instead of SIGTERM"] = False,
) -> str:
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pid` | `str` | (required) | Process ID to terminate. |
| `force` | `bool` | `False` | If `True`, send SIGKILL immediately instead of SIGTERM. |

**Behavior:**

- Default mode sends SIGTERM to the process group for graceful shutdown. If the process does not exit within 5 seconds, SIGKILL is sent automatically.
- With `force=True`, sends SIGKILL immediately without waiting.
- Kills the entire process group (via `os.killpg`) to include child processes.
- Returns `"Process <pid> terminated successfully"` on success, `"Process <pid> already terminated"` if already exited, or `"Error: ..."` on failure.

---

## Named Shell Sessions

The `session` parameter on the `bash` tool enables persistent interactive shell sessions where state (working directory, environment variables, virtual environments) carries over between calls.

### Usage

```python
# First call creates the session
await bash("cd /tmp && export MY_VAR=hello", session="build")

# Second call reuses the same shell process
await bash("echo $MY_VAR && pwd", session="build")
# Output: hello\n/tmp
```

### ShellSession Dataclass

```python
@dataclass
class ShellSession:
    name: str                    # User-chosen session name (e.g., "build", "test")
    process: asyncio.subprocess.Process  # The underlying shell subprocess
    lock: asyncio.Lock           # Per-session lock to serialize command execution
    created_at: datetime         # When the session was created
```

The `is_alive` property returns `True` if the underlying process is still running (`process.returncode is None`).

### Sentinel-Based Execution

Commands in named sessions use a sentinel-based output detection pattern (inspired by SWE-ReX). When a command is submitted:

1. A unique sentinel string is generated: `___SENTINEL_<8-hex-chars>___`
2. The command is sent as: `<command>; echo "<sentinel>$?"\n`
3. Output lines are collected until one starts with the sentinel
4. The exit code is extracted from the text following the sentinel

This avoids the need for prompts, timing heuristics, or output length guesses. Each session uses an `asyncio.Lock` to serialize concurrent command requests.

### Session Lifecycle

- **Creation**: `get_or_create_session(name, cwd)` creates a new `bash --norc --noprofile` process if no alive session exists with that name.
- **Reuse**: Subsequent calls to `get_or_create_session()` with the same name return the existing session if its process is still alive.
- **Replacement**: If an existing session's process has died, a new session is created in its place.
- **Closing**: `close_session(name)` sends SIGTERM, waits up to 5 seconds, then escalates to SIGKILL.
- **Listing**: `list_sessions()` returns a `dict[str, bool]` mapping session name to alive status.

### Restrictions

Named sessions cannot be combined with `run_in_background=True`. Attempting to do so returns an error.

---

## Process Manager

The `ProcessManager` class maintains a registry of all background processes started by the bash tool, plus all named shell sessions.

### Singleton Access

```python
from rawagents.tools.builtin.shell._process_manager import get_process_manager

manager = get_process_manager()
```

The process manager is a module-level singleton (not a `ContextVar`) because OS processes are inherently global -- a background process started in one coroutine must be killable from another.

### ProcessInfo Dataclass

Each tracked background process is represented by a `ProcessInfo`:

```python
@dataclass
class ProcessInfo:
    pid: int                         # OS process ID
    process: asyncio.subprocess.Process  # The asyncio subprocess
    command: str                     # The command that was executed
    started_at: datetime             # When the process was started
    output_buffer: list[str]         # Accumulated output lines
    last_read_index: int             # Index for incremental reads (default 0)
```

| Property | Type | Description |
|----------|------|-------------|
| `is_running` | `bool` | `True` if `process.returncode is None` |
| `exit_code` | `int \| None` | The return code, or `None` if still running |

The output buffer has a hard cap of `MAX_BUFFER_LINES = 10_000` lines. When exceeded, the oldest lines are evicted and `last_read_index` is adjusted accordingly.

### Output Collection

Background output is collected via a dedicated `asyncio.Task` that reads lines from the process stdout. An `asyncio.Event` (`_new_output_event`) is signaled on each new line, allowing `get_output()` to wake immediately rather than polling.

### ProcessManager Methods

| Method | Description |
|--------|-------------|
| `register(process, command)` | Register a background process and start output collection. Returns the PID as a string. |
| `get_output(pid, timeout=5000)` | Get new output since last read. Returns `(output, status)` tuple. |
| `kill(pid, force=False)` | Terminate a process. SIGTERM with 5-second SIGKILL escalation by default. |
| `get_or_create_session(name, cwd, env=None)` | Get or create a named shell session. |
| `execute_in_session(session, command, timeout_sec=120)` | Execute a command in a named session. Returns `(output, exit_code)`. |
| `close_session(name)` | Close a named session. |
| `list_sessions()` | List all sessions with alive status. |
| `cleanup()` | Force-kill all tracked processes and close all sessions. |
