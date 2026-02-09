# Product Requirements Document (PRD)
# RawAgents Tool Extensibility & Customization System

**Version:** 1.0
**Date:** February 2026
**Status:** Draft
**Author:** Tawab Safi

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Background & Motivation](#2-background--motivation)
3. [Goals & Non-Goals](#3-goals--non-goals)
4. [Industry Analysis](#4-industry-analysis)
5. [Current Architecture Assessment](#5-current-architecture-assessment)
6. [Proposed Architecture](#6-proposed-architecture)
7. [Detailed Design](#7-detailed-design)
8. [API Design](#8-api-design)
9. [Migration Path](#9-migration-path)
10. [Testing Strategy](#10-testing-strategy)
11. [Risks & Mitigations](#11-risks--mitigations)
12. [Success Criteria](#12-success-criteria)
13. [Implementation Plan](#13-implementation-plan)
14. [Appendix: Evaluated Options](#14-appendix-evaluated-options)

---

## 1. Executive Summary

### 1.1 What We're Building

A **Tool Extensibility System** for RawAgents that enables users to customize, override, extend, and compose built-in tools without forking the library. This system introduces three core mechanisms:

1. **Middleware Chain** — Intercept tool execution with pre/post hooks that can modify inputs, outputs, or short-circuit execution entirely.
2. **Configurable Internals** — Surface hardcoded constants, security patterns, and strategy chains as configurable parameters.
3. **Tool Composition** — Enable wrapping, extending, and replacing built-in tools while preserving the `@tool` decorator contract.

### 1.2 Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Extension Model** | Middleware chain (onion/Django pattern) | Proven pattern, zero-coupling, composable |
| **Configuration** | `ToolConfig` dataclass per tool category | Type-safe, discoverable, no magic strings |
| **Override Strategy** | Wrap-and-delegate (not subclass) | Preserves `@tool` contract, no inheritance needed |
| **Security Patterns** | Additive modification (add/remove) | Safer than full override, preserves defaults |
| **Backward Compatibility** | 100% — all new features are opt-in | Zero breaking changes to existing code |

### 1.3 Core Principle

**"Extend, Don't Fork"**: Users should never need to copy-paste a built-in tool's source code to change its behavior. Every behavioral aspect should be customizable through composition or configuration.

---

## 2. Background & Motivation

### 2.1 Problem Statement

RawAgents' built-in tools (filesystem, shell) are well-designed for default use cases, but users cannot easily customize them for their specific needs:

1. **Hardcoded Constants** — Output limits (50KB), line limits (2000), timeouts (5s for locks, 5s for SIGTERM grace) are baked into source code with no override mechanism.
2. **Closed Security Patterns** — Deny/allow pattern lists can only be replaced wholesale (no `add_pattern()` or `remove_pattern()` API). Default patterns are stored in private module-level variables (`_DEFAULT_DENY_PATTERNS`).
3. **No Middleware** — PRD 003 (Tool Executor) listed "G4: Middleware Support" as a goal, but only simple `on_before`/`on_after` callbacks were implemented. These callbacks cannot modify inputs, outputs, or short-circuit execution.
4. **Hardcoded Strategy Chains** — The replacer strategy chain in `_replacers.py` is a module-level list with no way to reorder, skip, or inject custom strategies.
5. **Global Singletons** — `ProcessManager`, `ShellAuditLogger`, and security contexts use module-level singletons that can't be swapped for testing or customization.

### 2.2 Real-World Use Cases

| Use Case | Current Pain | Desired Behavior |
|----------|-------------|-----------------|
| **Custom search API in web_search tool** | Must write tool from scratch | Swap the HTTP provider, keep the schema/validation |
| **Add deny pattern to shell** | Must import private `_DEFAULT_DENY_PATTERNS`, copy all 100+ entries, append, pass full list | `ctx.add_deny_pattern("my-pattern")` |
| **Log all tool calls to external system** | `on_before`/`on_after` callbacks can observe but not modify | Middleware can log, modify, retry, or reject |
| **Increase shell output limit for CI** | Must fork `bash.py` to change `MAX_OUTPUT_BYTES` | Pass `ToolConfig(max_output_bytes=200_000)` |
| **Custom file edit strategy** | Must fork `_replacers.py` | Register custom `Replacer` in strategy chain |
| **Rate-limit tool calls** | Not possible without wrapping executor | Middleware with rate limiter state |
| **Approval workflow** | `on_before` can't block execution | Middleware raises or returns early |

### 2.3 Design Philosophy

Following RawAgents' "Primitives over Frameworks" philosophy:

- **Functions, not classes** — Extension points are callables, not abstract base classes
- **Composition, not inheritance** — Wrap tools, don't subclass them
- **Explicit, not magic** — Configuration is visible in code, not hidden in config files
- **Opt-in, not mandatory** — Everything works without configuration (zero-config default)

---

## 3. Goals & Non-Goals

### 3.1 Goals

**G1: Middleware Chain for ToolExecutor**
- Middleware functions that wrap tool execution with pre/post logic
- Can modify `ToolCall` arguments before execution
- Can modify `ToolResult` content after execution
- Can short-circuit execution (reject, cache, redirect)
- Composable: multiple middleware stack in order

**G2: Configurable Tool Parameters**
- Surface hardcoded constants as named parameters
- Type-safe configuration via dataclasses
- Per-tool and per-category configuration
- Sensible defaults (zero-config works identically to today)

**G3: Security Pattern Modification API**
- `add_deny_pattern()` / `remove_deny_pattern()` for incremental changes
- Access to default pattern lists as public constants
- Merge semantics (user patterns + defaults, not replace)

**G4: Tool Composition & Override**
- Wrap a built-in tool with custom pre/post logic
- Replace a built-in tool's implementation while keeping its schema
- Create tool variants (same logic, different defaults)
- Register custom tools alongside built-in ones

**G5: Pluggable Internal Components**
- Replacer strategy chain is configurable
- ProcessManager can be swapped (for testing)
- AuditLogger is injectable
- Security contexts support factory pattern

### 3.2 Non-Goals

**NG1: Plugin System with Discovery**
- We will NOT implement automatic plugin discovery (entry_points, file scanning). Users explicitly register extensions in code.

**NG2: Remote Tool Execution**
- We will NOT implement RPC, MCP server hosting, or network-based tool dispatch. Tools execute in-process.

**NG3: GUI Configuration**
- No YAML/JSON config files, no web UI. All configuration is Python code.

**NG4: Runtime Hot-Reload**
- Middleware and configuration are set at initialization time, not changed during execution.

**NG5: Breaking Changes**
- Zero breaking changes. All existing code must work identically without modification.

---

## 4. Industry Analysis

### 4.1 Middleware & Hook Patterns

| Framework | Pattern | Mechanism | Strengths | Weaknesses |
|-----------|---------|-----------|-----------|------------|
| **Django** | Onion middleware | `get_response` callable chain, `process_request`/`process_response` | Battle-tested, composable | Tied to HTTP request/response model |
| **FastAPI** | `Depends()` DI | Type-hint-based dependency injection | Elegant, testable, chains dependencies | Dependencies are values, not behavior interceptors |
| **pytest/pluggy** | Hook specs + impls | `@hookspec`/`@hookimpl` with `tryfirst`/`trylast`/`wrapper` | Extremely flexible ordering, N-to-1 | Complex API surface, learning curve |
| **Vercel AI SDK** | `wrapLanguageModel` | `wrapGenerate`/`wrapStream` middleware functions | Clean composition, provider-agnostic | TypeScript-specific, model-level not tool-level |
| **OpenAI Agents SDK** | `FunctionTool` class | `on_invoke_tool`, `is_enabled`, `tool_use_behavior` | Direct tool-level control | No middleware chain, per-tool only |
| **Express.js** | `use()` middleware | `(req, res, next)` pattern | Simple, well-understood | No type safety |

### 4.2 Tool Extension Patterns

| Framework | Extension Mechanism | How Users Customize |
|-----------|-------------------|-------------------|
| **LangChain** | Subclass `BaseTool` | Override `_run()` method, custom `args_schema` |
| **CrewAI** | `@tool` decorator + `BaseTool` | Decorator for simple, class for complex |
| **AutoGen** | `register_function()` | Register plain functions on agents |
| **Semantic Kernel** | `@kernel_function` decorator | Plugin classes with decorated methods |
| **Anthropic API** | Tool definition dicts | Pass tool schemas + handler functions |
| **Google Gemini** | `FunctionDeclaration` | Schema objects + callback functions |
| **MCP (Model Context Protocol)** | `@server.call_tool()` | Server-side tool handlers with JSON Schema |

### 4.3 Key Insights from Industry

1. **Django's onion model is the gold standard** for middleware — each layer wraps the next, enabling clean pre/post processing without coupling.
2. **FastAPI's `Depends()` is elegant for DI** but not directly applicable to behavior interception (rawagents already has `Annotated[T, Inject]`).
3. **pluggy is too complex** for our needs — we don't need N-to-1 hook dispatch, just a linear middleware chain.
4. **OpenAI Agents SDK's `FunctionTool`** provides the right granularity (per-tool control) but lacks composability (no middleware chain).
5. **The "wrap" pattern** (Vercel AI SDK's `wrapLanguageModel`) is the cleanest — create a new entity that delegates to the original while adding behavior.

### 4.4 Recommended Approach

Combine **Django-style middleware chain** on the executor with **OpenAI-style per-tool configuration** and **Vercel-style wrap pattern** for individual tool override:

```
┌─────────────────────────────────────────────────────────┐
│                    ToolExecutor                          │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │ Middleware Chain (Django-style onion)            │    │
│  │                                                 │    │
│  │  ┌──────────────────────────────────────────┐   │    │
│  │  │ Rate Limiter                             │   │    │
│  │  │  ┌───────────────────────────────────┐   │   │    │
│  │  │  │ Logger                            │   │   │    │
│  │  │  │  ┌────────────────────────────┐   │   │   │    │
│  │  │  │  │ Approval Gate              │   │   │   │    │
│  │  │  │  │  ┌─────────────────────┐   │   │   │   │    │
│  │  │  │  │  │ Tool Execution      │   │   │   │   │    │
│  │  │  │  │  └─────────────────────┘   │   │   │   │    │
│  │  │  │  └────────────────────────────┘   │   │   │    │
│  │  │  └───────────────────────────────────┘   │   │    │
│  │  └──────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  ToolConfig: {max_output_bytes, deny_patterns, ...}     │
└─────────────────────────────────────────────────────────┘
```

---

## 5. Current Architecture Assessment

### 5.1 What Works Well

| Aspect | Assessment |
|--------|-----------|
| `@tool` decorator | Clean, minimal, attaches metadata without changing function behavior |
| `ToolExecutor` registry | Simple `register()`/`unregister()` with name-based lookup |
| `Annotated[T, Inject]` DI | Elegant, zero-overhead, invisible to LLM |
| `SecurityContext` via `contextvars` | Async-safe, per-task isolation |
| Error-as-string pattern | Tools return `"Error: ..."` strings, never raise — safe for LLM consumption |

### 5.2 Extension Barriers (Detailed)

#### Barrier 1: `on_before`/`on_after` Cannot Modify Execution

```python
# Current implementation (executor.py)
class ToolExecutor:
    def __init__(
        self,
        tools: list[Callable[..., Any]] | None = None,
        on_before: Callable[[ToolCall], None] | None = None,      # observe only
        on_after: Callable[[ToolCall, ToolResult], None] | None = None,  # observe only
    ) -> None:
```

**Problem**: `on_before` returns `None` — it cannot modify the `ToolCall` or prevent execution. `on_after` returns `None` — it cannot modify the `ToolResult`. Both silently swallow exceptions.

#### Barrier 2: Hardcoded Constants

```python
# bash.py
MAX_OUTPUT_BYTES = 50_000    # No way to change without forking
MAX_OUTPUT_LINES = 2_000     # No way to change without forking

# read.py
MAX_OUTPUT_BYTES = 50_000    # Same
DEFAULT_LINE_LIMIT = 2_000   # Same

# _process_manager.py
MAX_BUFFER_LINES = 10_000    # ClassVar, no configuration
```

#### Barrier 3: Private Default Patterns

```python
# fs/_security.py
_DEFAULT_DENIED_PATTERNS = [...]  # Private, 40+ patterns
_DEFAULT_BINARY_EXTENSIONS = {..}  # Private frozenset

# shell/_security.py
_DEFAULT_DENY_PATTERNS = [...]  # Private, 100+ patterns
```

Users can override the entire list but cannot incrementally add/remove:
```python
# Must copy ALL defaults to add one pattern
ctx = SecurityContext(denied_patterns=[...all 40+...] + ["my-pattern"])
```

#### Barrier 4: Hardcoded Strategy Chain

```python
# _replacers.py — module-level, no configuration
_STRATEGIES: list[Replacer] = [
    SimpleReplacer(),
    LineTrimmedReplacer(),
    BlockAnchorReplacer(),
    WhitespaceNormalizedReplacer(),
    IndentationFlexibleReplacer(),
]

def find_and_replace(content, old, new, replace_all):
    for strategy in _STRATEGIES:  # Always all 5, always this order
        ...
```

#### Barrier 5: Module-Level Singletons

```python
# _process_manager.py
_default_manager: ProcessManager | None = None
def get_process_manager() -> ProcessManager:
    global _default_manager  # Cannot swap for testing
    ...

# _errors.py
_audit_logger: ShellAuditLogger | None = None
def get_audit_logger() -> ShellAuditLogger | None:
    return _audit_logger  # Cannot inject per-request
```

### 5.3 Dependency Graph

```
ToolExecutor
├── register(func)     → checks __tool_name__
├── execute(call, ctx) → finds func, injects context, calls
│   ├── _validate_and_coerce_arguments()
│   ├── original_func(**kwargs)
│   └── _serialize_output()
└── on_before / on_after → observe only

@tool decorator
├── _validate_signature(func)
├── generate_tool_schema(name, desc, func, injected)
└── attaches: __tool_name__, __tool_schema__, __tool_is_async__,
             __tool_injected_params__, __tool_original_func__

Built-in Tool (e.g., bash)
├── get_shell_security_context()  → contextvars singleton
├── ctx.validate_command()        → deny pattern matching
├── ctx.get_working_directory()   → persistent state
├── get_process_manager()         → module singleton
├── get_audit_logger()            → module singleton (optional)
└── _utils.stream_with_timeout()  → utility function

Built-in Tool (e.g., edit)
├── get_security_context()        → contextvars singleton
├── validate_path_or_error()      → utility function
├── require_read_before_edit()    → session state check
├── file_lock()                   → TOCTOU protection
├── find_and_replace()            → hardcoded strategy chain
└── awrite_text()                 → async I/O
```

---

## 6. Proposed Architecture

### 6.1 High-Level Design

```
┌──────────────────────────────────────────────────────────────────────┐
│                            User Code                                 │
│                                                                      │
│  executor = ToolExecutor(                                            │
│      tools=[bash, read, write, my_custom_tool],                      │
│      middleware=[rate_limiter, logger, approval_gate],                │
│      config=ToolConfig(shell=ShellToolConfig(max_output_bytes=100K)) │
│  )                                                                   │
└──────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         ToolExecutor                                 │
│                                                                      │
│  1. Find tool by name                                                │
│  2. Run middleware chain:                                            │
│     middleware[0](call, context, next) →                              │
│       middleware[1](call, context, next) →                            │
│         middleware[2](call, context, next) →                          │
│           actual_tool_execution()                                    │
│  3. Return ToolResult                                                │
└──────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    Configurable Components                           │
│                                                                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────┐     │
│  │ SecurityContext  │  │ ProcessManager  │  │ Replacer Chain   │     │
│  │ + add_pattern()  │  │ (injectable)    │  │ (configurable)   │     │
│  │ + remove_pattern │  │                 │  │                  │     │
│  └─────────────────┘  └─────────────────┘  └──────────────────┘     │
└──────────────────────────────────────────────────────────────────────┘
```

### 6.2 Component Summary

| Component | Purpose | New/Modified |
|-----------|---------|-------------|
| `ToolMiddleware` | Protocol for middleware functions | **New** |
| `ToolExecutor` (enhanced) | Middleware chain execution | **Modified** |
| `ToolConfig` | Configuration dataclass hierarchy | **New** |
| `SecurityContext` (enhanced) | Add/remove pattern methods | **Modified** |
| `ShellSecurityContext` (enhanced) | Add/remove pattern methods | **Modified** |
| `DEFAULT_FS_DENIED_PATTERNS` | Public constant | **New** (expose existing) |
| `DEFAULT_SHELL_DENY_PATTERNS` | Public constant | **New** (expose existing) |
| `wrap_tool()` | Tool composition helper | **New** |
| `find_and_replace()` (enhanced) | Accept custom strategy list | **Modified** |

---

## 7. Detailed Design

### 7.1 Middleware System

#### 7.1.1 Middleware Protocol

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class ToolMiddleware(Protocol):
    """Protocol for tool execution middleware.

    Middleware wraps tool execution in an onion-layer pattern.
    Each middleware receives the call context and a `next_handler`
    function to invoke the next middleware (or the actual tool).

    The middleware CAN:
    - Modify the ToolCall before passing to next_handler
    - Modify the ToolResult after receiving from next_handler
    - Short-circuit by returning a ToolResult without calling next_handler
    - Raise exceptions (caught by executor, returned as error ToolResult)
    """

    async def __call__(
        self,
        call: ToolCall,
        context: dict[str, Any],
        next_handler: Callable[..., Awaitable[ToolResult]],
    ) -> ToolResult: ...
```

#### 7.1.2 Middleware Examples

```python
# Logging middleware
async def logging_middleware(
    call: ToolCall,
    context: dict[str, Any],
    next_handler: Callable[..., Awaitable[ToolResult]],
) -> ToolResult:
    print(f"[LOG] Calling {call.name} with {call.arguments}")
    result = await next_handler(call, context)
    print(f"[LOG] {call.name} returned (error={result.is_error})")
    return result

# Rate limiting middleware
class RateLimiter:
    def __init__(self, max_calls_per_minute: int = 60):
        self.max_calls = max_calls_per_minute
        self._calls: list[float] = []

    async def __call__(
        self,
        call: ToolCall,
        context: dict[str, Any],
        next_handler: Callable[..., Awaitable[ToolResult]],
    ) -> ToolResult:
        now = time.monotonic()
        self._calls = [t for t in self._calls if now - t < 60]
        if len(self._calls) >= self.max_calls:
            return ToolResult(
                tool_call_id=call.id,
                name=call.name,
                content="Error: Rate limit exceeded. Try again later.",
                is_error=True,
            )
        self._calls.append(now)
        return await next_handler(call, context)

# Approval gate middleware
async def approval_gate(
    call: ToolCall,
    context: dict[str, Any],
    next_handler: Callable[..., Awaitable[ToolResult]],
) -> ToolResult:
    """Block dangerous tools unless pre-approved."""
    dangerous_tools = {"bash", "write", "edit", "kill_shell"}
    if call.name in dangerous_tools:
        approver = context.get("approval_callback")
        if approver and not await approver(call):
            return ToolResult(
                tool_call_id=call.id,
                name=call.name,
                content="Error: Tool call rejected by approval policy.",
                is_error=True,
            )
    return await next_handler(call, context)

# Input/output modification middleware
async def redact_secrets(
    call: ToolCall,
    context: dict[str, Any],
    next_handler: Callable[..., Awaitable[ToolResult]],
) -> ToolResult:
    result = await next_handler(call, context)
    # Redact API keys from output
    content = re.sub(r'sk-[a-zA-Z0-9]{20,}', '[REDACTED]', result.content)
    return ToolResult(
        tool_call_id=result.tool_call_id,
        name=result.name,
        content=content,
        is_error=result.is_error,
    )
```

#### 7.1.3 Middleware Chain Execution

The executor builds an execution chain at initialization time:

```
call → middleware[0] → middleware[1] → ... → middleware[N] → tool_execution
                                                                    ↓
result ← middleware[0] ← middleware[1] ← ... ← middleware[N] ← tool_result
```

Each middleware calls `next_handler(call, context)` to proceed, or returns a `ToolResult` directly to short-circuit.

### 7.2 Configuration System

#### 7.2.1 Configuration Hierarchy

```python
@dataclass(frozen=True)
class FSToolConfig:
    """Configuration for filesystem tools."""
    max_output_bytes: int = 50_000
    default_line_limit: int = 2_000
    max_line_length: int = 2_000
    max_glob_results: int = 100
    max_grep_matches: int = 100
    max_list_files: int = 100
    streaming_threshold: int = 10_485_760  # 10MB
    replacer_strategies: list[Replacer] | None = None  # None = use defaults

@dataclass(frozen=True)
class ShellToolConfig:
    """Configuration for shell tools."""
    max_output_bytes: int = 50_000
    max_output_lines: int = 2_000
    max_buffer_lines: int = 10_000
    sigterm_grace_seconds: float = 5.0
    default_timeout_ms: int = 120_000
    max_timeout_ms: int = 600_000

@dataclass(frozen=True)
class ToolConfig:
    """Top-level tool configuration."""
    fs: FSToolConfig = field(default_factory=FSToolConfig)
    shell: ShellToolConfig = field(default_factory=ShellToolConfig)
```

#### 7.2.2 Configuration Flow

```python
# User creates config with overrides
config = ToolConfig(
    shell=ShellToolConfig(max_output_bytes=200_000),
    fs=FSToolConfig(max_glob_results=500),
)

# Pass to executor
executor = ToolExecutor(
    tools=[bash, read, edit],
    config=config,
)

# Tools access config via injection
@tool
async def bash(
    command: Annotated[str, "The shell command to execute"],
    config: Annotated[ShellToolConfig, Inject],  # Injected by executor
) -> str:
    max_bytes = config.max_output_bytes  # Uses user's 200_000
    ...
```

**Alternative (no-injection approach)**: Tools read config from the security context, which already uses `contextvars`:

```python
# Tools access config from context
ctx = get_shell_security_context()
max_bytes = ctx.config.max_output_bytes  # Via context attribute
```

### 7.3 Security Pattern Modification

#### 7.3.1 Public Constants

```python
# fs/_security.py — make public
DEFAULT_FS_DENIED_PATTERNS: tuple[str, ...] = (
    "*.env", "*.env.*", ".env", ".env.*",
    "*credentials*", "*secret*", ...
)

DEFAULT_FS_BINARY_EXTENSIONS: frozenset[str] = frozenset({
    ".exe", ".dll", ".so", ...
})

# shell/_security.py — make public
DEFAULT_SHELL_DENY_PATTERNS: tuple[str, ...] = (
    "rm -rf /*", "rm -rf /", "sudo *", ...
)
```

#### 7.3.2 Incremental Modification API

```python
# SecurityContext gets new methods
@dataclass
class SecurityContext:
    ...

    def add_denied_pattern(self, pattern: str) -> None:
        """Add a pattern to the deny list."""
        if pattern not in self.denied_patterns:
            self.denied_patterns.append(pattern)

    def remove_denied_pattern(self, pattern: str) -> None:
        """Remove a pattern from the deny list.

        Raises:
            ValueError: If pattern not in deny list.
        """
        self.denied_patterns.remove(pattern)

    def add_allowed_pattern(self, pattern: str) -> None:
        """Add a pattern to the allow list (overrides deny)."""
        if pattern not in self.allowed_patterns:
            self.allowed_patterns.append(pattern)

    def remove_allowed_pattern(self, pattern: str) -> None:
        """Remove a pattern from the allow list."""
        self.allowed_patterns.remove(pattern)

# Usage:
ctx = SecurityContext(workspace="/project")
ctx.add_denied_pattern("*.bak")
ctx.remove_denied_pattern("*.env")  # Allow .env files
ctx.add_allowed_pattern("config/.env.example")  # But allow this specific one
```

```python
# ShellSecurityContext gets same methods
@dataclass
class ShellSecurityContext:
    ...

    def add_deny_pattern(self, pattern: str) -> None:
        """Add a command pattern to the deny list."""
        if pattern not in self.deny_patterns:
            self.deny_patterns.append(pattern)

    def remove_deny_pattern(self, pattern: str) -> None:
        """Remove a command pattern from the deny list."""
        self.deny_patterns.remove(pattern)
```

### 7.4 Tool Composition

#### 7.4.1 `wrap_tool()` Helper

```python
def wrap_tool(
    original: Callable[..., Any],
    *,
    name: str | None = None,
    description: str | None = None,
    before: Callable[..., dict[str, Any] | None] | None = None,
    after: Callable[..., str | None] | None = None,
) -> Callable[..., Any]:
    """Create a new tool that wraps an existing one.

    Args:
        original: The @tool-decorated function to wrap.
        name: Override tool name (default: keep original).
        description: Override description (default: keep original).
        before: Called before execution. Receives kwargs, returns modified
                kwargs or None to keep original. Return a string to
                short-circuit with that as the result.
        after: Called after execution. Receives (result_string, kwargs),
               returns modified result or None to keep original.

    Returns:
        A new @tool-decorated function with the wrapper behavior.

    Example:
        from rawagents.tools.builtin.shell import bash

        # Add logging to bash
        def log_before(**kwargs):
            print(f"Running: {kwargs['command']}")
            return None  # Don't modify args

        def log_after(result, **kwargs):
            print(f"Output length: {len(result)}")
            return None  # Don't modify result

        logged_bash = wrap_tool(bash, before=log_before, after=log_after)

        # Override bash to add a custom prefix
        def add_prefix(**kwargs):
            kwargs["command"] = f"set -euo pipefail; {kwargs['command']}"
            return kwargs

        strict_bash = wrap_tool(
            bash,
            name="strict_bash",
            description="Execute shell commands with strict mode enabled",
            before=add_prefix,
        )
    """
```

#### 7.4.2 Tool Replacement Pattern

```python
# Replace built-in tool in executor
executor = ToolExecutor(tools=[read, write, edit])

# Unregister built-in, register custom
executor.unregister("bash")
executor.register(my_custom_bash)

# OR: Use force parameter (new)
executor.register(my_custom_bash, force=True)  # Replaces existing
```

### 7.5 Pluggable Internal Components

#### 7.5.1 Replacer Strategy Configuration

```python
# find_and_replace gains optional strategies parameter
def find_and_replace(
    content: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
    strategies: list[Replacer] | None = None,  # None = use defaults
) -> ReplaceResult:
    """Find and replace text using a chain of strategies.

    Args:
        ...
        strategies: Custom strategy list. If None, uses default chain:
                    [Simple, LineTrimmed, BlockAnchor,
                     WhitespaceNormalized, IndentationFlexible]
    """
    active_strategies = strategies if strategies is not None else _STRATEGIES
    for strategy in active_strategies:
        ...
```

#### 7.5.2 Injectable Singletons

```python
# ProcessManager supports custom instances
class ShellSecurityContext:
    ...
    process_manager: ProcessManager | None = None  # None = use default singleton

    def get_process_manager(self) -> ProcessManager:
        """Get the process manager for this context."""
        if self.process_manager is not None:
            return self.process_manager
        return get_process_manager()  # Fall back to global singleton
```

---

## 8. API Design

### 8.1 Enhanced ToolExecutor

```python
class ToolExecutor:
    """Execute tools safely with dependency injection and middleware.

    New in v0.2:
    - Middleware chain for intercepting tool execution
    - ToolConfig for customizable tool parameters
    - force parameter on register() for tool replacement
    """

    def __init__(
        self,
        tools: list[Callable[..., Any]] | None = None,
        middleware: list[ToolMiddleware] | None = None,
        config: ToolConfig | None = None,
        # Legacy callbacks (still supported, run inside middleware chain)
        on_before: Callable[[ToolCall], None] | None = None,
        on_after: Callable[[ToolCall, ToolResult], None] | None = None,
    ) -> None: ...

    def register(
        self,
        func: Callable[..., Any],
        *,
        force: bool = False,
    ) -> None:
        """Register a @tool decorated function.

        Args:
            func: A function decorated with @tool.
            force: If True, replace existing tool with same name.
                   If False (default), raise ValueError on duplicate.
        """

    async def execute(
        self,
        tool_call: ToolCall,
        context: dict[str, Any] | None = None,
    ) -> ToolResult:
        """Execute a tool call through the middleware chain."""

    def use(self, middleware: ToolMiddleware) -> None:
        """Add middleware to the end of the chain.

        Can be called after initialization.
        """
```

### 8.2 Public Exports (New)

```python
# rawagents/tools/__init__.py — new exports
from rawagents.tools.middleware import ToolMiddleware
from rawagents.tools.config import ToolConfig, FSToolConfig, ShellToolConfig
from rawagents.tools.composition import wrap_tool

# rawagents/tools/builtin/fs/__init__.py — new exports
from rawagents.tools.builtin.fs._security import (
    DEFAULT_FS_DENIED_PATTERNS,
    DEFAULT_FS_BINARY_EXTENSIONS,
)

# rawagents/tools/builtin/shell/__init__.py — new exports
from rawagents.tools.builtin.shell._security import (
    DEFAULT_SHELL_DENY_PATTERNS,
)
```

### 8.3 Complete Usage Example

```python
from rawagents.tools import (
    ToolExecutor, ToolConfig, tool, Inject, wrap_tool,
)
from rawagents.tools.config import ShellToolConfig, FSToolConfig
from rawagents.tools.builtin.fs import read, write, edit
from rawagents.tools.builtin.shell import bash, bash_output, kill_shell

# 1. Configure tools
config = ToolConfig(
    shell=ShellToolConfig(
        max_output_bytes=200_000,      # 200KB for CI environments
        sigterm_grace_seconds=10.0,     # Longer grace for build processes
    ),
    fs=FSToolConfig(
        max_glob_results=500,           # Larger codebases
    ),
)

# 2. Define middleware
async def audit_middleware(call, context, next_handler):
    """Log all tool calls to external audit system."""
    audit_log.record(call.name, call.arguments)
    result = await next_handler(call, context)
    audit_log.record_result(call.name, result.is_error)
    return result

async def cost_tracker(call, context, next_handler):
    """Track tool execution costs."""
    start = time.monotonic()
    result = await next_handler(call, context)
    elapsed = time.monotonic() - start
    metrics.record(call.name, elapsed)
    return result

# 3. Customize built-in tools
def enforce_strict_mode(**kwargs):
    kwargs["command"] = f"set -euo pipefail; {kwargs['command']}"
    return kwargs

strict_bash = wrap_tool(bash, name="bash", before=enforce_strict_mode)

# 4. Create executor
executor = ToolExecutor(
    tools=[strict_bash, bash_output, kill_shell, read, write, edit],
    middleware=[audit_middleware, cost_tracker],
    config=config,
)

# 5. Customize security
from rawagents.tools.builtin.shell import (
    ShellSecurityContext, set_shell_security_context,
)

ctx = ShellSecurityContext(workspace="/my-project")
ctx.add_deny_pattern("npm publish *")    # Block npm publish
ctx.remove_deny_pattern("git push *")    # Allow git push
set_shell_security_context(ctx)

# 6. Execute tools
result = await executor.execute(tool_call, context={"db": my_db})
```

---

## 9. Migration Path

### 9.1 Backward Compatibility

All changes are **additive**. Existing code works without modification:

| Existing Pattern | After PRD 007 |
|-----------------|---------------|
| `ToolExecutor(tools=[...])` | Still works, no middleware |
| `ToolExecutor(tools=[...], on_before=fn)` | Still works, callbacks run inside middleware chain |
| `SecurityContext(denied_patterns=[...])` | Still works, full override |
| `ShellSecurityContext(deny_patterns=[...])` | Still works, full override |
| `get_process_manager()` | Still works, returns global singleton |

### 9.2 Deprecation Schedule

| Feature | Status | Deprecation | Removal |
|---------|--------|-------------|---------|
| `on_before` callback | Supported | v0.3 (warning) | v1.0 |
| `on_after` callback | Supported | v0.3 (warning) | v1.0 |
| `_DEFAULT_DENIED_PATTERNS` (private) | Supported | Immediate (use `DEFAULT_FS_DENIED_PATTERNS`) | v1.0 |
| `_DEFAULT_DENY_PATTERNS` (private) | Supported | Immediate (use `DEFAULT_SHELL_DENY_PATTERNS`) | v1.0 |

### 9.3 Migration Examples

```python
# Before: on_before/on_after
executor = ToolExecutor(
    tools=[bash],
    on_before=lambda call: print(f"Calling {call.name}"),
    on_after=lambda call, result: print(f"Done: {result.is_error}"),
)

# After: middleware (more powerful)
async def log_middleware(call, context, next_handler):
    print(f"Calling {call.name}")
    result = await next_handler(call, context)
    print(f"Done: {result.is_error}")
    return result

executor = ToolExecutor(tools=[bash], middleware=[log_middleware])
```

---

## 10. Testing Strategy

### 10.1 Test Categories

| Category | Tests | Description |
|----------|-------|-------------|
| Middleware chain | 20+ | Order, short-circuit, error handling, async |
| ToolConfig | 15+ | Defaults, overrides, frozen immutability |
| Security patterns | 10+ | add/remove, public constants, merge semantics |
| wrap_tool | 15+ | Before/after hooks, name override, schema preservation |
| register(force=True) | 5+ | Replace, original removed, schemas updated |
| Backward compat | 10+ | on_before/on_after still work, no behavior changes |
| Integration | 10+ | Full pipeline with middleware + config + custom tools |

### 10.2 Key Test Scenarios

```python
# Middleware ordering
async def test_middleware_executes_in_order():
    order = []
    async def m1(call, ctx, next):
        order.append("m1-before")
        result = await next(call, ctx)
        order.append("m1-after")
        return result
    async def m2(call, ctx, next):
        order.append("m2-before")
        result = await next(call, ctx)
        order.append("m2-after")
        return result

    executor = ToolExecutor(tools=[my_tool], middleware=[m1, m2])
    await executor.execute(call)
    assert order == ["m1-before", "m2-before", "m2-after", "m1-after"]

# Middleware short-circuit
async def test_middleware_can_short_circuit():
    async def blocker(call, ctx, next):
        return ToolResult(tool_call_id=call.id, name=call.name,
                         content="Blocked", is_error=True)

    executor = ToolExecutor(tools=[my_tool], middleware=[blocker])
    result = await executor.execute(call)
    assert result.is_error
    assert result.content == "Blocked"

# Config override
async def test_config_overrides_defaults():
    config = ToolConfig(shell=ShellToolConfig(max_output_bytes=100))
    assert config.shell.max_output_bytes == 100
    assert config.fs.max_output_bytes == 50_000  # Default preserved

# Security pattern modification
def test_add_deny_pattern():
    ctx = SecurityContext(workspace="/project")
    original_count = len(ctx.denied_patterns)
    ctx.add_denied_pattern("*.backup")
    assert len(ctx.denied_patterns) == original_count + 1
    assert "*.backup" in ctx.denied_patterns

# wrap_tool preserves schema
def test_wrap_tool_preserves_schema():
    wrapped = wrap_tool(bash, before=lambda **kw: kw)
    assert wrapped.__tool_schema__ == bash.__tool_schema__

# force register
def test_register_force_replaces():
    executor = ToolExecutor(tools=[bash])
    executor.register(my_custom_bash, force=True)
    assert "bash" in executor
    # Verify it's the custom one
    assert executor._tools["bash"] is my_custom_bash
```

---

## 11. Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **Middleware performance overhead** | Low | Medium | Benchmark; middleware chain is built once at init, not per-call |
| **Middleware error swallowing** | High | Low | Middleware errors propagate as ToolResult(is_error=True); never silently dropped |
| **Config explosion** | Medium | Medium | Keep configs flat (no nesting beyond 2 levels); frozen dataclasses prevent mutation bugs |
| **Breaking changes** | High | Low | 100% backward compatible; new features are opt-in; deprecation warnings before removal |
| **Security bypass via middleware** | High | Medium | Document that middleware can bypass security; this is intentional for advanced users |
| **Circular imports** | Medium | Low | Config module has zero dependencies on tool implementations |

---

## 12. Success Criteria

### 12.1 Functional Criteria

| Criterion | Measurement |
|-----------|-------------|
| **Middleware chain works** | 3+ middleware compose correctly (order, short-circuit, error) |
| **Config overrides apply** | Tool behavior changes when config values change |
| **Security patterns modifiable** | add/remove patterns without copying defaults |
| **wrap_tool works** | Wrapped tools have correct schema, pre/post hooks fire |
| **100% backward compatible** | All existing tests pass without modification |
| **Zero new dependencies** | stdlib only (dataclasses, typing, contextvars) |

### 12.2 Quality Criteria

| Criterion | Target |
|-----------|--------|
| Test coverage | >95% for new code |
| Type safety | mypy strict passes |
| Lint clean | ruff check passes |
| Documentation | Docstrings on all public APIs |
| Performance | <1ms overhead per middleware layer |

---

## 13. Implementation Plan

### Phase 1: Middleware Chain (Priority: P0)

**Files**: `src/rawagents/tools/middleware.py`, modified `executor.py`
**Effort**: ~200 LOC source + ~300 LOC tests

1. Define `ToolMiddleware` protocol in `middleware.py`
2. Add `middleware` parameter to `ToolExecutor.__init__()`
3. Build chain at init time (not per-call)
4. Execute chain in `execute()` method
5. Wrap legacy `on_before`/`on_after` as internal middleware (backward compat)
6. Add `use()` method for post-init middleware addition

### Phase 2: Configuration System (Priority: P0)

**Files**: `src/rawagents/tools/config.py`, modified tool files
**Effort**: ~150 LOC source + ~200 LOC tests

1. Define `ToolConfig`, `FSToolConfig`, `ShellToolConfig` dataclasses
2. Add `config` parameter to `ToolExecutor.__init__()`
3. Pass config to tools via injection context
4. Modify tools to read config values instead of module constants
5. Default values match current hardcoded values exactly

### Phase 3: Security Pattern API (Priority: P1)

**Files**: Modified `fs/_security.py`, `shell/_security.py`
**Effort**: ~100 LOC source + ~100 LOC tests

1. Rename private constants to public (keep private as aliases with deprecation)
2. Add `add_denied_pattern()`, `remove_denied_pattern()` to `SecurityContext`
3. Add `add_deny_pattern()`, `remove_deny_pattern()` to `ShellSecurityContext`
4. Add `add_allowed_pattern()`, `remove_allowed_pattern()` to `SecurityContext`

### Phase 4: Tool Composition (Priority: P1)

**Files**: `src/rawagents/tools/composition.py`, modified `executor.py`
**Effort**: ~150 LOC source + ~200 LOC tests

1. Implement `wrap_tool()` function
2. Add `force` parameter to `ToolExecutor.register()`
3. Ensure wrapped tools preserve `__tool_schema__` and all metadata

### Phase 5: Pluggable Internals (Priority: P2)

**Files**: Modified `_replacers.py`, `_process_manager.py`
**Effort**: ~50 LOC source + ~100 LOC tests

1. Add `strategies` parameter to `find_and_replace()`
2. Add `process_manager` field to `ShellSecurityContext`
3. Document extension points

---

## 14. Appendix: Evaluated Options

### Option A: Pluggy-Style Plugin System

**Description**: Use pluggy (pytest's plugin framework) for hook-based extensibility with `@hookspec` and `@hookimpl`.

**Pros**: Extremely flexible, battle-tested, supports N-to-1 dispatch, ordering control.

**Cons**: Adds dependency (pluggy), complex API surface, overkill for our use case (we need linear middleware, not N-to-1 dispatch), learning curve.

**Verdict**: **Rejected** — Too complex for our "Primitives over Frameworks" philosophy.

### Option B: Abstract Base Class Inheritance

**Description**: Built-in tools inherit from `BaseTool` class. Users subclass to override.

**Pros**: Familiar OOP pattern, IDE autocomplete, clear override points.

**Cons**: Forces class hierarchy (against "Functions, not Frameworks"), inheritance is brittle (fragile base class problem), users must understand internal implementation to subclass correctly.

**Verdict**: **Rejected** — Contradicts core design philosophy. Composition beats inheritance.

### Option C: Event Emitter Pattern

**Description**: Tools emit events (pre_execute, post_execute, on_error) that listeners subscribe to.

**Pros**: Decoupled, supports multiple listeners, familiar from Node.js.

**Cons**: Cannot modify execution flow (events are notifications), no type safety, ordering issues with multiple listeners.

**Verdict**: **Rejected** — Cannot intercept/modify execution. Same limitation as current `on_before`/`on_after`.

### Option D: Decorator Stacking

**Description**: Provide decorators that wrap existing tools: `@with_logging`, `@with_rate_limit`, etc.

**Pros**: Pythonic, composable via stacking.

**Cons**: Order-dependent (decorator application order matters), no runtime composition, each decorator must preserve `__tool_*` metadata.

**Verdict**: **Partially adopted** — `wrap_tool()` function provides this capability without the metadata preservation footgun.

### Option E: Configuration File (YAML/JSON)

**Description**: Tool configuration via `rawagents.yaml` or `rawagents.json`.

**Pros**: Non-code configuration, CI/CD friendly, environment-specific.

**Cons**: Not type-safe, requires parser, file discovery logic, against "explicit code" philosophy, schema validation overhead.

**Verdict**: **Rejected** — Python code is the configuration language. NG3 explicitly excludes this.

### Option F: Django-Style Middleware Chain (Selected)

**Description**: Middleware functions that wrap tool execution in an onion-layer pattern, with each middleware calling `next_handler` to proceed.

**Pros**: Battle-tested (20+ years in Django), simple mental model, composable, can modify inputs/outputs/short-circuit, type-safe with Protocol.

**Cons**: Slightly more complex than simple callbacks (must call `next_handler`).

**Verdict**: **Selected** — Best balance of power and simplicity. Combined with per-tool `wrap_tool()` and `ToolConfig` dataclasses for comprehensive extensibility.
