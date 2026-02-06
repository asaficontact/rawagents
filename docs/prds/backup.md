# Product Requirements Document (PRD)
# RawAgents Built-in File System Tools

**Version:** 1.0
**Date:** February 2026
**Status:** Draft
**Author:** Tawab Safi

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Background & Motivation](#2-background--motivation)
3. [Goals & Non-Goals](#3-goals--non-goals)
4. [Tool Inventory](#4-tool-inventory)
5. [Tool Specifications](#5-tool-specifications)
6. [Implementation Approach](#6-implementation-approach)
7. [Reference Implementations](#7-reference-implementations)
8. [Security Considerations](#8-security-considerations)
9. [Testing Strategy](#9-testing-strategy)
10. [Project Structure](#10-project-structure)
11. [Development Process](#11-development-process)

---

## 1. Executive Summary

### 1.1 What We're Building

The **File System Tools** module (`rawagents.tools.builtin.fs`) provides the core file operations needed to build Claude Code-like agents. These tools enable agents to read, write, edit, search, and navigate codebases.

Following RawAgents' **"Primitives over Frameworks"** philosophy, each tool is:
- A standalone, single-purpose function
- Independently testable
- Composable with other tools
- Usable without the full RawAgents framework

### 1.2 Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Architecture** | Separate tools (OpenCode style) | Better composability, debugging, LLM compatibility |
| **Edit Strategy** | String replacement (not line-based) | More reliable, matches Claude Code approach |
| **Grep Backend** | `ripgrep-python` (native binding) | Performance without subprocess overhead |
| **Path Handling** | Absolute paths required | Security, clarity, prevents confusion |
| **Security** | Symlink resolution before validation | Prevents path traversal attacks |

### 1.3 Tools Summary

| Tool | Purpose | Priority |
|------|---------|----------|
| `read` | Read file contents with line numbers | P0 |
| `write` | Create or overwrite files | P0 |
| `edit` | String replacement in files | P0 |
| `ls` | List directory contents | P0 |
| `glob` | Pattern-based file search | P0 |
| `grep` | Content search via ripgrep | P0 |
| `insert` | Insert content at line N | P1 |
| `multiedit` | Atomic batch edits | P1 |
| `patch` | Apply unified diffs | P2 |

---

## 2. Background & Motivation

### 2.1 Problem Statement

To build Claude Code-like agents with RawAgents, developers need reliable file system tools that:

1. **Match Claude Code's capabilities** - Same operations, same reliability
2. **Work with LLMs** - Clear schemas, predictable outputs, good error messages
3. **Are secure** - Prevent path traversal, handle edge cases safely
4. **Are fast** - Handle large codebases efficiently

### 2.2 Why Not Use Existing Packages?

| Option | Issue |
|--------|-------|
| LangChain FileManagementToolkit | Heavy dependency, no grep/glob with ripgrep |
| OpenHands str_replace_editor | Combined tool design, known issues with long files |
| Raw subprocess calls | No safety, inconsistent across platforms |

### 2.3 Our Approach

Port the **architecture** from OpenCode (separate tools) while implementing in **Python** with:
- Native ripgrep bindings for performance
- Pydantic validation for type safety
- Security-first path handling
- Comprehensive error messages

---

## 3. Goals & Non-Goals

### 3.1 Goals

**G1: Feature Parity with Claude Code**
- All file operations Claude Code agents can perform
- Same parameter patterns and behavior

**G2: Security by Default**
- Path traversal prevention via symlink resolution
- Configurable workspace boundaries
- Safe defaults for all operations

**G3: LLM-Optimized Output**
- Line numbers in output (cat -n style)
- Truncation with helpful messages
- Clear error messages with suggestions

**G4: Performance**
- Native ripgrep for grep operations
- Efficient glob using pathlib
- Lazy loading where possible

**G5: Testability**
- Each tool independently testable
- Mock filesystem support
- Comprehensive test coverage

### 3.2 Non-Goals

**NG1: GUI/IDE Integration**
- Tools are headless, CLI/API focused
- IDE plugins are out of scope

**NG2: Version Control**
- Git operations are separate tools
- Undo via git, not built-in

**NG3: Remote File Systems**
- Local filesystem only
- Cloud storage out of scope

**NG4: Binary File Editing**
- Text files only for edit operations
- Binary read support (images, PDFs) is P2

---

## 4. Tool Inventory

### 4.1 Priority 0 (Must Have)

These tools are essential for basic agent file operations:

```
┌─────────────────────────────────────────────────────────────────┐
│                    PRIORITY 0: CORE TOOLS                        │
├─────────────────────────────────────────────────────────────────┤
│  read   │ Read file contents with line numbers                   │
│  write  │ Create or overwrite files                              │
│  edit   │ Replace strings in files (must be unique)              │
│  ls     │ List directory contents                                │
│  glob   │ Find files by pattern (**/*.py)                        │
│  grep   │ Search file contents with ripgrep                      │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Priority 1 (Should Have)

Enhanced editing capabilities:

```
┌─────────────────────────────────────────────────────────────────┐
│                    PRIORITY 1: ENHANCED TOOLS                    │
├─────────────────────────────────────────────────────────────────┤
│  insert    │ Insert content after a specific line               │
│  multiedit │ Multiple edits in one atomic operation             │
└─────────────────────────────────────────────────────────────────┘
```

### 4.3 Priority 2 (Nice to Have)

Advanced operations:

```
┌─────────────────────────────────────────────────────────────────┐
│                    PRIORITY 2: ADVANCED TOOLS                    │
├─────────────────────────────────────────────────────────────────┤
│  patch     │ Apply unified diff patches                         │
│  read_image│ Read images as base64 for vision models            │
│  read_pdf  │ Extract text from PDF files                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Tool Specifications

### 5.1 Read Tool

**Purpose:** Read file contents with line numbers, supporting offset/limit for large files.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_path` | str | ✅ | - | Absolute path to file |
| `offset` | int | ❌ | 0 | Starting line (0-indexed) |
| `limit` | int | ❌ | 2000 | Maximum lines to read |

**Output Format:**
```
     1	First line of content
     2	Second line of content
     3	Third line of content
```
- Right-aligned line numbers (5 spaces)
- Tab separator between number and content
- Preserves original line endings

**Behavior:**
- Lines longer than 2000 characters are truncated with `... [truncated]`
- Returns error if file doesn't exist
- Returns error if path is outside allowed workspace
- Detects binary files and returns appropriate error

**Example:**
```python
result = await read(
    file_path="/project/src/main.py",
    offset=100,
    limit=50
)
# Returns lines 100-149 with line numbers
```

---

### 5.2 Write Tool

**Purpose:** Create new files or overwrite existing files.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_path` | str | ✅ | - | Absolute path to file |
| `content` | str | ✅ | - | Content to write |

**Behavior:**
- Creates parent directories if they don't exist
- Overwrites existing files completely
- Returns error if path is outside allowed workspace
- Returns confirmation with bytes written

**Safety:**
- Requires file to have been read first (tracked in session)
- Can be bypassed with `force=True` for new files

**Example:**
```python
result = await write(
    file_path="/project/src/new_file.py",
    content="def hello():\n    print('Hello, World!')\n"
)
# Returns: "Wrote 43 bytes to /project/src/new_file.py"
```

---

### 5.3 Edit Tool

**Purpose:** Perform exact string replacement in files.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_path` | str | ✅ | - | Absolute path to file |
| `old_string` | str | ✅ | - | Text to find (must be unique) |
| `new_string` | str | ✅ | - | Replacement text |
| `replace_all` | bool | ❌ | False | Replace all occurrences |

**Behavior:**
- **Exact match required** - character-for-character including whitespace
- **Uniqueness enforced** - fails if `old_string` matches multiple locations (unless `replace_all=True`)
- Returns error with context if no match found
- Returns error with match count if multiple matches found

**Error Messages:**
```
# No match found
Error: Could not find the specified text in /project/src/main.py
The text you're trying to replace does not exist in the file.
Suggestion: Use the read tool to verify the exact content.

# Multiple matches found
Error: Found 3 occurrences of the specified text in /project/src/main.py
The edit tool requires unique matches. Either:
1. Provide more context to make the match unique
2. Use replace_all=True to replace all occurrences
```

**Example:**
```python
result = await edit(
    file_path="/project/src/main.py",
    old_string="def hello():\n    print('Hello')",
    new_string="def hello():\n    print('Hello, World!')"
)
# Returns: "Successfully replaced text in /project/src/main.py"
```

---

### 5.4 LS Tool

**Purpose:** List directory contents with optional filtering.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | str | ✅ | - | Absolute path to directory |
| `ignore` | list[str] | ❌ | [] | Glob patterns to ignore |
| `show_hidden` | bool | ❌ | False | Include hidden files |

**Output Format:**
```
drwxr-xr-x  src/
drwxr-xr-x  tests/
-rw-r--r--  README.md
-rw-r--r--  pyproject.toml
```

**Behavior:**
- Returns directories first, then files
- Shows file permissions (Unix-style)
- Respects .gitignore patterns by default
- Limits to 1000 entries with truncation notice

**Example:**
```python
result = await ls(
    path="/project",
    ignore=["*.pyc", "__pycache__"],
    show_hidden=False
)
```

---

### 5.5 Glob Tool

**Purpose:** Find files matching a glob pattern.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `pattern` | str | ✅ | - | Glob pattern (e.g., `**/*.py`) |
| `path` | str | ❌ | "." | Root directory for search |
| `limit` | int | ❌ | 100 | Maximum files to return |

**Output:**
- List of absolute file paths
- **Sorted by modification time (newest first)**
- Truncation notice if limit exceeded

**Pattern Syntax:**
- `*` - any characters except /
- `**` - any characters including /
- `?` - single character
- `[abc]` - character class
- `{a,b}` - alternatives

**Example:**
```python
result = await glob(
    pattern="**/*.py",
    path="/project/src",
    limit=50
)
# Returns: ["/project/src/main.py", "/project/src/utils.py", ...]
```

---

### 5.6 Grep Tool

**Purpose:** Search file contents using ripgrep.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `pattern` | str | ✅ | - | Regex pattern to search |
| `path` | str | ❌ | "." | File or directory to search |
| `file_type` | str | ❌ | None | Filter by type (py, js, etc.) |
| `glob` | str | ❌ | None | File pattern filter |
| `output_mode` | str | ❌ | "files" | `content`, `files`, or `count` |
| `context_before` | int | ❌ | 0 | Lines before match (-B) |
| `context_after` | int | ❌ | 0 | Lines after match (-A) |
| `case_insensitive` | bool | ❌ | False | Ignore case (-i) |
| `multiline` | bool | ❌ | False | Match across lines |
| `limit` | int | ❌ | 100 | Maximum results |

**Output Modes:**

1. **files** (default) - Just file paths:
   ```
   /project/src/main.py
   /project/src/utils.py
   ```

2. **content** - Matching lines with context:
   ```
   /project/src/main.py:42:    def hello():
   /project/src/main.py:43:        print("Hello")
   ```

3. **count** - Match counts per file:
   ```
   /project/src/main.py:5
   /project/src/utils.py:2
   ```

**Example:**
```python
result = await grep(
    pattern="def.*hello",
    path="/project/src",
    file_type="py",
    output_mode="content",
    context_after=2
)
```

---

### 5.7 Insert Tool (P1)

**Purpose:** Insert content after a specific line number.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_path` | str | ✅ | - | Absolute path to file |
| `line_number` | int | ✅ | - | Line number to insert after (0 = beginning) |
| `content` | str | ✅ | - | Content to insert |

**Behavior:**
- Line 0 inserts at the beginning of the file
- Line N inserts after line N
- Returns error if line number exceeds file length

**Example:**
```python
result = await insert(
    file_path="/project/src/main.py",
    line_number=10,
    content="# This is a new comment\n"
)
```

---

### 5.8 MultiEdit Tool (P1)

**Purpose:** Perform multiple edits atomically.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_path` | str | ✅ | - | Absolute path to file |
| `edits` | list[Edit] | ✅ | - | List of edit operations |

**Edit Object:**
```python
{
    "old_string": str,  # Text to find
    "new_string": str,  # Replacement text
}
```

**Behavior:**
- **Atomic** - all edits succeed or none apply
- Edits are applied in order
- Each edit must have unique `old_string` in the file
- Returns error if any edit fails validation

**Example:**
```python
result = await multiedit(
    file_path="/project/src/main.py",
    edits=[
        {"old_string": "foo", "new_string": "bar"},
        {"old_string": "hello", "new_string": "world"},
    ]
)
```

---

### 5.9 Patch Tool (P2)

**Purpose:** Apply unified diff patches.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_path` | str | ✅ | - | Absolute path to file |
| `patch` | str | ✅ | - | Unified diff content |

**Patch Format:**
```diff
--- a/file.py
+++ b/file.py
@@ -10,6 +10,7 @@
 def hello():
     print("Hello")
+    print("World")
     return True
```

**Behavior:**
- Applies standard unified diff format
- Supports context lines for matching
- Returns error if patch doesn't apply cleanly

---

## 6. Implementation Approach

### 6.1 Core Module Structure

```python
# rawagents/tools/builtin/fs/__init__.py

from rawagents.tools.builtin.fs.read import read
from rawagents.tools.builtin.fs.write import write
from rawagents.tools.builtin.fs.edit import edit
from rawagents.tools.builtin.fs.ls import ls
from rawagents.tools.builtin.fs.glob import glob_files
from rawagents.tools.builtin.fs.grep import grep

__all__ = ["read", "write", "edit", "ls", "glob_files", "grep"]
```

### 6.2 Tool Implementation Pattern

Each tool follows this pattern:

```python
# rawagents/tools/builtin/fs/read.py

from typing import Annotated
from rawagents.tools import tool
from rawagents.tools.builtin.fs._security import validate_path, resolve_path

@tool
async def read(
    file_path: Annotated[str, "Absolute path to the file to read"],
    offset: Annotated[int, "Starting line number (0-indexed)"] = 0,
    limit: Annotated[int, "Maximum number of lines to read"] = 2000,
) -> str:
    """Read file contents with line numbers.

    Returns the file content with line numbers in cat -n format.
    Lines are numbered starting from 1.

    Example:
        >>> await read("/project/main.py", offset=0, limit=50)
        "     1\\tdef main():\\n     2\\t    print('Hello')\\n"
    """
    # Validate and resolve path
    resolved_path = resolve_path(file_path)
    validate_path(resolved_path)

    # Read file
    try:
        with open(resolved_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        return f"Error: File not found: {file_path}"
    except PermissionError:
        return f"Error: Permission denied: {file_path}"

    # Apply offset and limit
    selected_lines = lines[offset:offset + limit]

    # Format with line numbers
    result = []
    for i, line in enumerate(selected_lines):
        line_num = offset + i + 1
        # Truncate long lines
        if len(line) > 2000:
            line = line[:2000] + "... [truncated]\n"
        result.append(f"{line_num:>5}\t{line}")

    # Add truncation notice
    if offset + limit < len(lines):
        remaining = len(lines) - (offset + limit)
        result.append(f"\n... {remaining} more lines. Use offset={offset + limit} to continue.")

    return "".join(result)
```

### 6.3 Security Module

```python
# rawagents/tools/builtin/fs/_security.py

import os
from pathlib import Path
from typing import Optional

# Configurable workspace boundary
_workspace_root: Optional[Path] = None

def set_workspace(root: str) -> None:
    """Set the allowed workspace root directory."""
    global _workspace_root
    _workspace_root = Path(root).resolve()

def resolve_path(path: str) -> Path:
    """Resolve path following symlinks."""
    return Path(path).resolve()

def validate_path(path: Path) -> None:
    """Validate path is within allowed workspace.

    Raises:
        PermissionError: If path is outside workspace
    """
    if _workspace_root is None:
        return  # No restriction if workspace not set

    try:
        path.relative_to(_workspace_root)
    except ValueError:
        raise PermissionError(
            f"Access denied: {path} is outside the allowed workspace {_workspace_root}"
        )
```

---

## 7. Reference Implementations

### 7.1 Read Tool References

| Source | Location | Notes |
|--------|----------|-------|
| **OpenCode** | [github.com/sst/opencode/.../read.ts](https://github.com/sst/opencode/blob/dev/packages/opencode/src/tool/read.ts) | TypeScript, cat -n format |
| **Claude Code** | [gist.github.com/bgauryy/...](https://gist.github.com/bgauryy/0cdb9aa337d01ae5bd0c803943aa36bd) | Tool specification |
| **LangChain** | [github.com/langchain-ai/.../read.py](https://github.com/langchain-ai/langchain/tree/master/libs/community/langchain_community/tools/file_management/read.py) | Python, simple |
| **Strands Tools** | [github.com/strands-agents/tools/.../file_read.py](https://github.com/strands-agents/tools/blob/main/src/strands_tools/file_read.py) | Python, 10 modes |
| **MCP Filesystem** | [github.com/safurrier/mcp-filesystem](https://github.com/safurrier/mcp-filesystem) | Token-efficient |

### 7.2 Write Tool References

| Source | Location | Notes |
|--------|----------|-------|
| **OpenCode** | [github.com/sst/opencode/.../write.ts](https://github.com/sst/opencode/blob/dev/packages/opencode/src/tool/write.ts) | TypeScript |
| **LangChain** | [github.com/langchain-ai/.../write.py](https://github.com/langchain-ai/langchain/tree/master/libs/community/langchain_community/tools/file_management/write.py) | Python |

### 7.3 Edit Tool References

| Source | Location | Notes |
|--------|----------|-------|
| **OpenCode** | [github.com/sst/opencode/.../edit.ts](https://github.com/sst/opencode/blob/dev/packages/opencode/src/tool/edit.ts) | String replacement |
| **Anthropic text_editor** | [github.com/cablehead/anthropic-text-editor](https://github.com/cablehead/anthropic-text-editor) | Rust reference |
| **OpenHands** | [github.com/OpenHands/OpenHands/.../str_replace_editor](https://github.com/OpenHands/OpenHands) | Known issues documented |
| **Claude Quickstarts** | [github.com/anthropics/claude-quickstarts/.../edit.py](https://github.com/anthropics/claude-quickstarts) | Python |

### 7.4 Glob Tool References

| Source | Location | Notes |
|--------|----------|-------|
| **OpenCode** | [github.com/sst/opencode/.../glob.ts](https://github.com/sst/opencode/blob/dev/packages/opencode/src/tool/glob.ts) | Sorts by mtime |
| **Python pathlib** | [docs.python.org/3/library/pathlib.html](https://docs.python.org/3/library/pathlib.html) | Built-in |
| **wcmatch** | [github.com/facelessuser/wcmatch](https://github.com/facelessuser/wcmatch) | Extended patterns |

### 7.5 Grep Tool References

| Source | Location | Notes |
|--------|----------|-------|
| **OpenCode** | [github.com/sst/opencode/.../grep.ts](https://github.com/sst/opencode/blob/dev/packages/opencode/src/tool/grep.ts) | Ripgrep wrapper |
| **ripgrep-python** | [pypi.org/project/ripgrep-python](https://pypi.org/project/ripgrep-python/) | Native Rust binding |
| **rpygrep** | [pypi.org/project/rpygrep](https://pypi.org/project/rpygrep/) | Type-safe, async |
| **ripgrepy** | [github.com/securisec/ripgrepy](https://github.com/securisec/ripgrepy) | Method chaining |

### 7.6 Patch Tool References

| Source | Location | Notes |
|--------|----------|-------|
| **OpenCode** | [github.com/sst/opencode/.../apply_patch.ts](https://github.com/sst/opencode/blob/dev/packages/opencode/src/tool/apply_patch.ts) | V4A format |
| **OpenAI Codex** | [github.com/openai/codex/.../apply_patch](https://github.com/openai/codex/blob/main/codex-rs/apply-patch/apply_patch_tool_instructions.md) | V4A format spec |
| **codex-apply-patch** | [pypi.org/project/codex-apply-patch](https://pypi.org/project/codex-apply-patch/) | Python package |
| **Aider** | [github.com/Aider-AI/aider/.../editblock_coder.py](https://github.com/Aider-AI/aider/blob/main/aider/coders/editblock_coder.py) | Unified diff |

---

## 8. Security Considerations

### 8.1 Path Traversal Prevention

**Critical Vulnerability:** Symlinks can bypass path validation.

**Wrong Approach:**
```python
# VULNERABLE: Check string path, then follow symlinks
if path.startswith("/allowed/workspace"):
    content = open(path).read()  # Follows symlinks!
```

**Correct Approach:**
```python
# SECURE: Resolve symlinks FIRST, then validate
real_path = os.path.realpath(path)
if real_path.startswith("/allowed/workspace"):
    content = open(real_path).read()
```

**Implementation:**
```python
def validate_path(path: str, workspace: str) -> str:
    """Validate and resolve path securely.

    1. Resolve all symlinks
    2. Verify resolved path is within workspace
    3. Return resolved path for use
    """
    resolved = os.path.realpath(path)
    workspace_resolved = os.path.realpath(workspace)

    if not resolved.startswith(workspace_resolved + os.sep):
        raise PermissionError(f"Path {path} resolves outside workspace")

    return resolved
```

### 8.2 File Type Validation

- Check file type before operations
- Detect binary files by checking for null bytes
- Reject operations on sensitive files (.env, credentials)

### 8.3 Resource Limits

| Resource | Limit | Rationale |
|----------|-------|-----------|
| Max file size | 10MB | Prevent memory exhaustion |
| Max lines | 50,000 | Prevent context overflow |
| Max line length | 2,000 chars | Prevent parsing issues |
| Max glob results | 1,000 | Prevent enumeration |
| Max grep results | 1,000 | Prevent output explosion |

---

## 9. Testing Strategy

### 9.1 Test Structure

```
tests/tools/builtin/fs/
├── conftest.py              # Shared fixtures
├── test_read.py
├── test_write.py
├── test_edit.py
├── test_ls.py
├── test_glob.py
├── test_grep.py
├── test_insert.py
├── test_multiedit.py
├── test_patch.py
└── test_security.py
```

### 9.2 Test Categories

**Unit Tests (per tool):**
- Happy path operations
- Edge cases (empty files, long lines, unicode)
- Error handling (file not found, permission denied)
- Parameter validation

**Security Tests:**
- Path traversal via ..
- Symlink escape attempts
- Workspace boundary enforcement
- Sensitive file protection

**Integration Tests:**
- Tool chaining (read → edit → write)
- Concurrent operations
- Large file handling

### 9.3 Fixtures

```python
# tests/tools/builtin/fs/conftest.py

import pytest
import tempfile
from pathlib import Path

@pytest.fixture
def temp_workspace():
    """Create a temporary workspace directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)

        # Create test files
        (workspace / "test.py").write_text("def hello():\n    pass\n")
        (workspace / "subdir").mkdir()
        (workspace / "subdir" / "nested.py").write_text("# nested\n")

        yield workspace

@pytest.fixture
def mock_large_file(temp_workspace):
    """Create a large test file."""
    content = "\n".join(f"Line {i}" for i in range(10000))
    (temp_workspace / "large.txt").write_text(content)
    return temp_workspace / "large.txt"
```

---

## 10. Project Structure

```
src/rawagents/tools/builtin/
├── __init__.py              # Exports all builtin tools
├── fs/
│   ├── __init__.py          # File system tools exports
│   ├── _security.py         # Path validation, workspace handling
│   ├── _utils.py            # Shared utilities
│   ├── read.py              # Read tool
│   ├── write.py             # Write tool
│   ├── edit.py              # Edit tool
│   ├── ls.py                # LS tool
│   ├── glob.py              # Glob tool
│   ├── grep.py              # Grep tool
│   ├── insert.py            # Insert tool (P1)
│   ├── multiedit.py         # MultiEdit tool (P1)
│   └── patch.py             # Patch tool (P2)
├── web/                     # Web tools (future)
├── shell/                   # Shell tools (future)
└── agent/                   # Agent orchestration tools (future)
```

---

## 11. Development Process

### 11.1 Iterative Implementation

**IMPORTANT:** This PRD should be implemented **sequentially**, one tool at a time:

```
For each tool in [read, write, edit, ls, glob, grep, insert, multiedit, patch]:
    1. Research
       - Study reference implementations listed in Section 7
       - Understand edge cases and known issues
       - Finalize implementation approach

    2. Test First
       - Write comprehensive tests before implementation
       - Cover happy path, edge cases, and error scenarios
       - Include security tests

    3. Implement
       - Follow the pattern in Section 6.2
       - Ensure all tests pass
       - Add docstrings and type hints

    4. Review
       - Code review against reference implementations
       - Security review for path handling
       - Performance testing for large files/directories

    5. Document
       - Update docstrings
       - Add usage examples
       - Document any deviations from spec
```

### 11.2 Implementation Order

| Phase | Tools | Dependency |
|-------|-------|------------|
| Phase 1 | `read`, `ls`, `glob` | None (read-only) |
| Phase 2 | `write`, `edit` | read (for verification) |
| Phase 3 | `grep` | ripgrep-python package |
| Phase 4 | `insert`, `multiedit` | edit |
| Phase 5 | `patch` | edit, unified-diff parsing |

### 11.3 Definition of Done

A tool is complete when:

- [ ] All tests pass (>90% coverage)
- [ ] Security tests pass
- [ ] Performance acceptable for files up to 10MB
- [ ] Error messages are clear and actionable
- [ ] Docstrings complete with examples
- [ ] Type hints for all parameters and return values
- [ ] Works with RawAgents `@tool` decorator
- [ ] Integration test with actual LLM passes

---

## Appendix A: Dependencies

**Required:**
```toml
[project.dependencies]
# Core
pydantic = ">=2.0"

# For grep tool
ripgrep-python = ">=0.1"  # OR rpygrep for async

# For patch tool (P2)
unidiff = ">=0.7"  # Optional, for unified diff parsing
```

**Development:**
```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21",
    "pytest-cov>=4.0",
]
```

---

## Appendix B: Related Documents

- [RawAgents Vision](../vision.md)
- [RawAgents Philosophy](../rawagents_philosophy.md)
- [Tool Executor PRD](./tool_executor.md)
- [Claude Code Research](../../research/claude_code_tools.md)

---

## Appendix C: Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Feb 2026 | Initial PRD |
