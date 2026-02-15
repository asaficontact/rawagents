# Product Requirements Document (PRD)
# RawAgents Built-in Tool Enhancements

**Version:** 1.0
**Date:** February 2026
**Status:** Draft
**Author:** Tawab Safi

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Background & Motivation](#2-background--motivation)
3. [Goals & Non-Goals](#3-goals--non-goals)
4. [Enhancement Inventory](#4-enhancement-inventory)
5. [Enhancement Specifications](#5-enhancement-specifications)
6. [Cross-Cutting Concerns](#6-cross-cutting-concerns)
7. [Implementation Approach](#7-implementation-approach)
8. [Reference Implementations](#8-reference-implementations)
9. [Testing Strategy](#9-testing-strategy)
10. [Project Structure](#10-project-structure)
11. [Development Process](#11-development-process)

---

## 1. Executive Summary

### 1.1 What We're Building

This PRD addresses **8 enhancement areas** identified by benchmarking RawAgents' built-in tools against state-of-the-art coding agents (Claude Code, OpenCode, SWE-agent/SWE-ReX, Aider). These are improvements to existing modules (`fs`, `shell`, `web`) and the `ToolExecutor`, not new tool modules.

Following RawAgents' **"Primitives over Frameworks"** philosophy, each enhancement is:
- An incremental improvement to an existing module
- Independently implementable and testable
- Backward-compatible with existing tool signatures
- Opt-in where it introduces new behavior

### 1.2 Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **LSP Integration** | Protocol-based `DiagnosticsProvider` (opt-in) | Follows `SearchProvider` pattern; doesn't couple tools to any LSP library |
| **Batch Execution** | `execute_batch()` on existing `ToolExecutor` | Minimal API surface; `asyncio.gather()` for parallelism |
| **Shell Security** | Keep regex heuristics, add optional tree-sitter layer | Current 100+ deny patterns are effective; tree-sitter adds defense-in-depth |
| **Fuzzy Edit Matching** | Add `FuzzyReplacer` as 6th strategy in existing chain | Slots into existing `Replacer` ABC; `difflib.SequenceMatcher` (stdlib only) |
| **Output Truncation** | Shared `TruncationResult` + context-aware recovery hints | Eliminates duplicated truncation logic across `bash.py` and `read.py` |
| **File Safety** | Upgrade `_read_files: set` to `dict[str, float]` with mtime | Minimal change; catches external modifications between read and edit |
| **Named Sessions** | Optional `session` parameter on `bash` tool | Backward-compatible; ProcessManager gains session-keyed lookup |
| **Code Search** | `CodeSearchProvider` Protocol extending `SearchProvider` pattern | Users bring their own backend (GitHub API, Sourcegraph, Exa) |

### 1.3 Enhancements Summary

| # | Enhancement | Module | Priority | Complexity |
|---|-------------|--------|----------|------------|
| E1 | Diagnostics Feedback Loop (LSP) | `fs`, `executor` | P0 - Critical | High |
| E2 | Batch/Parallel Tool Execution | `executor` | P0 - Critical | Medium |
| E3 | Fuzzy Edit Matching | `fs` | P1 - High | Low |
| E4 | File Modification Timestamp Safety | `fs` | P1 - High | Low |
| E5 | Smart Output Truncation | `fs`, `shell` | P1 - High | Medium |
| E6 | Named Shell Sessions | `shell` | P2 - Medium | Medium |
| E7 | Tree-Sitter Shell Security | `shell` | P2 - Medium | High |
| E8 | Code Search Provider | `web` | P3 - Low | Low |

---

## 2. Background & Motivation

### 2.1 Problem Statement

RawAgents' built-in tools (PRDs 005, 006, 008) provide solid foundational capabilities for building coding agents. However, benchmarking against leading coding agent implementations reveals 8 areas where enhancements would significantly improve agent effectiveness, safety, and developer experience.

These gaps were identified by analyzing:
- **OpenCode** (open-source coding agent by Anomaly): LSP integration, batch execution, tree-sitter parsing, smart truncation
- **Claude Code** (Anthropic): Diagnostics feedback loop, output recovery hints, parallel tool calls
- **SWE-ReX** (SWE-agent runtime): Named shell sessions, persistent process management
- **Aider**: Fuzzy edit matching with `difflib.SequenceMatcher`

### 2.2 Why These Enhancements Matter

| Enhancement | Without It | With It |
|-------------|-----------|---------|
| **Diagnostics Feedback** | Agent makes edit, doesn't know if it introduced errors | Agent gets immediate syntax/type errors after edit, can self-correct |
| **Batch Execution** | 5 independent reads = 5 sequential round-trips | 5 independent reads = 1 parallel round-trip |
| **Fuzzy Matching** | LLM-generated `old_string` with minor whitespace differences fails | Gracefully matches despite small discrepancies |
| **mtime Safety** | Agent reads file, user edits externally, agent overwrites user's changes | Agent detects external changes and warns before overwriting |
| **Smart Truncation** | "Output truncated" with no guidance | "Output truncated. Use `grep` to search, or `read` with `offset=500`" |
| **Named Sessions** | Each command is isolated; no shared environment state | Agent can maintain persistent shells (e.g., `venv activate` persists) |
| **Tree-Sitter Security** | `rm -rf /` caught by regex, but `eval "rm" "-rf" "/"` may slip through | AST-based parsing catches obfuscated commands |
| **Code Search** | Agent limited to local `grep` for code discovery | Agent can search across GitHub/Sourcegraph for patterns and examples |

### 2.3 Design Principles

All enhancements follow RawAgents' core principles:

1. **Primitives over Frameworks** - Each enhancement is a composable primitive, not a monolithic feature
2. **Zero-Config Defaults** - Enhancements work out of the box with sensible defaults
3. **Opt-In Complexity** - Advanced features (LSP, tree-sitter, code search) require explicit opt-in
4. **Protocol-Based Extensibility** - New capabilities use `Protocol` classes users can implement
5. **Backward Compatibility** - No existing tool signatures change; new parameters are optional

---

## 3. Goals & Non-Goals

### 3.1 Goals

**G1: Agent Self-Correction**
- Enable agents to detect and fix their own errors through diagnostics feedback
- Close the "edit → verify → fix" loop that makes coding agents effective

**G2: Execution Efficiency**
- Support parallel execution of independent tool calls
- Reduce round-trips between LLM and tools

**G3: Edit Reliability**
- Improve success rate of LLM-generated edits through fuzzy matching
- Prevent data loss from external file modifications

**G4: Output Quality**
- Provide actionable guidance when output is truncated
- Help agents navigate large outputs efficiently

**G5: Shell Persistence**
- Support persistent shell sessions for multi-step workflows
- Maintain environment state across commands

**G6: Security Depth**
- Add AST-based command validation as defense-in-depth layer
- Catch obfuscated commands that bypass regex patterns

### 3.2 Non-Goals

- **Full LSP server**: We provide a `DiagnosticsProvider` protocol, not an LSP client library
- **DAG-based task orchestration**: Batch execution is flat `asyncio.gather()`, not a dependency graph
- **Built-in code search backend**: We provide the `CodeSearchProvider` protocol; users bring their provider
- **Replacing existing security**: Tree-sitter augments (not replaces) the current regex/fnmatch system
- **Cross-session persistence**: Named sessions are per-process; no disk persistence
- **Breaking changes**: All existing tool signatures remain unchanged

---

## 4. Enhancement Inventory

### 4.1 Module Impact Map

```
src/rawagents/tools/
  executor.py                  # E1 (on_after_file_change), E2 (execute_batch)
  builtin/
    fs/
      _security.py             # E4 (mtime tracking)
      _replacers.py            # E3 (FuzzyReplacer)
      _utils.py                # E5 (TruncationResult)
      _diagnostics.py          # E1 (DiagnosticsProvider) [NEW]
      edit.py                  # E1 (post-edit diagnostics), E3 (fuzzy strategy)
      write.py                 # E1 (post-write diagnostics)
      read.py                  # E5 (shared truncation)
    shell/
      _security.py             # E7 (tree-sitter layer)
      _process_manager.py      # E6 (session registry)
      _truncation.py           # E5 (shared truncation) [NEW]
      bash.py                  # E5 (shared truncation), E6 (session param)
    web/
      _types.py                # E8 (CodeSearchProvider)
      code_search.py           # E8 (code_search tool) [NEW]
```

### 4.2 Dependency Graph

```
E4 (mtime) ──────────────────── standalone (no dependencies)
E3 (fuzzy) ──────────────────── standalone (no dependencies)
E5 (truncation) ─────────────── standalone (no dependencies)
E8 (code search) ────────────── standalone (no dependencies)
E6 (named sessions) ─────────── standalone (no dependencies)
E2 (batch execution) ────────── standalone (no dependencies)
E1 (diagnostics) ────────────── depends on E4 (mtime tracking for change detection)
E7 (tree-sitter) ────────────── standalone (optional dependency: tree-sitter-bash)
```

---

## 5. Enhancement Specifications

### E1: Diagnostics Feedback Loop

#### 5.1.1 Problem

When an agent edits a file, it has no way to know if the edit introduced syntax errors, type errors, or other issues. The agent must explicitly run a linter or type checker to discover problems — assuming it even thinks to do so.

OpenCode solves this with tight LSP integration: after every edit, it calls `LSP.touchFile()` and `LSP.diagnostics()` to get immediate feedback. Claude Code similarly provides post-edit diagnostics.

#### 5.1.2 Design

**Protocol Definition** (`fs/_diagnostics.py`):

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class Diagnostic:
    """A single diagnostic message (error, warning, etc.)."""
    file: str
    line: int
    column: int
    severity: str  # "error" | "warning" | "info" | "hint"
    message: str
    source: str  # e.g., "pyright", "ruff", "mypy"


@runtime_checkable
class DiagnosticsProvider(Protocol):
    """Protocol for pluggable diagnostics backends.

    Users implement this Protocol to integrate their preferred
    diagnostics source (LSP client, linter subprocess, etc.).

    Example:
        class RuffDiagnosticsProvider:
            async def get_diagnostics(self, file_path: str) -> list[Diagnostic]:
                result = await asyncio.create_subprocess_exec(
                    "ruff", "check", "--output-format=json", file_path,
                    stdout=asyncio.subprocess.PIPE,
                )
                stdout, _ = await result.communicate()
                return [Diagnostic(...) for item in json.loads(stdout)]

            async def notify_change(self, file_path: str) -> None:
                pass  # Ruff doesn't need notification
    """

    async def get_diagnostics(self, file_path: str) -> list[Diagnostic]:
        """Get diagnostics for a file.

        Args:
            file_path: Absolute path to the file.

        Returns:
            List of diagnostics (errors, warnings, etc.).
        """
        ...

    async def notify_change(self, file_path: str) -> None:
        """Notify the provider that a file has changed.

        Called BEFORE get_diagnostics() to give the backend
        time to re-analyze the file (e.g., LSP textDocument/didChange).

        Args:
            file_path: Absolute path to the changed file.
        """
        ...
```

**Integration in `SecurityContext`**:

```python
# In _security.py, add to SecurityContext:
diagnostics_provider: DiagnosticsProvider | None = None
"""Optional diagnostics provider for post-edit feedback."""
```

**Integration in `edit.py` and `write.py`**:

After a successful edit/write, if a `DiagnosticsProvider` is configured:

```python
# At end of edit() / write(), after successful file operation:
if ctx.diagnostics_provider is not None:
    try:
        await ctx.diagnostics_provider.notify_change(str(resolved_path))
        diagnostics = await ctx.diagnostics_provider.get_diagnostics(str(resolved_path))
        if diagnostics:
            errors = [d for d in diagnostics if d.severity == "error"]
            warnings = [d for d in diagnostics if d.severity == "warning"]
            diag_lines = []
            for d in errors[:5]:  # Cap at 5 errors
                diag_lines.append(f"  {d.line}:{d.column} {d.severity}: {d.message} [{d.source}]")
            for d in warnings[:3]:  # Cap at 3 warnings
                diag_lines.append(f"  {d.line}:{d.column} {d.severity}: {d.message} [{d.source}]")
            if diag_lines:
                result += "\n\nDiagnostics:\n" + "\n".join(diag_lines)
                if len(errors) > 5:
                    result += f"\n  ... and {len(errors) - 5} more errors"
    except Exception:
        pass  # Never let diagnostics failure break the edit
```

#### 5.1.3 Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Protocol vs. concrete class | `Protocol` | Users choose their LSP client / linter; we don't dictate |
| Diagnostics appended to result | Yes, appended as suffix | Agent sees diagnostics in same tool result; no extra round-trip |
| Failure behavior | Silent (try/except pass) | Diagnostics are advisory; must never break file operations |
| Max diagnostics shown | 5 errors + 3 warnings | Prevent flooding the LLM context with hundreds of diagnostics |

#### 5.1.4 Example User Implementation

```python
# LSP-based provider (using pygls or pylsp)
class LSPDiagnosticsProvider:
    def __init__(self, lsp_client):
        self._client = lsp_client

    async def notify_change(self, file_path: str) -> None:
        self._client.did_change(file_path)

    async def get_diagnostics(self, file_path: str) -> list[Diagnostic]:
        raw = await self._client.get_diagnostics(file_path)
        return [Diagnostic(
            file=file_path,
            line=d.range.start.line + 1,
            column=d.range.start.character + 1,
            severity=_lsp_severity_to_str(d.severity),
            message=d.message,
            source=d.source or "lsp",
        ) for d in raw]

# Subprocess-based provider (simpler, no LSP dependency)
class RuffDiagnosticsProvider:
    async def notify_change(self, file_path: str) -> None:
        pass  # Ruff reads from disk, no notification needed

    async def get_diagnostics(self, file_path: str) -> list[Diagnostic]:
        proc = await asyncio.create_subprocess_exec(
            "ruff", "check", "--output-format=json", "--select=E,F", file_path,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if not stdout:
            return []
        items = json.loads(stdout)
        return [Diagnostic(
            file=file_path, line=item["location"]["row"],
            column=item["location"]["column"],
            severity="error" if item["code"].startswith("F") else "warning",
            message=item["message"], source="ruff",
        ) for item in items]
```

#### 5.1.5 Files Changed

| File | Change |
|------|--------|
| `fs/_diagnostics.py` | **NEW**: `Diagnostic`, `DiagnosticsProvider` protocol |
| `fs/_security.py` | Add `diagnostics_provider: DiagnosticsProvider \| None = None` field |
| `fs/edit.py` | Append diagnostics to result after successful edit |
| `fs/write.py` | Append diagnostics to result after successful write |
| `fs/__init__.py` | Re-export `Diagnostic`, `DiagnosticsProvider` |

---

### E2: Batch/Parallel Tool Execution

#### 5.2.1 Problem

The current `ToolExecutor.execute()` accepts a single `ToolCall` and returns a single `ToolResult`. When an LLM wants to execute 5 independent file reads, the executor processes them sequentially — 5 round-trips instead of 1.

OpenCode's `batch` tool allows up to 25 parallel tool invocations in a single call. Claude Code achieves the same through multiple `tool_use` content blocks in a single message.

#### 5.2.2 Design

**New method on `ToolExecutor`**:

```python
async def execute_batch(
    self,
    tool_calls: list[ToolCall],
    context: dict[str, Any] | None = None,
    *,
    max_concurrency: int = 25,
) -> list[ToolResult]:
    """Execute multiple tool calls in parallel.

    Independent calls run concurrently via asyncio.gather().
    Results are returned in the same order as input tool_calls.

    Args:
        tool_calls: List of tool calls to execute.
        context: Shared injection context for all calls.
        max_concurrency: Maximum concurrent executions (default 25).

    Returns:
        List of ToolResults in same order as input.
    """
    if not tool_calls:
        return []

    # Cap concurrency
    semaphore = asyncio.Semaphore(max_concurrency)

    async def _execute_with_limit(tc: ToolCall) -> ToolResult:
        async with semaphore:
            return await self.execute(tc, context)

    results = await asyncio.gather(
        *[_execute_with_limit(tc) for tc in tool_calls],
        return_exceptions=False,  # execute() never raises
    )
    return list(results)
```

#### 5.2.3 Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Execution model | Flat `asyncio.gather()` with semaphore | Simple, covers 95% of cases; no DAG complexity |
| Max concurrency | 25 (matching OpenCode) | Prevents resource exhaustion while allowing good parallelism |
| Recursive batch | Not blocked (unlike OpenCode) | Python's asyncio handles nested parallelism naturally |
| Error handling | Per-call isolation (same as `execute()`) | One failure doesn't cancel others |
| Result ordering | Same order as input | Predictable for the LLM to correlate results |

#### 5.2.4 Batch Tool Wrapper (Optional)

For agents that want to expose batch execution as a tool itself (OpenCode-style):

```python
@tool
async def batch(
    invocations: Annotated[list[dict[str, Any]], "List of {tool_name, arguments} objects"],
    executor: Annotated[ToolExecutor, Inject],
) -> str:
    """Execute multiple tool calls in parallel.

    Each invocation is {tool_name: str, arguments: dict}.
    Returns results as a JSON array in same order.
    Max 25 invocations per batch.
    """
    if len(invocations) > 25:
        return "Error: Maximum 25 invocations per batch"

    tool_calls = [
        ToolCall(
            id=f"batch_{i}",
            name=inv["tool_name"],
            arguments=inv.get("arguments", {}),
        )
        for i, inv in enumerate(invocations)
    ]
    results = await executor.execute_batch(tool_calls)
    return json.dumps([{"content": r.content, "is_error": r.is_error} for r in results])
```

#### 5.2.5 Files Changed

| File | Change |
|------|--------|
| `executor.py` | Add `execute_batch()` method |
| `builtin/batch.py` | **NEW** (optional): `batch` tool wrapper for exposing as tool |

---

### E3: Fuzzy Edit Matching

#### 5.3.1 Problem

The current 5 replacement strategies handle whitespace variations well, but none handle content differences — when the LLM generates an `old_string` that is "close but not exact" to what's in the file. For example, the LLM might misremember a variable name or include a slightly different comment.

Aider solves this with `difflib.SequenceMatcher`, finding the most similar chunk in the file and applying the replacement if similarity exceeds a threshold (typically 0.6).

#### 5.3.2 Design

**New strategy: `FuzzyReplacer`** (6th in the chain):

```python
class FuzzyReplacer(Replacer):
    """Fuzzy matching using difflib.SequenceMatcher.

    Finds the most similar contiguous block in the file content
    and replaces it if similarity exceeds the threshold.

    This is the LAST resort — only used after all exact/whitespace
    strategies fail. A threshold of 0.7 prevents false positives
    while catching common LLM transcription errors.
    """

    SIMILARITY_THRESHOLD = 0.7

    @property
    def name(self) -> str:
        return "fuzzy"

    def find_matches(self, content: str, old_string: str) -> list[Match]:
        """Find the most similar block in content.

        Slides a window of len(old_string) +/- 20% over the content,
        computing similarity at each position. Returns the best match
        above the threshold.
        """
        import difflib

        old_lines = old_string.splitlines(keepends=True)
        content_lines = content.splitlines(keepends=True)
        window_size = len(old_lines)

        if window_size == 0 or len(content_lines) == 0:
            return []

        best_ratio = 0.0
        best_start = -1
        best_end = -1

        # Allow window size variation of +/- 20%
        min_window = max(1, int(window_size * 0.8))
        max_window = min(len(content_lines), int(window_size * 1.2))

        for ws in range(min_window, max_window + 1):
            for i in range(len(content_lines) - ws + 1):
                candidate = content_lines[i : i + ws]
                ratio = difflib.SequenceMatcher(
                    None, old_lines, candidate
                ).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    # Convert line indices to character positions
                    best_start = sum(len(l) for l in content_lines[:i])
                    best_end = best_start + sum(len(l) for l in candidate)

        if best_ratio >= self.SIMILARITY_THRESHOLD:
            return [Match(
                start=best_start,
                end=best_end,
                matched_text=content[best_start:best_end],
            )]
        return []
```

**Integration**: Add to the strategy chain in `_replacers.py`:

```python
# Current (lines 400-406):
_DEFAULT_STRATEGIES = [
    SimpleReplacer(),
    LineTrimmedReplacer(),
    BlockAnchorReplacer(),
    WhitespaceNormalizedReplacer(),
    IndentationFlexibleReplacer(),
]

# New:
_DEFAULT_STRATEGIES = [
    SimpleReplacer(),
    LineTrimmedReplacer(),
    BlockAnchorReplacer(),
    WhitespaceNormalizedReplacer(),
    IndentationFlexibleReplacer(),
    FuzzyReplacer(),  # Last resort
]
```

#### 5.3.3 Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Library | `difflib.SequenceMatcher` (stdlib) | Zero dependencies; Aider proves it works well |
| Threshold | 0.7 (stricter than Aider's 0.6) | Prevent false positive replacements on wrong code blocks |
| Position in chain | Last (6th) | Only triggers when all exact/whitespace strategies fail |
| Window variation | +/- 20% | Handles LLM adding/removing a line in the search block |
| Matching unit | Lines (not characters) | Matches how LLMs think about code; more meaningful similarity |

#### 5.3.4 When Fuzzy Match Triggers

The fuzzy replacer appends a notice to the result:

```python
# In find_and_replace(), when fuzzy strategy succeeds:
if result.strategy == "fuzzy":
    result.content += ""  # content already updated
    # The edit tool will note this in its output:
    # "Applied using fuzzy matching (similarity: 0.85). Verify the result."
```

#### 5.3.5 Files Changed

| File | Change |
|------|--------|
| `fs/_replacers.py` | Add `FuzzyReplacer` class; add to `_DEFAULT_STRATEGIES` |
| `fs/edit.py` | Add notice when fuzzy strategy is used |

---

### E4: File Modification Timestamp Safety

#### 5.4.1 Problem

The current `SecurityContext._read_files` is a `set[str]` — it tracks *whether* a file was read, but not *when*. If a user edits a file externally between the agent's read and edit, the agent's edit silently overwrites the user's changes.

OpenCode tracks `mtime` in a `filePath -> timestamp` map and rejects edits when the file has been modified since the last read. Their issue tracker (GitHub #5840) shows this is a known pain point with ongoing improvements.

#### 5.4.2 Design

**Change `_read_files` type**:

```python
# Current (line 251 of _security.py):
_read_files: set[str] = field(default_factory=set, init=False, repr=False)

# New:
_read_files: dict[str, float] = field(default_factory=dict, init=False, repr=False)
"""Maps resolved path -> st_mtime at time of read."""
```

**Update `mark_file_read()`**:

```python
# Current (lines 431-439):
def mark_file_read(self, path: str | Path) -> None:
    self._read_files.add(str(Path(path).resolve()))

# New:
def mark_file_read(self, path: str | Path) -> None:
    resolved = str(Path(path).resolve())
    try:
        mtime = Path(path).resolve().stat().st_mtime
    except OSError:
        mtime = 0.0
    self._read_files[resolved] = mtime
```

**Update `check_read_before_edit()`**:

```python
# Current (lines 441-452):
def check_read_before_edit(self, path: str | Path) -> bool:
    resolved = str(Path(path).resolve())
    return resolved in self._read_files or not Path(path).exists()

# New:
def check_read_before_edit(self, path: str | Path) -> bool | str:
    """Check if file was read and hasn't changed since.

    Returns:
        True: File was read and is unchanged (safe to edit).
        False: File was never read in this session.
        str: File was read but modified externally (warning message).
    """
    resolved = str(Path(path).resolve())
    p = Path(path).resolve()

    # New file — allow edit
    if not p.exists():
        return True

    # Not read in this session
    if resolved not in self._read_files:
        return False

    # Check if modified since read
    try:
        current_mtime = p.stat().st_mtime
    except OSError:
        return True  # Can't stat, allow edit

    stored_mtime = self._read_files[resolved]
    if stored_mtime > 0 and current_mtime != stored_mtime:
        return (
            f"File has been modified externally since last read. "
            f"Read the file again to see current contents before editing."
        )

    return True
```

**Update `require_read_before_edit()` in `_utils.py`**:

```python
# Current (lines 252-274):
def require_read_before_edit(ctx, resolved_path, display_path) -> str | None:
    if not ctx.check_read_before_edit(resolved_path):
        return f"Error: File '{display_path}' was not read ..."
    return None

# New:
def require_read_before_edit(ctx, resolved_path, display_path) -> str | None:
    check = ctx.check_read_before_edit(resolved_path)
    if check is False:
        return (
            f"Error: File '{display_path}' was not read in this session. "
            f"Please read the file first before editing it."
        )
    if isinstance(check, str):
        return f"Error: {check}"
    return None
```

#### 5.4.3 Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Tracking granularity | `st_mtime` (float seconds) | Sufficient for detecting external edits; cross-platform |
| Not `st_mtime_ns` | Correct, use `st_mtime` | Nanosecond precision causes false positives on some filesystems |
| Not content hashing | Correct | Hashing large files on every read is expensive; mtime is fast |
| External modification behavior | Error (must re-read) | Prevent silent data loss; agent re-reads to see current state |
| Backward compatibility | `check_read_before_edit()` return type changes | `bool | str` is backward-compatible: `if not check:` still works for `False` and truthy strings |

#### 5.4.4 Edge Cases

| Scenario | Behavior |
|----------|----------|
| File read, not modified, edit | Allowed (mtime matches) |
| File read, user edits externally, agent edits | Rejected with "modified externally" error |
| File read, agent edits, agent edits again | Allowed (agent should update mtime after its own edits) |
| File created (not read), edit | Allowed (new file exemption) |
| File deleted between read and edit | Handled by existing `check_exists` logic |
| Git checkout changes mtime | Rejected (correct — file content changed) |

**Post-edit mtime update**: After a successful edit in `edit.py`, update the stored mtime:

```python
# After successful write in edit.py:
ctx.mark_file_read(resolved_path)  # Refresh mtime to current
```

#### 5.4.5 Files Changed

| File | Change |
|------|--------|
| `fs/_security.py` | Change `_read_files` type; update `mark_file_read()` and `check_read_before_edit()` |
| `fs/_utils.py` | Update `require_read_before_edit()` to handle string return |
| `fs/edit.py` | Call `mark_file_read()` after successful edit to refresh mtime |
| `fs/write.py` | Call `mark_file_read()` after successful write to refresh mtime |

---

### E5: Smart Output Truncation

#### 5.5.1 Problem

Output truncation is currently duplicated across `bash.py` and `read.py` with different constants, different truncation strategies, and different message formats. Neither provides actionable recovery hints to help the agent navigate the truncated output.

OpenCode's truncation system provides context-aware hints: if a `task` tool is available, it suggests delegating to a sub-agent; otherwise it suggests `grep` for searching.

#### 5.5.2 Design

**Shared `TruncationResult` dataclass**:

```python
# In a shared location (fs/_utils.py or new _truncation.py)

@dataclass
class TruncationResult:
    """Result of truncating output."""
    content: str
    was_truncated: bool
    original_lines: int
    original_bytes: int
    kept_lines: int
    kept_bytes: int
    saved_to: str | None = None  # Path to full output file

    def format_message(
        self,
        *,
        tool_name: str,
        hints: list[str] | None = None,
    ) -> str:
        """Format the truncation message with recovery hints.

        Args:
            tool_name: The tool that produced the output ("bash", "read", etc.)
            hints: Optional recovery hints to append.
        """
        if not self.was_truncated:
            return self.content

        parts = [self.content]
        parts.append(
            f"\n\n... (output truncated: showing {self.kept_lines} of "
            f"{self.original_lines} lines, "
            f"{self.kept_bytes // 1024}KB of {self.original_bytes // 1024}KB)"
        )

        if self.saved_to:
            parts.append(f"\nFull output saved to: {self.saved_to}")

        if hints:
            parts.append("\nTo see more:")
            for hint in hints:
                parts.append(f"  - {hint}")

        return "".join(parts)


def truncate_output(
    output: str,
    *,
    max_lines: int = 2000,
    max_bytes: int = 50 * 1024,
    save_full: bool = False,
    prefix: str = "rawagents",
) -> TruncationResult:
    """Truncate output with consistent behavior.

    Args:
        output: The raw output string.
        max_lines: Maximum lines to keep.
        max_bytes: Maximum bytes to keep.
        save_full: Whether to save full output to a temp file.
        prefix: Prefix for temp file name.

    Returns:
        TruncationResult with truncated content and metadata.
    """
    original_lines = output.count("\n") + 1
    original_bytes = len(output.encode("utf-8"))

    truncated = False
    lines = output.split("\n")

    if len(lines) > max_lines:
        output = "\n".join(lines[:max_lines])
        truncated = True

    if len(output.encode("utf-8")) > max_bytes:
        output = output[:max_bytes].rsplit("\n", 1)[0]
        truncated = True

    saved_to = None
    if truncated and save_full:
        import tempfile
        with tempfile.NamedTemporaryFile(
            mode="w", prefix=f"{prefix}_", suffix=".txt", delete=False,
        ) as f:
            f.write(output)  # Note: we'd need the original full output
            saved_to = f.name

    return TruncationResult(
        content=output,
        was_truncated=truncated,
        original_lines=original_lines,
        original_bytes=original_bytes,
        kept_lines=min(len(lines), max_lines),
        kept_bytes=min(original_bytes, max_bytes),
        saved_to=saved_to,
    )
```

**Context-Aware Hints**:

```python
# In bash.py:
def _bash_truncation_hints(command: str) -> list[str]:
    """Generate recovery hints for truncated bash output."""
    hints = []
    hints.append("Use `grep` tool to search the output for specific patterns")
    hints.append(f"Use `bash_output` to read the saved file with offset/limit")
    if "test" in command or "pytest" in command:
        hints.append("Re-run with `--tb=short` or `--no-header` to reduce output")
    if "find" in command or "ls" in command:
        hints.append("Add more specific filters to narrow results")
    return hints

# In read.py:
def _read_truncation_hints(file_path: str, end_line: int) -> list[str]:
    """Generate recovery hints for truncated file read."""
    return [
        f"Use `read` with `offset={end_line}` to continue reading",
        "Use `grep` to search for specific content in the file",
    ]
```

#### 5.5.3 Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Shared vs. inline | Shared `truncate_output()` function | Eliminates duplication; consistent behavior |
| Constants | Keep at 2000 lines / 50KB | Existing values are well-tested |
| Hints | Tool-specific hint generators | Different tools need different guidance |
| Temp file cleanup | Not automated (user responsibility) | Same as current behavior; avoids cleanup complexity |
| Format | Appended to content string | Agent sees it in the tool result; no separate channel |

#### 5.5.4 Files Changed

| File | Change |
|------|--------|
| `fs/_utils.py` | Add `TruncationResult`, `truncate_output()` |
| `shell/bash.py` | Use shared `truncate_output()`; add `_bash_truncation_hints()` |
| `fs/read.py` | Use shared `truncate_output()`; add `_read_truncation_hints()` |

---

### E6: Named Shell Sessions

#### 5.6.1 Problem

Each `bash` tool invocation runs a fresh subprocess. There's no way to maintain a persistent shell session where environment variables, virtual environments, and working directory changes persist across commands.

SWE-ReX provides named shell sessions with persistent state. OpenCode uses a `workdir` parameter to avoid `cd` tracking issues.

#### 5.6.2 Design

**New parameter on `bash` tool**:

```python
@tool
async def bash(
    command: Annotated[str, "The bash command to execute"],
    timeout: Annotated[int | None, "Timeout in seconds (default: 120)"] = None,
    run_in_background: Annotated[bool, "Run as background process"] = False,
    session: Annotated[str | None, "Named session ID for persistent shell"] = None,
    ctx: Annotated[ShellSecurityContext, Inject] = ...,
) -> str:
    ...
```

**Session Registry in `ProcessManager`**:

```python
@dataclass
class ShellSession:
    """A persistent interactive shell session."""
    session_id: str
    process: asyncio.subprocess.Process
    stdin: asyncio.StreamWriter
    stdout: asyncio.StreamReader
    stderr: asyncio.StreamReader
    working_directory: str
    created_at: datetime
    last_command_at: datetime
    command_count: int = 0

class ProcessManager:
    # Existing: _processes: dict[str, ProcessInfo]
    # New:
    _sessions: dict[str, ShellSession] = {}

    async def get_or_create_session(self, session_id: str, cwd: str) -> ShellSession:
        """Get existing session or create a new one."""
        if session_id in self._sessions:
            session = self._sessions[session_id]
            if session.process.returncode is None:  # Still alive
                return session
            # Dead session — recreate
            del self._sessions[session_id]

        # Create new interactive shell
        process = await asyncio.create_subprocess_exec(
            "bash", "--norc", "--noprofile",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        session = ShellSession(
            session_id=session_id,
            process=process,
            stdin=process.stdin,
            stdout=process.stdout,
            stderr=process.stderr,
            working_directory=cwd,
            created_at=datetime.now(UTC),
            last_command_at=datetime.now(UTC),
        )
        self._sessions[session_id] = session
        return session

    async def execute_in_session(
        self, session_id: str, command: str, timeout: int = 120
    ) -> tuple[str, int]:
        """Execute a command in a named session.

        Uses a sentinel marker to detect command completion:
        Appends `; echo "___SENTINEL_<uuid>___$?"` to the command,
        then reads stdout until the sentinel appears.

        Returns:
            Tuple of (output, exit_code).
        """
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError(f"Session '{session_id}' not found")

        sentinel = f"___SENTINEL_{uuid.uuid4().hex[:8]}___"
        full_command = f"{command}; echo \"{sentinel}$?\"\n"
        session.stdin.write(full_command.encode())
        await session.stdin.drain()

        # Read until sentinel
        output_lines = []
        try:
            async with asyncio.timeout(timeout):
                while True:
                    line = await session.stdout.readline()
                    decoded = line.decode("utf-8", errors="replace").rstrip("\n")
                    if decoded.startswith(sentinel):
                        exit_code = int(decoded[len(sentinel):])
                        break
                    output_lines.append(decoded)
        except asyncio.TimeoutError:
            return "\n".join(output_lines) + "\n\nError: Command timed out", -1

        session.last_command_at = datetime.now(UTC)
        session.command_count += 1
        return "\n".join(output_lines), exit_code

    async def close_session(self, session_id: str) -> None:
        """Close a named session."""
        session = self._sessions.pop(session_id, None)
        if session and session.process.returncode is None:
            session.process.terminate()
            try:
                await asyncio.wait_for(session.process.wait(), timeout=5)
            except asyncio.TimeoutError:
                session.process.kill()

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all active sessions."""
        return [
            {
                "session_id": s.session_id,
                "working_directory": s.working_directory,
                "command_count": s.command_count,
                "created_at": s.created_at.isoformat(),
                "last_command_at": s.last_command_at.isoformat(),
                "alive": s.process.returncode is None,
            }
            for s in self._sessions.values()
        ]
```

#### 5.6.3 Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Session identification | String ID (user-chosen) | Simple, memorable (e.g., "build", "test", "venv") |
| Sentinel detection | UUID-based sentinel in output | Proven pattern (SWE-ReX uses this exact approach) |
| Shell initialization | `bash --norc --noprofile` | Predictable environment; no user shell customizations |
| Session lifetime | Per-process (not persisted to disk) | Simple; sessions are cheap to recreate |
| Backward compatibility | `session=None` means current behavior | Existing code is unaffected |

#### 5.6.4 Usage Example

```python
# First command: activate virtual environment
result1 = await bash(command="source .venv/bin/activate && which python", session="dev")
# Returns: /path/to/.venv/bin/python

# Second command: virtual env is still active
result2 = await bash(command="pip install requests", session="dev")
# Returns: Successfully installed requests-2.31.0

# Third command: environment persists
result3 = await bash(command="python -c 'import requests; print(requests.__version__)'", session="dev")
# Returns: 2.31.0
```

#### 5.6.5 Files Changed

| File | Change |
|------|--------|
| `shell/_process_manager.py` | Add `ShellSession`, session methods to `ProcessManager` |
| `shell/bash.py` | Add `session` parameter; route to session execution when set |

---

### E7: Tree-Sitter Shell Security

#### 5.7.1 Problem

The current shell security uses regex/fnmatch pattern matching against 100+ deny patterns. While effective for most cases, it can be bypassed by command obfuscation techniques:

```bash
# These may bypass regex patterns:
eval "r""m" "-r""f" "/"
$(echo cm0gLXJmIC8= | base64 -d)
bash -c "$(printf '\x72\x6d\x20\x2d\x72\x66\x20\x2f')"
```

OpenCode uses tree-sitter to parse bash commands into an AST, then validates the AST nodes rather than the raw text.

#### 5.7.2 Design

**Optional tree-sitter layer** (augments, does not replace, regex):

```python
# In _security.py, new optional validation step:

class ShellSecurityContext:
    # Existing fields...
    use_tree_sitter: bool = False
    """Enable AST-based command validation (requires tree-sitter-bash)."""

    def validate_command(self, command: str) -> None:
        """Validate command against security constraints.

        Validation order:
        1. Regex/fnmatch patterns (existing, always runs)
        2. Tree-sitter AST validation (optional, if enabled)
        """
        # Step 1: Existing regex validation (unchanged)
        self._validate_with_patterns(command)

        # Step 2: Optional AST validation
        if self.use_tree_sitter:
            self._validate_with_tree_sitter(command)

    def _validate_with_tree_sitter(self, command: str) -> None:
        """Validate command using tree-sitter AST parsing.

        Extracts all command names from the AST, including:
        - Simple commands: `rm -rf /`
        - Subshells: `$(rm -rf /)`
        - Command substitution: `\`rm -rf /\``
        - Eval arguments: `eval "rm -rf /"`
        - Pipe chains: `cat file | sh`
        """
        try:
            import tree_sitter_bash as tsbash
            from tree_sitter import Language, Parser
        except ImportError:
            warnings.warn(
                "tree-sitter-bash not installed. "
                "Install with: pip install tree-sitter tree-sitter-bash",
                stacklevel=2,
            )
            return  # Gracefully degrade

        parser = Parser(Language(tsbash.language()))
        tree = parser.parse(command.encode())

        # Walk AST and extract all command names
        command_names = self._extract_commands_from_ast(tree.root_node)

        # Validate each extracted command against deny patterns
        for cmd_name in command_names:
            self._validate_with_patterns(cmd_name)

    def _extract_commands_from_ast(self, node) -> list[str]:
        """Recursively extract command names from tree-sitter AST."""
        commands = []

        if node.type == "command":
            # Get the command name (first child that's command_name)
            for child in node.children:
                if child.type == "command_name":
                    commands.append(child.text.decode())
                    break

        # Handle eval/exec with string arguments
        if node.type == "command":
            cmd_text = node.children[0].text.decode() if node.children else ""
            if cmd_text in ("eval", "exec", "bash", "sh", "zsh"):
                # Extract string arguments and recursively parse
                for child in node.children[1:]:
                    if child.type in ("string", "raw_string"):
                        inner_text = child.text.decode().strip("'\"")
                        commands.extend(
                            self._extract_commands_from_ast(
                                Parser(Language(tsbash.language()))
                                .parse(inner_text.encode())
                                .root_node
                            )
                        )

        # Recurse into all children
        for child in node.children:
            commands.extend(self._extract_commands_from_ast(child))

        return commands
```

#### 5.7.3 Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Opt-in | `use_tree_sitter=False` default | Avoids mandatory dependency; current regex is good enough for most |
| Dependency | `tree-sitter` + `tree-sitter-bash` | Python bindings are mature; used by GitHub, Neovim, etc. |
| Failure behavior | Warning + graceful degradation | If tree-sitter not installed, falls back to regex-only |
| Augment vs. replace | Augment (both layers run) | Defense in depth; regex catches obvious cases fast |
| Recursive parsing | Yes (eval/exec arguments) | Key security benefit over regex; catches obfuscation |

#### 5.7.4 Limitations

- Tree-sitter parses syntax, not semantics. `$(cat /etc/shadow)` looks syntactically fine
- Base64-encoded payloads still require heuristic detection (existing regex handles `base64 -d | sh`)
- Environment variable expansion (`$CMD`) happens at runtime, not parse time

#### 5.7.5 Files Changed

| File | Change |
|------|--------|
| `shell/_security.py` | Add `use_tree_sitter` field; add `_validate_with_tree_sitter()` and `_extract_commands_from_ast()` |
| `pyproject.toml` | Add `tree-sitter` + `tree-sitter-bash` as optional dependency: `pip install rawagents[tree-sitter]` |

---

### E8: Code Search Provider

#### 5.8.1 Problem

The current web tools provide `web_search` (via `SearchProvider` protocol) for general web searches, but there's no dedicated tool for searching code across repositories. Agents are limited to local `grep` for code discovery.

OpenCode integrates with the Exa API for code search. Sourcegraph provides powerful code search across millions of repositories.

#### 5.8.2 Design

**New protocol** (`web/_types.py`):

```python
@dataclass
class CodeSearchResult:
    """A single code search result."""
    file_path: str
    repository: str
    url: str
    snippet: str
    language: str
    line_start: int
    line_end: int
    score: float  # Relevance score (0-1)


@runtime_checkable
class CodeSearchProvider(Protocol):
    """Protocol for pluggable code search backends.

    Users implement this to add code search capabilities.
    Possible backends: GitHub Code Search API, Sourcegraph, Exa, grep.app.

    Example:
        class GitHubCodeSearchProvider:
            def __init__(self, token: str):
                self._token = token

            async def search_code(
                self, query, *, language=None, repo=None,
                path_filter=None, num_results=10,
            ) -> list[CodeSearchResult]:
                import httpx
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        "https://api.github.com/search/code",
                        params={"q": f"{query} language:{language}"},
                        headers={"Authorization": f"token {self._token}"},
                    )
                    ...

            @property
            def name(self) -> str:
                return "github"
    """

    async def search_code(
        self,
        query: str,
        *,
        language: str | None = None,
        repo: str | None = None,
        path_filter: str | None = None,
        num_results: int = 10,
    ) -> list[CodeSearchResult]:
        """Search for code across repositories.

        Args:
            query: The search query (code pattern, function name, etc.).
            language: Filter by programming language.
            repo: Filter by repository (e.g., "owner/repo").
            path_filter: Filter by file path pattern (e.g., "src/**/*.py").
            num_results: Number of results to return.

        Returns:
            List of CodeSearchResult objects.
        """
        ...

    @property
    def name(self) -> str:
        """Provider name for logging/identification."""
        ...
```

**New tool** (`web/code_search.py`):

```python
@tool
async def code_search(
    query: Annotated[str, "Code search query (function names, patterns, etc.)"],
    language: Annotated[str | None, "Filter by programming language"] = None,
    repo: Annotated[str | None, "Filter by repository (owner/repo)"] = None,
    num_results: Annotated[int, "Number of results (1-20, default 10)"] = 10,
) -> str:
    """Search for code across repositories using a pluggable provider.

    Requires a CodeSearchProvider to be configured in WebContext.
    """
    ctx = get_web_context()

    if ctx.code_search_provider is None:
        return (
            "Error: No code search provider configured. "
            "Set WebContext.code_search_provider to enable code search."
        )

    ctx.check_rate_limit("search")
    num_results = min(max(num_results, 1), 20)

    try:
        results = await ctx.code_search_provider.search_code(
            query, language=language, repo=repo, num_results=num_results,
        )
    except Exception as e:
        return f"Error: Code search failed: {e}"

    if not results:
        return "No code results found."

    # Format results
    lines = [f"Found {len(results)} code results:\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. **{r.repository}** — `{r.file_path}` (L{r.line_start}-{r.line_end})")
        lines.append(f"   Language: {r.language} | Score: {r.score:.2f}")
        lines.append(f"   URL: {r.url}")
        lines.append(f"   ```{r.language}")
        lines.append(f"   {r.snippet}")
        lines.append("   ```")
        lines.append("")

    return "\n".join(lines)
```

**Integration in `WebContext`**:

```python
# In _context.py, add field:
code_search_provider: CodeSearchProvider | None = None
"""Optional code search provider for searching code across repositories."""
```

#### 5.8.3 Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Protocol | Separate `CodeSearchProvider` (not extending `SearchProvider`) | Different return type (`CodeSearchResult` vs `SearchResult`), different parameters |
| Built-in provider | None (protocol only) | We don't want to mandate a specific API; users choose |
| Rate limiting | Shares `search` rate limit bucket | Code search is a type of search operation |
| Result format | Markdown with code blocks | LLMs parse this well; includes context for understanding |

#### 5.8.4 Files Changed

| File | Change |
|------|--------|
| `web/_types.py` | Add `CodeSearchResult`, `CodeSearchProvider` protocol |
| `web/_context.py` | Add `code_search_provider` field to `WebContext` |
| `web/code_search.py` | **NEW**: `code_search` tool |
| `web/__init__.py` | Re-export new types and tool |

---

## 6. Cross-Cutting Concerns

### 6.1 Backward Compatibility

Every enhancement is designed for backward compatibility:

| Enhancement | Compatibility Guarantee |
|-------------|------------------------|
| E1 (Diagnostics) | `diagnostics_provider=None` by default; existing behavior unchanged |
| E2 (Batch) | New method on `ToolExecutor`; existing `execute()` unchanged |
| E3 (Fuzzy) | Added as last strategy; only triggers when all 5 existing strategies fail |
| E4 (mtime) | `check_read_before_edit()` returns `True`/`False`/`str`; `if not check:` still works for `False` |
| E5 (Truncation) | Same constants, same behavior; just shared implementation |
| E6 (Sessions) | `session=None` by default; existing single-command behavior unchanged |
| E7 (Tree-sitter) | `use_tree_sitter=False` by default; regex-only remains default |
| E8 (Code Search) | New tool and protocol; no existing code changes |

### 6.2 Optional Dependencies

| Enhancement | Dependency | How to Install |
|-------------|-----------|----------------|
| E1-E6 | None (stdlib only) | Built-in |
| E7 | `tree-sitter`, `tree-sitter-bash` | `pip install rawagents[tree-sitter]` |
| E8 | None for protocol; `httpx` for providers | `httpx` already a dependency (via web tools) |

### 6.3 Error Handling

All enhancements follow the existing error pattern:

```python
# Tool functions return error strings (never raise)
return "Error: descriptive message"

# Internal helpers may raise (caught by tool function or executor)
raise SomeError("details")

# Advisory features (diagnostics, hints) silently degrade
try:
    diagnostics = await provider.get_diagnostics(file_path)
except Exception:
    pass  # Never let advisory features break core functionality
```

### 6.4 Performance Considerations

| Enhancement | Performance Impact |
|-------------|-------------------|
| E1 (Diagnostics) | Adds latency to edit/write (async, can be optimized with background tasks) |
| E2 (Batch) | Net positive — reduces total execution time through parallelism |
| E3 (Fuzzy) | Adds latency only when all 5 other strategies fail (rare case) |
| E4 (mtime) | Negligible — `stat()` is fast, replaces `set.add()` with `dict[]=` |
| E5 (Truncation) | No change — same logic, shared code |
| E6 (Sessions) | Slightly more memory per session; amortized benefit from process reuse |
| E7 (Tree-sitter) | Adds ~5ms per command validation when enabled |
| E8 (Code Search) | Network latency (external API); behind rate limiter |

---

## 7. Implementation Approach

### 7.1 Implementation Order

Enhancements are ordered by dependency, priority, and complexity:

```
Phase 1: Foundation (no dependencies)
  ├── E4: mtime tracking          [P1, Low complexity, ~2 hours]
  ├── E3: Fuzzy matching          [P1, Low complexity, ~2 hours]
  └── E5: Smart truncation        [P1, Medium complexity, ~3 hours]

Phase 2: Execution (no dependencies)
  ├── E2: Batch execution         [P0, Medium complexity, ~3 hours]
  └── E6: Named sessions          [P2, Medium complexity, ~4 hours]

Phase 3: Integration (E4 should be done first)
  ├── E1: Diagnostics feedback    [P0, High complexity, ~5 hours]
  └── E8: Code search provider    [P3, Low complexity, ~2 hours]

Phase 4: Advanced (standalone)
  └── E7: Tree-sitter security    [P2, High complexity, ~5 hours]
```

### 7.2 Phase 1: Foundation Enhancements

#### E4: mtime Tracking (Start Here)

1. Change `_read_files` from `set[str]` to `dict[str, float]` in `_security.py`
2. Update `mark_file_read()` to store `st_mtime`
3. Update `check_read_before_edit()` to compare mtimes
4. Update `require_read_before_edit()` in `_utils.py` to handle string return
5. Update `edit.py` and `write.py` to refresh mtime after successful operations
6. Update existing tests for new return type

#### E3: Fuzzy Matching

1. Add `FuzzyReplacer` class to `_replacers.py`
2. Add to `_DEFAULT_STRATEGIES` list (position 6)
3. Add notice in `edit.py` when fuzzy strategy succeeds
4. Add tests for fuzzy matching (threshold, window variation, edge cases)

#### E5: Smart Truncation

1. Add `TruncationResult` and `truncate_output()` to `fs/_utils.py`
2. Refactor `bash.py` truncation to use shared function
3. Refactor `read.py` truncation to use shared function
4. Add tool-specific hint generators
5. Verify existing tests pass with new implementation

### 7.3 Phase 2: Execution Enhancements

#### E2: Batch Execution

1. Add `execute_batch()` method to `ToolExecutor`
2. Add tests for parallel execution, error isolation, ordering
3. (Optional) Add `batch` tool wrapper in `builtin/batch.py`

#### E6: Named Sessions

1. Add `ShellSession` dataclass and session methods to `ProcessManager`
2. Add `session` parameter to `bash` tool
3. Implement sentinel-based command completion detection
4. Add session cleanup in `ProcessManager.close_all()`
5. Add tests for session persistence, cleanup, dead session recovery

### 7.4 Phase 3: Integration Enhancements

#### E1: Diagnostics Feedback

1. Create `fs/_diagnostics.py` with `Diagnostic` and `DiagnosticsProvider`
2. Add `diagnostics_provider` field to `SecurityContext`
3. Add post-edit diagnostics in `edit.py`
4. Add post-write diagnostics in `write.py`
5. Add tests with mock `DiagnosticsProvider`

#### E8: Code Search Provider

1. Add `CodeSearchResult` and `CodeSearchProvider` to `web/_types.py`
2. Add `code_search_provider` field to `WebContext`
3. Create `web/code_search.py` tool
4. Add tests with mock provider

### 7.5 Phase 4: Advanced Enhancement

#### E7: Tree-Sitter Security

1. Add `use_tree_sitter` field to `ShellSecurityContext`
2. Implement `_validate_with_tree_sitter()` and `_extract_commands_from_ast()`
3. Add optional dependency in `pyproject.toml`: `rawagents[tree-sitter]`
4. Add tests for AST extraction and obfuscation detection
5. Test graceful degradation when tree-sitter not installed

---

## 8. Reference Implementations

### 8.1 OpenCode (TypeScript/Bun)

| Enhancement | OpenCode Source | Key Pattern |
|-------------|----------------|-------------|
| E1 (Diagnostics) | `packages/opencode/src/tool/edit.ts` | Post-edit: `await LSP.touchFile(filePath); diagnostics = await LSP.diagnostics()` |
| E1 (LSP Client) | `packages/opencode/src/lsp/client.ts` | Full LSP client with `vscode-jsonrpc`, 9 operations |
| E2 (Batch) | `packages/opencode/src/tool/batch.ts` | `Promise.all()` with max 25 calls; recursive batch blocked |
| E5 (Truncation) | `packages/opencode/src/tool/truncation.ts` | Context-aware: checks `hasTaskTool(agent)` for hint selection |
| E6 (Sessions) | N/A (uses `workdir` param instead) | `workdir` parameter on bash tool; avoids cd tracking |
| E7 (Tree-sitter) | `packages/opencode/src/tool/bash.ts` | Tree-sitter bash parsing for command validation |
| E8 (Code Search) | `packages/opencode/src/tool/codesearch.ts` | Exa MCP API for code context search |

### 8.2 Claude Code (Anthropic)

| Enhancement | Claude Code Pattern |
|-------------|-------------------|
| E1 (Diagnostics) | IDE integration provides diagnostics after edits |
| E2 (Batch) | Multiple `tool_use` content blocks in single message |
| E5 (Truncation) | Output truncation with file save and offset hints |

### 8.3 SWE-ReX (SWE-agent)

| Enhancement | SWE-ReX Pattern |
|-------------|-----------------|
| E6 (Sessions) | Named shell sessions with sentinel-based completion detection |
| E6 (Runtime) | `AbstractRuntime` protocol for local/Docker/Modal/Fargate backends |

### 8.4 Aider

| Enhancement | Aider Pattern |
|-------------|---------------|
| E3 (Fuzzy) | `replace_most_similar_chunk()` with `difflib.SequenceMatcher`, threshold ~0.6 |
| E3 (EditBlock) | EditBlock format (`<<<<<<`/`======`/`>>>>>>`) with fuzzy fallback |

---

## 9. Testing Strategy

### 9.1 Test Matrix

| Enhancement | Unit Tests | Integration Tests | Edge Cases |
|-------------|-----------|-------------------|------------|
| E1 (Diagnostics) | Mock provider; verify diagnostics appended to result | Real ruff subprocess provider | Provider raises; provider returns empty; provider timeout |
| E2 (Batch) | 5 concurrent reads; error isolation | Mixed read+edit batch | Empty batch; single item; >25 items |
| E3 (Fuzzy) | Threshold boundary (0.69 vs 0.71); multi-line | Combined with other strategies | Empty old_string; zero-length file; identical match (should use Simple) |
| E4 (mtime) | Read-then-edit; external modification | Git checkout between read/edit | Deleted file; Permission error on stat(); mtime resolution |
| E5 (Truncation) | Line limit; byte limit; both | Bash + read consistency | Empty output; exactly at limit; Unicode truncation boundary |
| E6 (Sessions) | Create, reuse, close | Multi-command persistence | Dead session recovery; concurrent session access; timeout |
| E7 (Tree-sitter) | AST extraction for simple/nested/obfuscated | eval/exec recursive parsing | tree-sitter not installed; malformed bash; empty command |
| E8 (Code Search) | Mock provider; result formatting | Rate limiting | Provider not configured; API error; empty results |

### 9.2 Test Organization

```
tests/tools/builtin/
  fs/
    test_replacers.py           # E3: Add fuzzy matching tests
    test_security.py            # E4: Update mtime tracking tests
    test_edit.py                # E1, E3, E4: Post-edit diagnostics + fuzzy + mtime
    test_write.py               # E1, E4: Post-write diagnostics + mtime
    test_read.py                # E5: Truncation tests
    test_diagnostics.py         # E1: DiagnosticsProvider tests [NEW]
    test_truncation.py          # E5: Shared truncation tests [NEW]
  shell/
    test_bash.py                # E5, E6: Truncation + sessions
    test_security.py            # E7: Tree-sitter tests
    test_process_manager.py     # E6: Session management tests
  web/
    test_code_search.py         # E8: Code search tests [NEW]
  test_executor.py              # E2: Batch execution tests
```

### 9.3 Test Examples

**E3 — Fuzzy Matching**:
```python
async def test_fuzzy_replacer_similar_content():
    """Fuzzy matcher finds the most similar block above threshold."""
    content = "def hello():\n    print('Hello, world!')\n    return True\n"
    # LLM generates slightly wrong version:
    old_string = "def hello():\n    print('Hello world!')\n    return True\n"
    # Missing comma in 'Hello world!' vs 'Hello, world!'

    replacer = FuzzyReplacer()
    matches = replacer.find_matches(content, old_string)
    assert len(matches) == 1
    assert matches[0].matched_text == content  # Found the real content

async def test_fuzzy_replacer_below_threshold():
    """Fuzzy matcher rejects content below 0.7 threshold."""
    content = "def foo():\n    return 42\n"
    old_string = "class Bar:\n    value = 99\n"  # Completely different

    replacer = FuzzyReplacer()
    matches = replacer.find_matches(content, old_string)
    assert len(matches) == 0
```

**E4 — mtime Safety**:
```python
async def test_mtime_detects_external_modification(tmp_path):
    """Agent's edit is rejected if file was modified externally."""
    ctx = SecurityContext(workspace=str(tmp_path))
    f = tmp_path / "test.py"
    f.write_text("original")

    # Agent reads the file
    ctx.mark_file_read(f)

    # External modification (simulating user edit)
    import time; time.sleep(0.01)  # Ensure mtime differs
    f.write_text("user changed this")

    # Agent tries to edit
    check = ctx.check_read_before_edit(f)
    assert isinstance(check, str)
    assert "modified externally" in check
```

**E2 — Batch Execution**:
```python
async def test_batch_parallel_execution():
    """Batch executes independent calls in parallel."""
    executor = ToolExecutor([read_tool, grep_tool])
    calls = [
        ToolCall(id="1", name="read", arguments={"file_path": "/a.py"}),
        ToolCall(id="2", name="read", arguments={"file_path": "/b.py"}),
        ToolCall(id="3", name="grep", arguments={"pattern": "TODO"}),
    ]
    results = await executor.execute_batch(calls)
    assert len(results) == 3
    assert results[0].tool_call_id == "1"
    assert results[1].tool_call_id == "2"
    assert results[2].tool_call_id == "3"
```

---

## 10. Project Structure

### 10.1 New Files

```
src/rawagents/tools/
  executor.py                  # Modified: add execute_batch()
  builtin/
    batch.py                   # NEW (optional): batch tool wrapper
    fs/
      _diagnostics.py          # NEW: Diagnostic, DiagnosticsProvider
      _replacers.py            # Modified: add FuzzyReplacer
      _security.py             # Modified: mtime tracking
      _utils.py                # Modified: TruncationResult, truncate_output()
      edit.py                  # Modified: diagnostics, fuzzy notice, mtime refresh
      write.py                 # Modified: diagnostics, mtime refresh
      read.py                  # Modified: shared truncation
    shell/
      _security.py             # Modified: tree-sitter layer
      _process_manager.py      # Modified: session management
      bash.py                  # Modified: shared truncation, session param
    web/
      _types.py                # Modified: CodeSearchResult, CodeSearchProvider
      _context.py              # Modified: code_search_provider field
      code_search.py           # NEW: code_search tool

tests/tools/builtin/
  fs/
    test_diagnostics.py        # NEW
    test_truncation.py         # NEW
  web/
    test_code_search.py        # NEW
  test_executor.py             # Modified: batch tests
```

### 10.2 Dependency Changes

```toml
# In pyproject.toml:
[project.optional-dependencies]
tree-sitter = [
    "tree-sitter>=0.23",
    "tree-sitter-bash>=0.23",
]
```

---

## 11. Development Process

### 11.1 Implementation Checklist

#### Phase 1: Foundation (Target: 1 day)

- [ ] **E4: mtime tracking**
  - [ ] Update `_read_files` type in `_security.py`
  - [ ] Update `mark_file_read()` and `check_read_before_edit()`
  - [ ] Update `require_read_before_edit()` in `_utils.py`
  - [ ] Update `edit.py` and `write.py` to refresh mtime
  - [ ] Update existing tests
  - [ ] Add new mtime-specific tests

- [ ] **E3: Fuzzy matching**
  - [ ] Implement `FuzzyReplacer` in `_replacers.py`
  - [ ] Add to `_DEFAULT_STRATEGIES`
  - [ ] Add fuzzy notice in `edit.py`
  - [ ] Add threshold and edge case tests

- [ ] **E5: Smart truncation**
  - [ ] Add `TruncationResult` and `truncate_output()` to `_utils.py`
  - [ ] Refactor `bash.py` truncation
  - [ ] Refactor `read.py` truncation
  - [ ] Add hint generators
  - [ ] Verify existing tests still pass

#### Phase 2: Execution (Target: 1 day)

- [ ] **E2: Batch execution**
  - [ ] Add `execute_batch()` to `ToolExecutor`
  - [ ] Add tests for parallelism, error isolation, ordering
  - [ ] (Optional) Create `batch` tool wrapper

- [ ] **E6: Named sessions**
  - [ ] Add `ShellSession` to `_process_manager.py`
  - [ ] Implement sentinel-based completion detection
  - [ ] Add `session` parameter to `bash` tool
  - [ ] Add tests for persistence, cleanup, recovery

#### Phase 3: Integration (Target: 1 day)

- [ ] **E1: Diagnostics feedback**
  - [ ] Create `_diagnostics.py` with protocol and dataclass
  - [ ] Add provider field to `SecurityContext`
  - [ ] Integrate in `edit.py` and `write.py`
  - [ ] Add tests with mock provider

- [ ] **E8: Code search**
  - [ ] Add types to `_types.py`
  - [ ] Add field to `WebContext`
  - [ ] Create `code_search.py` tool
  - [ ] Add tests with mock provider

#### Phase 4: Advanced (Target: 1 day)

- [ ] **E7: Tree-sitter security**
  - [ ] Add `use_tree_sitter` field
  - [ ] Implement AST extraction
  - [ ] Add optional dependency to `pyproject.toml`
  - [ ] Add tests for obfuscation detection
  - [ ] Test graceful degradation

### 11.2 Quality Gates

Each enhancement must pass before merging:

1. **All existing tests pass** — no regressions
2. **New tests pass** — covering happy path, edge cases, error cases
3. **Ruff check passes** — `ruff check --fix && ruff format`
4. **Type hints complete** — all new code has type annotations
5. **Docstrings complete** — all public functions/classes documented
6. **Backward compatible** — verified with existing tool signatures

### 11.3 Review Checklist

- [ ] No breaking changes to existing tool signatures
- [ ] New optional parameters have sensible defaults
- [ ] Error messages are clear and actionable
- [ ] Protocols match existing patterns (`SearchProvider`, `ContentProcessor`)
- [ ] Advisory features (diagnostics, hints) never break core functionality
- [ ] No new required dependencies (tree-sitter is optional)
- [ ] Test coverage for all new code paths

---

## Appendix A: OpenCode Reference File Map

| OpenCode File | Enhancement | Key Takeaway |
|---------------|-------------|--------------|
| `src/tool/edit.ts` | E1 | `LSP.touchFile()` + `LSP.diagnostics()` after every edit |
| `src/tool/batch.ts` | E2 | `Promise.all()`, max 25, recursive batch blocked |
| `src/tool/bash.ts` | E6, E7 | `workdir` param, tree-sitter bash parsing |
| `src/tool/truncation.ts` | E5 | Context-aware hints based on available tools |
| `src/tool/codesearch.ts` | E8 | Exa MCP API integration |
| `src/lsp/client.ts` | E1 | Full LSP client with 9 operations via `vscode-jsonrpc` |
| `src/shell/shell.ts` | E6 | Shell detection, SIGTERM -> SIGKILL process killing |

## Appendix B: Aider Fuzzy Matching Reference

Aider's `editblock_coder.py` implements fuzzy matching via:

1. **`replace_most_similar_chunk()`** — Slides a window over the file content
2. **`difflib.SequenceMatcher.ratio()`** — Computes similarity (0.0-1.0)
3. **Threshold ~0.6** — Lower than our proposed 0.7 (we're more conservative)
4. **Line-based comparison** — Matches by lines, not characters
5. **Informative feedback** — Shows diff between search block and best match when below threshold

Our `FuzzyReplacer` implements the same algorithm with:
- Stricter threshold (0.7 vs 0.6) to prevent false positives
- Window size variation (+/- 20%) to handle added/removed lines
- Integration into the existing 5-strategy chain as the last resort

## Appendix C: SWE-ReX Session Pattern

SWE-ReX's named session approach:

1. **Sentinel markers**: Each command gets a unique sentinel appended (`echo "SENTINEL_<uuid>$?"`)
2. **Output parsing**: Read stdout until sentinel appears; extract exit code from sentinel line
3. **Session lifecycle**: Create on first use, reuse on subsequent calls, cleanup on close
4. **Process health**: Check `returncode is None` before reuse; recreate dead sessions

Our `ProcessManager.execute_in_session()` follows this exact pattern, adapted for Python's `asyncio.subprocess`.
