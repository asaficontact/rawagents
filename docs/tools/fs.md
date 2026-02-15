# File System Tools

The `rawagents.tools.builtin.fs` module provides 8 tools for reading, writing, searching, and modifying files. Every operation is validated through a `SecurityContext` that enforces workspace boundaries, blocks sensitive file patterns, prevents symlink-escape attacks, and tracks read-before-edit state.

---

## Security Context

All fs tools obtain their security settings from a `SecurityContext` instance stored in a `contextvars.ContextVar`. Configure it once at startup and every subsequent tool call respects it.

```python
from rawagents.tools.builtin.fs import SecurityContext, set_security_context

ctx = SecurityContext(workspace="/home/user/project")
set_security_context(ctx)
```

### SecurityContext fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `workspace` | `str \| None` | `None` | Root directory for allowed operations. If `None`, no workspace boundary is enforced. |
| `denied_patterns` | `list[str]` | See below | Glob patterns for files that should never be accessed. |
| `allowed_patterns` | `list[str]` | `[]` | Glob patterns that override `denied_patterns` (allowlist). |
| `max_file_size` | `int` | `10485760` (10 MB) | Maximum file size in bytes for read/write operations. |
| `max_path_depth` | `int` | `50` | Maximum directory depth to prevent deeply nested path attacks. |
| `binary_extensions` | `frozenset[str]` | See below | File extensions treated as binary (`.exe`, `.dll`, `.zip`, `.pyc`, ...). |
| `track_file_modifications` | `bool` | `True` | Track file mtime to detect external changes between read and edit. Set to `False` in sandbox environments where mtime tracking is unreliable. |
| `diagnostics_provider` | `DiagnosticsProvider \| None` | `None` | Optional provider for post-edit feedback. See [Diagnostics Protocol](#diagnostics-protocol). |

**Default denied patterns** block environment files (`*.env`, `.env.*`), credentials (`*credentials*`, `*secret*`, `*password*`, `*token*`), cryptographic keys (`*.pem`, `*.key`, `*id_rsa*`, ...), AWS/SSH/Git credential files, and more.

**Default binary extensions** include executables (`.exe`, `.dll`, `.so`, `.dylib`), archives (`.zip`, `.tar`, `.gz`, `.7z`), bytecode (`.pyc`, `.pyo`), Java artifacts (`.class`, `.jar`), databases (`.db`, `.sqlite`), WebAssembly (`.wasm`), and object files (`.o`, `.a`, `.lib`).

### Access control functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `set_security_context` | `(ctx: SecurityContext) -> None` | Set the context for the current async context. |
| `get_security_context` | `(allow_permissive: bool = True) -> SecurityContext` | Get the current context. If none is set and `allow_permissive=True`, creates a permissive default with a `DeprecationWarning`. If `allow_permissive=False`, raises `SecurityContextNotSetError`. |
| `validate_path` | `(path: str, check_exists: bool = True) -> Path` | Convenience wrapper that calls `get_security_context().validate_path(...)`. |

### Read-before-edit tracking

The context tracks which files have been read during the current session. When `track_file_modifications` is `True`, it also records each file's `st_mtime` at read time. Before an edit or write to an existing file, the tools call `check_read_before_edit()`:

| Return value | Meaning |
|--------------|---------|
| `True` | File was read and is unchanged, or the file is new. Safe to edit. |
| `False` | File was never read in this session. The tool returns an error asking the user to read first. |
| `str` | File was read but modified externally since the last read. The returned string is a warning message. |

---

## Tool Reference

### read

```python
async def read(
    file_path: Annotated[str, "The absolute path to the file to read"],
    offset: Annotated[int, "Line number to start reading from (0-indexed)"] = 0,
    limit: Annotated[int, "Maximum number of lines to read"] = 2000,
) -> str
```

Read file contents with line numbers in `cat -n` format (right-aligned line numbers, 1-based in output). The `offset` parameter is 0-indexed.

Key constants:

| Constant | Value | Purpose |
|----------|-------|---------|
| `DEFAULT_LINE_LIMIT` | `2000` | Default value for `limit`. |
| `MAX_OUTPUT_BYTES` | `51200` (50 KB) | Output is truncated at this byte limit. |
| `MAX_LINE_LENGTH` | `2000` | Lines longer than this are truncated. |
| `STREAMING_THRESHOLD` | `10485760` (10 MB) | Files larger than this use a streaming line reader instead of loading into memory. |

Behaviour:

- Binary files (detected by extension or content sampling) return `"Error: Cannot read binary file: ..."`.
- Media files (images, PDFs) return base64-encoded content as a data URL.
- If the output exceeds 50 KB it is truncated and a continuation hint is appended.
- If fewer lines remain than were requested, a hint with the next `offset` value is appended.
- The file is marked as read for read-before-edit tracking.

```python
content = await read(file_path="/project/main.py")
# Returns: "     1\tdef main():\n     2\t    pass\n"

# Paginate a large file
page = await read(file_path="/project/big.py", offset=100, limit=50)
```

---

### write

```python
async def write(
    file_path: Annotated[str, "The absolute path to the file to write"],
    content: Annotated[str, "Content to write to the file"],
) -> str
```

Create or overwrite a file. Parent directories are created automatically.

Behaviour:

- Existing files must have been read first in the current session (read-before-edit tracking).
- New files (that do not exist yet) can be written without a prior read.
- Content size is validated against `max_file_size`.
- Existing files are locked for TOCTOU protection during the write.
- Returns `"Wrote file successfully."` on success.

```python
await write(file_path="/project/new_file.py", content="print('hello')")
```

---

### edit

```python
async def edit(
    file_path: Annotated[str, "The absolute path to the file to modify"],
    old_string: Annotated[str, "The text to replace"],
    new_string: Annotated[str, "The replacement text (must differ from old_string)"],
    replace_all: Annotated[bool, "Replace all occurrences (default: False)"] = False,
) -> str
```

Replace `old_string` with `new_string` using a chain of 6 matching strategies (see [Matching Strategies](#matching-strategies)). The file must have been read first.

Special cases:

- If `old_string` is empty, the file is created or overwritten with `new_string`.
- If `replace_all=False` and multiple matches are found, an error is returned.
- If the replacement is applied via the fuzzy strategy, the success message includes `"(applied via fuzzy matching -- verify the result)"`.

```python
await edit(
    file_path="/project/main.py",
    old_string="def hello():\n    pass",
    new_string="def hello():\n    print('Hello!')",
)
# Returns: "Edit applied successfully."

await edit(
    file_path="/project/main.py",
    old_string="foo",
    new_string="bar",
    replace_all=True,
)
# Returns: "Edit applied successfully. (3 replacements)"
```

---

### list_dir

```python
async def list_dir(
    path: Annotated[str, "Directory to list. Absolute path recommended."] = ".",
    ignore: Annotated[list[str] | None, "Glob patterns to ignore (added to defaults)"] = None,
) -> str
```

List files under a directory with Unicode tree-style output (`|--`, `└──`).

Defaults:

| Constant | Value | Purpose |
|----------|-------|---------|
| `MAX_FILES` | `100` | Maximum entries returned. If exceeded, output is truncated with a message. |
| `DEFAULT_IGNORE_PATTERNS` | `.git`, `node_modules`, `__pycache__`, `.venv`, `venv`, `dist`, `build`, `.tox`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `*.egg-info`, `.DS_Store`, `Thumbs.db` (and their sub-paths) | Patterns ignored by default. |

When `path` is `"."`, it resolves to the configured workspace. User-supplied `ignore` patterns are merged with the defaults.

```python
await list_dir("/project")
# Returns:
# /project/
# |-- src/
# |   └── main.py
# └── README.md
```

---

### glob

```python
async def glob(
    pattern: Annotated[str, "The glob pattern to match files against"],
    path: Annotated[str | None, "Directory to search in. If not specified, uses current working directory."] = None,
    structured: Annotated[bool, "If True, return JSON with count, truncated flag, and results array."] = False,
) -> str
```

Find files matching a glob pattern. Supports `*`, `**`, `?`, and `[abc]` character classes. Results are sorted by modification time, newest first.

| Constant | Value |
|----------|-------|
| `MAX_RESULTS` | `100` |

When `structured=True`, returns a JSON object: `{"count": N, "truncated": bool, "results": [...]}`.

```python
await glob("**/*.py")
# Returns one absolute path per line, newest first.

await glob("*.json", path="/project/config", structured=True)
# Returns JSON.
```

---

### grep

```python
async def grep(
    pattern: Annotated[str, "The regex pattern to search for in file contents"],
    path: Annotated[str | None, "Directory to search in. Defaults to current working directory."] = None,
    include: Annotated[str | None, 'File pattern to include (e.g., "*.py", "*.{ts,tsx}")'] = None,
    structured: Annotated[bool, "If True, return JSON with count, truncated flag, and grouped results."] = False,
) -> str
```

Search file contents using regex. Uses ripgrep (`rg`) if available, otherwise falls back to a pure-Python implementation. Results are grouped by file, sorted by file modification time (newest first).

| Constant | Value | Purpose |
|----------|-------|---------|
| `MAX_MATCHES` | `100` | Maximum total matches returned. |
| `MAX_LINE_LENGTH` | `2000` | Match lines are truncated at this length. |

Text output format:

```
Found N matches

/path/to/file.py:
 Line 42: <matching line text>
 Line 43: <matching line text>

/path/to/other.py:
 Line 10: <matching line text>
```

When `structured=True`, returns a JSON object: `{"count": N, "truncated": bool, "skipped_paths": bool, "files": {...}}`.

```python
await grep("def.*hello", path="/project/src", include="*.py")
await grep("TODO|FIXME")
```

---

### multiedit

```python
async def multiedit(
    file_path: Annotated[str, "The absolute path to the file to modify"],
    edits: Annotated[list[EditOp], "Array of edit operations to perform"],
) -> str
```

Perform multiple edits on a single file atomically. If any edit fails, all changes are rolled back and the file is left unchanged. Each `EditOp` uses the same matching strategies as `edit`.

`EditOp` is a Pydantic `BaseModel`:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `file_path` | `str` | (required) | Must match the top-level `file_path`. |
| `old_string` | `str` | (required) | The text to replace. |
| `new_string` | `str` | (required) | The replacement text. |
| `replace_all` | `bool` | `False` | Replace all occurrences. |

```python
from rawagents.tools.builtin.fs import EditOp

await multiedit(
    file_path="/project/main.py",
    edits=[
        EditOp(file_path="/project/main.py", old_string="foo", new_string="bar"),
        EditOp(file_path="/project/main.py", old_string="hello", new_string="world"),
    ],
)
# Returns: "MultiEdit applied successfully. (2 edits, 2 replacements)"
```

---

### apply_patch

```python
async def apply_patch(
    patch_text: Annotated[str, "The full patch text describing all changes"],
) -> str
```

Apply a Codex-style V4A patch bundle. The patch format supports four operations:

| Marker | Operation | Description |
|--------|-----------|-------------|
| `*** Add File: <path>` | Add | Creates a new file. Lines prefixed with `+`. |
| `*** Update File: <path>` | Update | Modifies an existing file using `@@` diff chunks with `-`/`+` prefixed lines. |
| `*** Move to: <path>` | Move | Used with Update to rename/move a file. |
| `*** Delete File: <path>` | Delete | Removes a file. |

The patch must be wrapped between `*** Begin Patch` and `*** End Patch` markers. Paths in the patch are resolved relative to the configured workspace.

```
*** Begin Patch
*** Add File: src/hello.py
+def hello():
+    print("hello")
*** Update File: src/main.py
@@ ... @@
-old_function()
+new_function()
*** Delete File: src/old.py
*** End Patch
```

```python
await apply_patch(patch_text)
# Returns: "Success. Updated the following files:\nA src/hello.py\nM src/main.py\nD src/old.py"
```

---

## Diagnostics Protocol

The fs module defines a pluggable diagnostics protocol for post-edit feedback. Agent loops can query a `DiagnosticsProvider` after edits to surface syntax errors, type errors, or linting warnings to the LLM.

### DiagnosticSeverity

An `Enum` with four levels matching LSP conventions:

| Value | String |
|-------|--------|
| `DiagnosticSeverity.ERROR` | `"error"` |
| `DiagnosticSeverity.WARNING` | `"warning"` |
| `DiagnosticSeverity.INFO` | `"info"` |
| `DiagnosticSeverity.HINT` | `"hint"` |

### Diagnostic

A `@dataclass` representing a single diagnostic message:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `file_path` | `str` | (required) | Absolute path to the file. |
| `line` | `int` | (required) | 1-based line number. |
| `column` | `int` | (required) | 1-based column number. |
| `severity` | `DiagnosticSeverity` | (required) | The severity level. |
| `message` | `str` | (required) | Human-readable diagnostic message. |
| `source` | `str` | (required) | The tool that produced this diagnostic (e.g., `"pyright"`, `"ruff"`). |
| `code` | `str` | `""` | Optional error/warning code (e.g., `"E501"`, `"F841"`). |

### DiagnosticsProvider

A `@runtime_checkable` `Protocol` with a single method:

```python
class DiagnosticsProvider(Protocol):
    async def get_diagnostics(self, file_path: str) -> list[Diagnostic]:
        ...
```

The tools themselves do not auto-invoke the provider. This is an agent-loop concern: after an edit completes, the loop can call `ctx.diagnostics_provider.get_diagnostics(path)` and feed the results back to the LLM.

```python
class RuffDiagnosticsProvider:
    async def get_diagnostics(self, file_path: str) -> list[Diagnostic]:
        import asyncio, json
        proc = await asyncio.create_subprocess_exec(
            "ruff", "check", "--output-format=json", file_path,
            stdout=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if not stdout:
            return []
        return [
            Diagnostic(
                file_path=file_path,
                line=item["location"]["row"],
                column=item["location"]["column"],
                severity=DiagnosticSeverity.WARNING,
                message=item["message"],
                source="ruff",
                code=item.get("code", ""),
            )
            for item in json.loads(stdout)
        ]

ctx = SecurityContext(
    workspace="/project",
    diagnostics_provider=RuffDiagnosticsProvider(),
)
set_security_context(ctx)
```

---

## Matching Strategies

The `edit` and `multiedit` tools use a chain of 6 replacement strategies, tried in order. The first strategy that finds a match wins. This reduces brittle failures from minor formatting differences in LLM-generated `old_string` values.

| Order | Class | Name | Description |
|-------|-------|------|-------------|
| 1 | `SimpleReplacer` | `"simple"` | Exact substring match. Fastest and most precise. |
| 2 | `LineTrimmedReplacer` | `"line_trimmed"` | Strips leading/trailing whitespace from each line before comparing. Handles trailing-space and indentation differences per line. |
| 3 | `BlockAnchorReplacer` | `"block_anchor"` | Uses the first and last lines as anchors, then verifies that at least 50% of middle lines match (stripped). Requires at least 2 lines. |
| 4 | `WhitespaceNormalizedReplacer` | `"whitespace_normalized"` | Collapses all whitespace sequences to single spaces before comparing. Tries window sizes within +/- 2 lines of the pattern length. |
| 5 | `IndentationFlexibleReplacer` | `"indentation_flexible"` | Compares stripped content and relative indentation structure, allowing the base indentation level to differ. |
| 6 | `FuzzyReplacer` | `"fuzzy"` | Uses `difflib.SequenceMatcher` to find the most similar contiguous block. Last resort. |

### FuzzyReplacer safety guards

The fuzzy strategy has extra protections against false positives:

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `threshold` | `0.7` | Minimum similarity ratio for patterns of 3+ lines. |
| `short_pattern_threshold` | `0.85` | Stricter threshold for patterns shorter than 3 lines. |
| `short_pattern_max_lines` | `3` | Patterns with fewer lines than this use the stricter threshold. |
| `max_file_lines_for_short_pattern` | `5000` | Files larger than this skip fuzzy matching entirely for short patterns (< 5 lines). |
| `min_pattern_lines` | `5` | Minimum pattern lines required for large-file fuzzy matching. |

The fuzzy matcher also allows window-size variation of +/- 20% to account for added or removed lines.

All strategies share a common `Replacer` base class with `find_matches(content, old_string) -> list[Match]` and `replace(content, old_string, new_string, replace_all) -> ReplacementResult`. The `find_and_replace()` function orchestrates the chain and returns the first successful `ReplacementResult`.
