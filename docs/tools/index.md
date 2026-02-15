# Built-in Tools

RawAgents ships with a set of built-in tools that give agents safe, auditable access to the local file system, shell, and web. They are the same primitives you would find in a Claude Code-style agent -- read files, execute commands, search the internet -- but wrapped in a security-first design that makes them safe to hand to an LLM.

Every built-in tool is an `async def` decorated with `@tool`. It accepts typed parameters, returns a plain `str`, and signals errors by returning an `"Error: ..."` string rather than raising exceptions. This keeps the contract simple for any agent loop that consumes tool output.

---

## Modules

The tools are organised into three modules under `rawagents.tools.builtin`:

| Module | Tools | Purpose |
|--------|-------|---------|
| [`fs`](fs.md) | `read`, `write`, `edit`, `list_dir`, `glob`, `grep`, `multiedit`, `apply_patch` | File system operations with path validation, symlink protection, and read-before-edit tracking. |
| [`shell`](shell.md) | `bash`, `bash_output`, `kill_shell` | Shell command execution with command validation, timeout enforcement, and optional OS-level sandboxing. |
| [`web`](web.md) | `web_search`, `web_fetch` | Web search and page fetching with domain filtering, SSRF prevention, and rate limiting. |

---

## Shared security pattern

All three modules follow the same context pattern for security configuration:

1. A `@dataclass` holds every security setting (workspace path, deny patterns, timeouts, limits, ...).
2. The dataclass instance is stored in a `contextvars.ContextVar`, making it async-safe and thread-safe.
3. A `set_*` / `get_*` function pair manages the context variable.

| Module | Context class | Setter | Getter |
|--------|--------------|--------|--------|
| `fs` | `SecurityContext` | `set_security_context()` | `get_security_context()` |
| `shell` | `ShellSecurityContext` | `set_shell_security_context()` | `get_shell_security_context()` |
| `web` | `WebContext` | `set_web_context()` | `get_web_context()` |

If you call a tool without setting its context first, a permissive default is created and a `DeprecationWarning` is emitted. In a future release the default will change to raising an error, so always configure contexts explicitly.

---

## Quick start

```python
from rawagents.tools.builtin.fs import (
    SecurityContext,
    set_security_context,
    read,
    write,
    edit,
)
from rawagents.tools.builtin.shell import (
    ShellSecurityContext,
    set_shell_security_context,
    bash,
)
from rawagents.tools.builtin.web import (
    WebContext,
    set_web_context,
    web_search,
    web_fetch,
)

# 1. Configure security contexts
set_security_context(SecurityContext(workspace="/home/user/project"))
set_shell_security_context(ShellSecurityContext(workspace="/home/user/project"))
set_web_context(WebContext(allowed_domains=["docs.python.org"]))

# 2. Use the tools
content = await read(file_path="/home/user/project/main.py")
result = await bash("git status")
results = await web_search(query="python asyncio tutorial")
```

---

## Further reading

- [File System Tools](fs.md) -- full reference for all 8 fs tools, the `SecurityContext` dataclass, the diagnostics protocol, and the 6 matching strategies used by `edit`.
- [Shell Tools](shell.md) -- `bash`, `bash_output`, `kill_shell`, the `ShellSecurityContext` dataclass, and sandbox configuration.
- [Web Tools](web.md) -- `web_search`, `web_fetch`, the `WebContext` dataclass, search providers, and content processors.
