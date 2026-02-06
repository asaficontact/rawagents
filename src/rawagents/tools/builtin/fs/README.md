# RawAgents Filesystem Tools

A comprehensive, security-first filesystem tools library for AI agent operations. This module provides 8 file system tools with robust security controls, multiple replacement strategies for LLM resilience, and full async support.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Security Model](#security-model)
- [Tools Reference](#tools-reference)
- [Utility Modules](#utility-modules)
- [Configuration Options](#configuration-options)
- [Testing](#testing)
- [Error Handling](#error-handling)

---

## Overview

The filesystem tools module provides:

- **8 File Operations**: read, write, edit, multiedit, list_dir, glob, grep, apply_patch
- **Security-First Design**: Workspace boundaries, symlink protection, sensitive file blocking
- **LLM Resilience**: 5 cascading replacement strategies reduce brittle exact-match failures
- **Read-Before-Edit Safety**: Prevents blind file overwrites
- **Async-Native**: All tools support async/await patterns
- **Structured Output**: Optional JSON format for programmatic consumption

---

## Architecture

```
fs/
├── __init__.py           # Public API facade
├── _security.py          # Security layer (SecurityContext)
├── _locking.py           # Cross-platform file locking
├── _utils.py             # Shared utilities
├── _diagnostics.py       # LSP diagnostics integration
├── _replacers.py         # 5 edit replacement strategies
├── read.py               # File reading tool
├── write.py              # File writing tool
├── edit.py               # Single edit tool
├── multiedit.py          # Atomic multi-edit tool
├── list.py               # Directory listing tool
├── glob.py               # Pattern matching tool
├── grep.py               # Content search tool
└── apply_patch.py        # Codex V4A patch application
```

### Dependency Flow

```
                    ┌─────────────────┐
                    │   __init__.py   │  (Public API)
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  _security   │◄───│    Tools     │───►│   _utils     │
└──────────────┘    └──────────────┘    └──────────────┘
        │                    │
        │                    ▼
        │           ┌──────────────┐
        └───────────│  _replacers  │
                    └──────────────┘
```

---

## Quick Start

### Basic Setup

```python
from rawagents.tools.builtin.fs import (
    SecurityContext,
    set_security_context,
    read,
    write,
    edit,
    glob,
    grep,
)

# 1. Configure security context (REQUIRED)
ctx = SecurityContext(workspace="/path/to/project")
set_security_context(ctx)

# 2. Use tools
async def main():
    # Read a file
    content = await read(file_path="/path/to/project/src/main.py")

    # Edit a file (must read first)
    result = await edit(
        file_path="/path/to/project/src/main.py",
        old_string="def old_function():",
        new_string="def new_function():",
    )

    # Search for patterns
    matches = await grep(pattern="TODO", path="/path/to/project")

    # Find files
    files = await glob(pattern="**/*.py", path="/path/to/project")
```

### Available Imports

```python
from rawagents.tools.builtin.fs import (
    # Security
    SecurityContext,
    SecurityContextNotSetError,
    WorkspaceSecurityError,
    get_security_context,
    set_security_context,
    validate_path,

    # Tools
    read,
    write,
    edit,
    multiedit,
    EditOp,
    list_dir,
    glob,
    grep,
    apply_patch,
)
```

---

## Security Model

### SecurityContext

The `SecurityContext` class enforces all security constraints:

```python
@dataclass
class SecurityContext:
    workspace: Optional[str] = None          # Root directory boundary
    denied_patterns: list[str] = [...]       # 45+ sensitive file patterns
    allowed_patterns: list[str] = []         # Override patterns (allowlist)
    max_file_size: int = 10 * 1024 * 1024    # 10MB default
    max_path_depth: int = 50                 # Directory depth limit
    binary_extensions: frozenset[str] = ...  # 30+ binary extensions
```

### Security Features

| Feature | Description |
|---------|-------------|
| **Workspace Boundaries** | All paths must resolve within the workspace directory |
| **Symlink Protection** | Symlinks are resolved before validation to prevent escapes |
| **Sensitive File Blocking** | Default patterns block `.env`, credentials, keys, etc. |
| **Read-Before-Edit** | Files must be read before write/edit/delete operations |
| **Resource Limits** | Max file size (10MB) and path depth (50) limits |
| **Binary Detection** | By extension and content sampling (null bytes) |

### Default Denied Patterns

```python
# Environment files
"*.env", ".env", ".env.*", "*/.env"

# Credentials
"*credentials*", "*secret*", "*password*", "*token*"

# Cryptographic keys
"*.pem", "*.key", "*.p12", "*id_rsa*", "*id_ed25519*"

# Cloud config
"*.aws/credentials", "*.ssh/config"

# Git credentials
"*.git-credentials", "*.netrc"
```

### Path Validation Order (Critical for Security)

1. **Resolve symlinks** → Get canonical path
2. **Check workspace boundary** → BEFORE existence check (prevents info leakage)
3. **Check file existence** → If required
4. **Check path depth** → Max 50 levels
5. **Check denied patterns** → Unless in allowlist

### Customizing Security

```python
# Allow specific sensitive files
ctx = SecurityContext(
    workspace="/project",
    allowed_patterns=[".env.example", "*.env.test"],
)

# Add custom denied patterns
ctx = SecurityContext(
    workspace="/project",
    denied_patterns=[
        *SecurityContext().denied_patterns,  # Keep defaults
        "*backup*",
        "*.bak",
    ],
)

# Adjust resource limits
ctx = SecurityContext(
    workspace="/project",
    max_file_size=50 * 1024 * 1024,  # 50MB
    max_path_depth=100,
)
```

---

## Tools Reference

### read()

Read file contents with line numbers.

```python
async def read(
    file_path: str,              # Absolute path to file
    offset: int = 0,             # Starting line (0-indexed)
    limit: int = 2000,           # Max lines to read
) -> str
```

**Features:**
- Line numbers in `cat -n` format (right-aligned 6 chars + tab)
- Streaming for large files (>10MB)
- Base64 encoding for media files (images, PDFs)
- Similar filename suggestions on file-not-found
- Marks files as read for read-before-edit tracking

**Output Format:**
```
     1	def hello():
     2	    print("Hello")
... (98 more lines, use offset=3 to continue)
```

**Error Messages:**
- `Error: File not found: {path}` (with suggestions)
- `Error: Cannot read binary file: {path}`
- `Error: {path} is outside workspace`

---

### write()

Create new files or overwrite existing files.

```python
async def write(
    file_path: str,    # Absolute path to file
    content: str,      # Content to write
) -> str
```

**Features:**
- Creates parent directories automatically
- Requires read-before-edit for existing files
- Marks file as read after writing
- UTF-8 encoding

**Output:** `Wrote file successfully.`

**Error Messages:**
- `Error: File '{path}' exists but was not read in this session`
- `Error: Permission denied writing to: {path}`

---

### edit()

Perform surgical text replacements with 5 fallback strategies.

```python
async def edit(
    file_path: str,           # Absolute path to file
    old_string: str,          # Text to replace
    new_string: str,          # Replacement text
    replace_all: bool = False # Replace all occurrences
) -> str
```

**Features:**
- 5 cascading replacement strategies (see below)
- Requires read-before-edit
- Empty `old_string` creates/overwrites entire file
- Unique match enforcement without `replace_all`

**Replacement Strategies** (tried in order):

| # | Strategy | Description |
|---|----------|-------------|
| 1 | Simple | Exact substring match |
| 2 | LineTrimmed | Strips leading/trailing whitespace per line |
| 3 | BlockAnchor | Matches first + last line as anchors |
| 4 | WhitespaceNormalized | Collapses all whitespace differences |
| 5 | IndentationFlexible | Matches relative indentation structure |

**Output:**
- `Edit applied successfully.`
- `Edit applied successfully. (3 replacements)`
- `Edit applied successfully. (created new file)`

**Error Messages:**
- `Error: old_string not found in content`
- `Error: Found N matches... use replace_all=True`
- `Error: File '{path}' was not read in this session`

---

### multiedit()

Perform multiple edits atomically (all succeed or all fail).

```python
from rawagents.tools.builtin.fs import multiedit, EditOp

async def multiedit(
    file_path: str,          # Absolute path to file
    edits: list[EditOp],     # Edit operations
) -> str

class EditOp(BaseModel):
    file_path: str           # Must match top-level file_path
    old_string: str
    new_string: str
    replace_all: bool = False
```

**Features:**
- True atomic semantics (rollback on failure)
- Sequential application in order
- All edits must target same file
- Uses same 5 replacement strategies

**Output:** `MultiEdit applied successfully. (2 edits, 3 replacements)`

---

### list_dir()

List directory contents with tree visualization.

```python
async def list_dir(
    path: str = ".",                # Directory to list
    ignore: Optional[list[str]] = None  # Additional ignore patterns
) -> str
```

**Features:**
- Unicode tree characters (├, └, │)
- Default ignores: `.git`, `node_modules`, `__pycache__`, `.venv`, etc.
- Maximum 100 entries (truncated with message)
- Directories marked with trailing `/`

**Output:**
```
/path/to/directory/
├── src/
│   ├── main.py
│   └── utils.py
├── tests/
└── README.md
```

---

### glob()

Find files matching glob patterns, sorted by modification time.

```python
async def glob(
    pattern: str,                    # Glob pattern (e.g., "**/*.py")
    path: Optional[str] = None,      # Search directory
    structured: bool = False         # Return JSON format
) -> str
```

**Features:**
- Standard glob patterns: `*`, `**`, `?`, `[abc]`
- Newest files first (mtime sorting)
- Maximum 100 results
- Directories excluded from results

**Output (default):**
```
/path/to/newest.py
/path/to/older.py

(Results are truncated. Consider using a more specific path or pattern.)
```

**Output (structured=True):**
```json
{
  "count": 2,
  "truncated": false,
  "results": ["/path/to/newest.py", "/path/to/older.py"]
}
```

---

### grep()

Search file contents using regex patterns.

```python
async def grep(
    pattern: str,                    # Regex pattern
    path: Optional[str] = None,      # Search directory
    include: Optional[str] = None,   # File filter (e.g., "*.py")
    structured: bool = False         # Return JSON format
) -> str
```

**Features:**
- Full Python regex syntax
- Ripgrep acceleration (falls back to Python if unavailable)
- Maximum 100 matches
- Line truncation at 2000 characters
- Automatic binary file skipping
- Newest files first

**Output (default):**
```
Found 3 matches

/path/to/file.py:
  Line 42: matching line text
  Line 43: another match

/path/to/other.py:
  Line 10: match here
```

**Output (structured=True):**
```json
{
  "count": 3,
  "truncated": false,
  "skipped_paths": false,
  "files": {
    "/path/to/file.py": [
      {"line": 42, "text": "matching line text"}
    ]
  }
}
```

---

### apply_patch()

Apply Codex V4A format patches.

```python
async def apply_patch(
    patch_text: str,    # Full patch text
) -> str
```

**Patch Format:**
```
*** Begin Patch
*** Add File: path/to/new.py
+def hello():
+    pass
*** Update File: path/to/existing.py
*** Move to: path/to/renamed.py    (optional)
@@ -1,2 +1,2 @@
-def old():
+def new():
     pass
*** Delete File: path/to/remove.py
*** End Patch
```

**Operations:**
- `Add File`: Create new file with content
- `Update File`: Modify existing file with diff chunks
- `Move to`: Rename/move file (with Update)
- `Delete File`: Remove file

**Output:**
```
Success. Updated the following files:
A src/new.py
M src/modified.py
D src/deleted.py
```

---

## Utility Modules

### _utils.py - Shared Utilities

| Function | Description |
|----------|-------------|
| `format_cat_n(lines, start)` | Format lines with line numbers |
| `truncate_line(line, max_len)` | Truncate with "..." suffix |
| `detect_binary(path, sample_size)` | Detect binary by null bytes |
| `suggest_similar_files(name, dir)` | Fuzzy filename suggestions |
| `is_media_file(path)` | Check for images/PDFs |
| `format_file_diagnostics(items)` | Format LSP diagnostics |

### _replacers.py - Replacement Strategies

The 5 replacement strategies reduce LLM brittleness:

```python
from rawagents.tools.builtin.fs._replacers import find_and_replace

result = find_and_replace(
    content="file content",
    old_string="text to find",
    new_string="replacement",
    replace_all=False,
)

if result.success:
    print(f"Replaced using {result.strategy} strategy")
    print(result.content)
else:
    print(f"Failed: {result.error}")
```

### _locking.py - File Locking

Cross-platform file locking for TOCTOU protection:

```python
from rawagents.tools.builtin.fs._locking import file_lock

# Async version
async with file_lock(path, exclusive=True, timeout=5.0):
    content = path.read_text()
    # ... modify ...
    path.write_text(new_content)

# Sync version
from rawagents.tools.builtin.fs._locking import file_lock_sync

with file_lock_sync(path):
    # ... operations ...
```

### _diagnostics.py - LSP Integration

Protocol for integrating diagnostics after file operations:

```python
from rawagents.tools.builtin.fs._diagnostics import (
    DiagnosticsProvider,
    DiagnosticItem,
    set_diagnostics_provider,
)

class MyLSPProvider:
    async def get_diagnostics(self, path: Path) -> list[DiagnosticItem]:
        # Query LSP server
        return [
            DiagnosticItem(
                line=10,
                severity="error",
                message="Undefined variable 'x'",
                source="pyright",
            )
        ]

set_diagnostics_provider(MyLSPProvider())
```

---

## Configuration Options

### SecurityContext Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `workspace` | `str \| None` | `None` | Root directory boundary |
| `denied_patterns` | `list[str]` | 45+ patterns | Blocked file patterns |
| `allowed_patterns` | `list[str]` | `[]` | Override allowlist |
| `max_file_size` | `int` | 10MB | Maximum file size |
| `max_path_depth` | `int` | 50 | Maximum directory depth |
| `binary_extensions` | `frozenset` | 30+ | Binary file extensions |

### Tool Constants

| Tool | Constant | Value | Description |
|------|----------|-------|-------------|
| read | `DEFAULT_LINE_LIMIT` | 2000 | Max lines per read |
| read | `MAX_OUTPUT_BYTES` | 50KB | Output truncation |
| read | `STREAMING_THRESHOLD` | 10MB | Use streaming above |
| grep | `MAX_MATCHES` | 100 | Result limit |
| grep | `MAX_LINE_LENGTH` | 2000 | Line truncation |
| glob | `MAX_RESULTS` | 100 | Result limit |
| list | `MAX_FILES` | 100 | Entry limit |

---

## Testing

### Test Fixtures

The test suite provides reusable fixtures in `conftest.py`:

```python
import pytest
from pathlib import Path
from rawagents.tools.builtin.fs import SecurityContext, set_security_context

@pytest.fixture
def temp_workspace() -> Generator[Path, None, None]:
    """Temporary directory with test files."""
    # Creates: test.py, subdir/nested.py, large.txt (100 lines)
    ...

@pytest.fixture
def secure_context(temp_workspace: Path) -> Generator[SecurityContext, None, None]:
    """Security context restricted to temp_workspace."""
    ctx = SecurityContext(workspace=str(temp_workspace))
    set_security_context(ctx)
    yield ctx
```

### Writing Tests

```python
from rawagents.tools.builtin.fs import read, edit, SecurityContext, set_security_context

class TestMyFeature:
    @pytest.mark.asyncio
    async def test_reads_file(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        # Setup
        test_file = temp_workspace / "test.txt"
        test_file.write_text("hello world")

        # Execute
        result = await read(file_path=str(test_file))

        # Assert
        assert "hello world" in result
        assert "Error" not in result

    @pytest.mark.asyncio
    async def test_edit_requires_read_first(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        existing = temp_workspace / "existing.txt"
        existing.write_text("original")

        # Should fail - not read yet
        result = await edit(
            file_path=str(existing),
            old_string="original",
            new_string="modified",
        )
        assert "Error" in result

        # Read first, then edit - should succeed
        await read(file_path=str(existing))
        result = await edit(
            file_path=str(existing),
            old_string="original",
            new_string="modified",
        )
        assert "successfully" in result.lower()
```

### Running Tests

```bash
# Run all filesystem tests
pytest tests/tools/builtin/fs/ -v

# Run with coverage
pytest tests/tools/builtin/fs/ -v --cov=rawagents.tools.builtin.fs

# Run specific test file
pytest tests/tools/builtin/fs/test_security.py -v

# Run specific test class
pytest tests/tools/builtin/fs/test_edit.py::TestEditFallbackStrategies -v
```

---

## Error Handling

### Exception Types

| Exception | Base | When Raised |
|-----------|------|-------------|
| `WorkspaceSecurityError` | `PermissionError` | Path validation failures |
| `SecurityContextNotSetError` | `RuntimeError` | No context configured |
| `FileNotFoundError` | (builtin) | File doesn't exist |
| `FileLockError` | `OSError` | Lock acquisition failed |

### Error Return Pattern

Tools return error strings (not exceptions) for LLM compatibility:

```python
result = await edit(...)

if "Error:" in result:
    # Handle error
    print(f"Edit failed: {result}")
else:
    # Success
    print("Edit succeeded")
```

### Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| `File not found: {path}` | Path doesn't exist | Check path spelling |
| `{path} is outside workspace` | Path escapes boundary | Use path within workspace |
| `File was not read in this session` | Read-before-edit | Call `read()` first |
| `old_string not found in content` | No match found | Check text carefully |
| `Found N matches... use replace_all` | Ambiguous match | Add context or use `replace_all` |
| `matches blocked pattern` | Sensitive file | Add to `allowed_patterns` |

---

## Best Practices

### 1. Always Set Security Context First

```python
# ✅ Good
ctx = SecurityContext(workspace="/project")
set_security_context(ctx)
result = await read(file_path="/project/file.py")

# ❌ Bad - Uses permissive default with deprecation warning
result = await read(file_path="/some/path")
```

### 2. Read Before Edit

```python
# ✅ Good
content = await read(file_path=path)  # Marks as read
result = await edit(file_path=path, ...)

# ❌ Bad - Will fail
result = await edit(file_path=path, ...)  # Error: not read
```

### 3. Use Structured Output for Parsing

```python
# ✅ Good - Parse JSON
import json
result = await glob(pattern="**/*.py", structured=True)
data = json.loads(result)
for file in data["results"]:
    process(file)

# ❌ Bad - Parse text
result = await glob(pattern="**/*.py")
files = result.split("\n")  # Fragile
```

### 4. Handle Large Files with Pagination

```python
# ✅ Good - Use offset/limit
offset = 0
while True:
    result = await read(file_path=path, offset=offset, limit=100)
    if "more lines" not in result:
        break
    offset += 100
```

### 5. Use Specific Patterns

```python
# ✅ Good - Specific pattern
files = await glob(pattern="src/**/*.py", path="/project")

# ❌ Bad - Too broad
files = await glob(pattern="**/*", path="/project")  # May hit limits
```

---

## Version History

- **v1.0**: Initial implementation with all 8 tools
- **v1.1**: Added 5 replacement strategies for LLM resilience
- **v1.2**: Added read-before-edit enforcement, file locking, diagnostics protocol, streaming for large files, structured output

---

## License

Part of the RawAgents project.
