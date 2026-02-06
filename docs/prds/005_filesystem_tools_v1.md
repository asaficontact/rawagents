# Product Requirements Document (PRD)
# RawAgents Built-in File System Tools

**Version:** 1.2
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
6. [Security Architecture](#6-security-architecture)
7. [Implementation Approach](#7-implementation-approach)
8. [Reference Implementations](#8-reference-implementations)
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
| **Architecture** | Separate tools (OpenCode style) | Mirrors OpenCode’s tool surface; composable and easy to test |
| **Tool names** | Match OpenCode exactly | Minimizes prompt drift when porting prompts/agents from OpenCode |
| **Edit Strategy** | OpenCode-style “replace with fallbacks” | Reduces brittle exact-match failures from LLM-generated `oldString` |
| **Search Backend** | ripgrep CLI (bundled or system `rg`) | Matches OpenCode’s behavior and `.gitignore` semantics |
| **Path Handling** | Absolute paths required | Claude Code/OpenCode require absolute paths for all file operations |
| **Patch Format** | `apply_patch` (Codex-style patch language) | Matches OpenCode and modern coding-agent ecosystems |
| **Security** | OpenCode-compatible boundary + external directory prompting | Matches OpenCode’s `external_directory` gating (with optional hardening) |

### 1.3 Tools Summary

| Tool | Purpose | Priority |
|------|---------|----------|
| `read` | Read file contents (text + PDF/images), line-numbered | P0 |
| `write` | Create or overwrite files | P0 |
| `edit` | Replace text in files (OpenCode fallback matching) | P0 |
| `list` | List directory tree (OpenCode style) | P0 |
| `glob` | Find files by glob (mtime-sorted) | P0 |
| `grep` | Search file contents using ripgrep | P0 |
| `multiedit` | Perform multiple edits atomically (all-or-nothing with rollback) | P1 |
| `apply_patch` | Apply Codex-style patch bundles (add/update/move/delete) | P2 |

**Out of scope for OpenCode parity (optional RawAgents extensions):**
- `insert`, `notebook_read`, `notebook_edit`, `read_image`, `read_pdf`, unified-diff `patch`

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
│  edit   │ Replace strings in files (OpenCode-style matching)      │
│  list   │ List directory tree (OpenCode style)                   │
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
│  multiedit     │ Multiple edits (atomic, all-or-nothing)        │
└─────────────────────────────────────────────────────────────────┘
```

### 4.3 Priority 2 (Nice to Have)

Advanced operations:

```
┌─────────────────────────────────────────────────────────────────┐
│                    PRIORITY 2: ADVANCED TOOLS                    │
├─────────────────────────────────────────────────────────────────┤
│  apply_patch │ Apply Codex-style patch bundles                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Tool Specifications

### 5.1 Read Tool

**Purpose:** Read file contents with line numbers, supporting offset/limit and OpenCode-style truncation.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_path` | str | ✅ | - | **Absolute path** to the file to read. Must be an absolute path, not relative. |
| `offset` | int | ❌ | 0 | Line number to start reading from (1-indexed in output, 0-indexed offset) |
| `limit` | int | ❌ | 2000 | Number of lines to read (defaults to 2000) |

**Output Format (cat -n style):**
```
     1	First line of content
     2	Second line of content
     3	Third line of content
```
- Right-aligned line numbers (6 character width)
- Tab character (`\t`) separator between number and content
- Matches `cat -n` output format used by Claude Code
- Lines longer than 2000 characters are truncated with `...`

**Behavior:**
- **Path resolution**:
  - If `filePath` is relative, resolve it against the project directory (OpenCode style).
- **External directory gating (OpenCode)**:
  - If the resolved path is outside the project/worktree boundary, request `external_directory` permission for the parent directory glob (see OpenCode `external-directory.ts`).
- **Permission**:
  - Requests `read` permission for the resolved file path.
- **Existence**:
  - If the file does not exist, error with up to 3 suggestions from the parent directory (case-insensitive substring match on the basename).
- **Binary detection**:
  - Reject common binary extensions (e.g., `.zip`, `.exe`, `.wasm`, `.pyc`) and also sample bytes (null-byte + non-printable ratio > 30%).
- **Media support (OpenCode)**:
  - If the file MIME type is `application/pdf` or `image/*` (excluding SVG), return an attachment (base64 data URL) and a short success message.
- **Truncation**:
  - Default `limit=2000` lines.
  - Additionally enforce a hard cap of **50 KiB** of output content; if exceeded, stop early and instruct the caller to use `offset` to continue.

**Example:**
```python
result = await read(
    filePath="src/main.py",
    offset=100,
    limit=50
)
# Returns lines 100-149 with line numbers
```

---

### 5.2 Write Tool

**Purpose:** Create or overwrite a file (OpenCode `write`).

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_path` | str | ✅ | - | **Absolute path** to the file to write. Must be an absolute path, not relative. |
| `content` | str | ✅ | - | Content to write |

**Behavior:**
- **Path resolution**: if `filePath` is relative, resolve against the project directory.
- **External directory gating (OpenCode)**: if outside project boundary, request `external_directory` permission.
- **Permission**: requests `edit` permission (OpenCode treats writes as edits) and includes a diff in metadata.
- **Existing file safety**: if the file exists, it must have been read in this session before writing (OpenCode-style “read-before-edit” tracking).
- **Overwrite semantics**: overwrites the entire file contents with `content`.
- **Output**: returns `"Wrote file successfully."` and may append LSP diagnostics if errors are detected.
- **LSP Diagnostics**: After writing, may include diagnostic output in the following format:
  ```
  <file_diagnostics path="/abs/path/to/file.py">
  L12: error: Undefined variable 'foo' [reportUndefinedVariable]
  L15: warning: Unused import 'os' [reportUnusedImport]
  </file_diagnostics>
  ```

**Example:**
```python
result = await write(
    filePath="src/new_file.py",
    content="def hello():\n    print('Hello, World!')\n"
)
# Returns: "Wrote file successfully."
```

---

### 5.3 Edit Tool

**Purpose:** Modify file contents by replacing `oldString` with `newString` (OpenCode `edit`).

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_path` | str | ✅ | - | **Absolute path** to the file to modify. Must be an absolute path, not relative. |
| `old_string` | str | ✅ | - | Text to replace |
| `new_string` | str | ✅ | - | Replacement text (must be different from `old_string`) |
| `replace_all` | bool | ❌ | False | Replace all occurrences of `old_string` |

**Behavior:**
- **Path resolution**: If `filePath` is relative, resolve it against the project directory.
- **External directory gating (OpenCode)**: If the resolved path is outside the project/worktree boundary, request `external_directory` permission.
- **Permission**: Requests `edit` permission and includes a diff in metadata.
- **Safety (OpenCode)**:
  - If `oldString != ""`, the file must exist and must have been read in this session (read-before-edit tracking).
- **Special case: create/overwrite**:
  - If `oldString == ""`, treat this as “write new content” (OpenCode behavior) and write `newString` to the file (creating if needed).
- **Replacement strategy (OpenCode)**:
  - The implementation attempts multiple matching strategies (in order) to reduce brittle failures:
    1. **SimpleReplacer**: Exact string match (fastest, most precise)
    2. **LineTrimmedReplacer**: Ignores leading/trailing whitespace per line
    3. **BlockAnchorReplacer**: Uses first/last line as anchors with similarity check for middle content
    4. **WhitespaceNormalizedReplacer**: Collapses all whitespace differences
    5. **IndentationFlexibleReplacer**: Allows different indentation levels while preserving relative structure
  - If `replaceAll=False`, replacement succeeds only when the final chosen match is unique.
- **Errors (OpenCode)**:
  - If no match is found: `"old_string not found in content"`.
  - If multiple matches are found (and not replacing all): `"Found multiple matches for old_string. Provide more surrounding lines in old_string to identify the correct match."`
- **LSP Diagnostics**: After editing, may include diagnostic output:
  ```
  <file_diagnostics path="/abs/path/to/file.py">
  L12: error: Syntax error [reportSyntaxError]
  </file_diagnostics>
  ```

**Example:**
```python
result = await edit(
    filePath="src/main.py",
    oldString="def hello():\n    print('Hello')",
    newString="def hello():\n    print('Hello, World!')"
)
# Returns: "Edit applied successfully."
```

---

### 5.4 List Tool

**Purpose:** List files under a directory (OpenCode `list`) with a directory-tree style output.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | str | ❌ | "." | Directory to list. **Absolute path recommended**; relative paths resolved against project directory. |
| `ignore` | list[str] | ❌ | [] | Glob patterns to ignore (OpenCode prepends `!` patterns internally) |

**Output Format (Unicode tree style):**
```
/absolute/search/path/
├── src/
│   └── rawagents/
│       └── __init__.py
└── tests/
    └── test_smoke.py
```
- Uses Unicode box-drawing characters: `├──`, `└──`, `│`
- `├──` for items with siblings below
- `└──` for last item in a directory
- `│` for vertical continuation lines

**Behavior:**
- **Path resolution**: resolve `path` against the project directory.
- **External directory gating (OpenCode)**: if outside project boundary, request `external_directory` permission for the directory.
- **Permission**: requests `list` permission for the resolved directory.
- **Enumeration backend**: uses ripgrep `--files` enumeration (OpenCode-style), which respects `.gitignore`-like behavior and excludes `.git/*` by default.
- **Ignore defaults**: apply a built-in ignore set (e.g., `node_modules/`, `.git/`, `dist/`, `.venv/`, etc.) and merge with user-provided `ignore`.
- **Limit**: stop after 100 files and mark the result as truncated.
- **Output structure**: build a tree of directories (directories first) and list files under each directory; output begins with the absolute search path followed by the tree.

**Example:**
```python
result = await list(
    path=".",
    ignore=["*.pyc", "__pycache__/*"],
)
```

---

### 5.5 Glob Tool

**Purpose:** Find files matching a glob pattern (OpenCode `glob`).

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `pattern` | str | ✅ | - | The glob pattern to match files against |
| `path` | str | ❌ | (omit) | The directory to search in. If not specified, the current working directory will be used. IMPORTANT: Omit this field to use the default directory. DO NOT enter `"undefined"` or `"null"`—simply omit it. Must be a valid directory path if provided. |

**Output Format (OpenCode):**
- If matches are found: newline-separated list of **absolute file paths**, sorted by **mtime (newest first)**.
- If no matches are found: the literal string `No files found`.
- If results are truncated: append a blank line, then:
  - `(Results are truncated. Consider using a more specific path or pattern.)`

**Behavior (OpenCode):**
- **Permission**: requests `glob` permission with `patterns=[pattern]` (and `always=["*"]`).
- **Path resolution**:
  - `search = path` if provided, else the project working directory.
  - If `search` is relative, resolve against the project directory.
- **External directory gating**: if `search` is outside the project boundary, request `external_directory` permission for the directory (`kind="directory"`).
- **Enumeration backend**: uses ripgrep file enumeration with `glob=[pattern]` rooted at `cwd=search`.
- **Limit**: returns at most 100 files; marks results as truncated if more are found.
- **Sorting**: stats each matched file to read `mtime` (missing stats default to 0), then sorts descending by `mtime`.
- **Return metadata**: `{ count: <number of returned files>, truncated: <bool> }`.
- **Return title**: relative path of the search directory to the worktree root.

**Example (OpenCode):**
```python
result = await glob(
    pattern="**/*.py",
    # path is optional; omit it to use the default working directory
)
```

---

### 5.6 Grep Tool

**Purpose:** Search file contents using ripgrep (OpenCode `grep`).

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `pattern` | str | ✅ | - | The regex pattern to search for in file contents |
| `path` | str | ❌ | (omit) | The directory to search in. Defaults to the current working directory. |
| `include` | str | ❌ | (omit) | File pattern to include in the search (e.g. `"*.js"`, `"*.{ts,tsx}"`) - maps to ripgrep `--glob` |

**Note on Claude Code parameters**: Claude Code's Grep tool includes additional parameters (`type`, `output_mode`, context options `-A/-B/-C`, `multiline`, `head_limit`, `offset`) that are Claude Code-specific and not part of OpenCode. For OpenCode parity, implement the core parameters above. Advanced parameters may be added as optional RawAgents extensions.

**Example:**
```python
result = await grep(
    pattern="def.*hello",
    path="src",
    include="*.py",
)
```

**Output Format (OpenCode):**
```
Found N matches

/abs/path/to/file.py:
 Line 42: <matching line text>
 Line 43: <matching line text>

(Results are truncated. Consider using a more specific path or pattern.)

(Some paths were inaccessible and skipped)
```
- Matches are grouped by file (by path) in the order they appear after sorting.
- Individual match line text is truncated to 2000 characters and suffixed with `...`.

**Behavior (OpenCode):**
- **Validation**: if `pattern` is empty, throws `pattern is required`.
- **Permission**: requests `grep` permission with `patterns=[pattern]` (and `always=["*"]`).
- **Path resolution**:
  - `searchPath = path` if provided, else the project working directory.
  - If `searchPath` is relative, resolve against the project directory.
- **External directory gating**: if `searchPath` is outside the project boundary, request `external_directory` permission for the directory (`kind="directory"`).
- **Ripgrep invocation**:
  - Runs ripgrep with flags `-nH --hidden --no-messages --field-match-separator=| --regexp <pattern>`.
  - If `include` is set, adds `--glob <include>`.
  - Searches under `searchPath`.
  - **Note**: The `--follow` flag (symlink following) was removed from OpenCode for security reasons. Symlinks are not followed during grep.
- **Exit code handling**:
  - `0`: matches found.
  - `1`: no matches → return `No files found`.
  - `2`: errors (broken symlinks, inaccessible paths, etc.) → still return matches if any output was produced; otherwise return `No files found`.
  - Any other non-zero exit code: raise `ripgrep failed: <stderr>`.
- **Parsing**: consumes ripgrep output as `filePath|lineNum|lineText` (using `|` as a field separator), stats each `filePath` to get `mtime`, and skips entries it cannot stat.
- **Sorting**: sorts matches by file `mtime` descending (newest files first). (Line ordering within a file is not guaranteed after sorting.)
- **Limit**: returns at most 100 matches; if more are found, sets `truncated=true` and appends the truncation notice.
- **Error note**: if exit code was `2`, appends `(Some paths were inaccessible and skipped)`.
- **Return metadata**: `{ matches: <number of returned matches>, truncated: <bool> }`.
- **Return title**: the pattern string.

---

### 5.7 Insert Tool (P1)

**Status:** Out of scope for OpenCode parity.

OpenCode does not ship a dedicated `insert` tool in `packages/opencode/src/tool/`. For OpenCode parity, inserts should be done via `edit` or `apply_patch`.

---

### 5.8 MultiEdit Tool (P1)

**Purpose:** Perform multiple edits sequentially on one file (OpenCode `multiedit`).

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_path` | str | ✅ | - | **Absolute path** to the file to modify. Must be an absolute path, not relative. |
| `edits` | list[EditOp] | ✅ | - | Array of edit operations to perform on the file |

**EditOp object (OpenCode):**
```python
{
    "file_path": str,      # The absolute path to the file to modify (must match the top-level file_path)
    "old_string": str,     # The text to replace
    "new_string": str,     # The text to replace it with (must be different from old_string)
    "replace_all": bool,   # Optional; default false
}
```

**Behavior (OpenCode):**
- Initializes the OpenCode `edit` tool and delegates each operation to it, in order.
- For each edit in `edits`, calls `edit` with:
  - `file_path`: the **top-level** `file_path`
  - `old_string`, `new_string`, `replace_all`: taken from the edit entry
- **ATOMIC (all-or-nothing)**: All edits are validated and applied together. If any edit fails, **all changes are rolled back** and the file is restored to its original state. This prevents partial modifications that could leave the file in an inconsistent state.
- **Rollback mechanism**: The original file content is preserved before any edits. On failure, the original content is restored.
- **Permissions/security**: permission prompts and `external_directory` gating are performed before the batch operation.
- Returns the output from the **last** delegated `edit` on success.
- Returns metadata containing a `results` array of each delegated edit's `metadata`.
- Return title is the path of `file_path` relative to the worktree root.

**Example:**
```python
result = await multiedit(
    file_path="/project/src/main.py",
    edits=[
        {"file_path": "/project/src/main.py", "old_string": "foo", "new_string": "bar"},
        {"file_path": "/project/src/main.py", "old_string": "hello", "new_string": "world", "replace_all": True},
    ]
)
# If either edit fails, file is rolled back to original state
```

---

### 5.9 NotebookRead Tool (P1)

**Status:** Out of scope for OpenCode parity.

OpenCode does not include notebook read/edit tools in `packages/opencode/src/tool/`. For OpenCode parity, Jupyter notebooks should be treated as files and edited via `read`/`edit`/`apply_patch` as appropriate. Notebook-aware tools may be added later as optional RawAgents extensions.

---

### 5.10 NotebookEdit Tool (P1)

**Status:** Out of scope for OpenCode parity.

OpenCode does not include notebook read/edit tools in `packages/opencode/src/tool/`. For OpenCode parity, notebook edits should be performed by editing the underlying JSON with `edit`/`apply_patch` (or by adding notebook-specific tools as optional RawAgents extensions later).

---

### 5.11 ApplyPatch Tool (P2)

**Purpose:** Apply a Codex-style patch bundle that can add/update/move/delete files (OpenCode `apply_patch`).

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `patch_text` | str | ✅ | - | The full patch text that describes all changes to be made |

**Patch Format (OpenCode / Codex-style):**
- The patch text is a single bundle starting with `*** Begin Patch` and ending with `*** End Patch`.
- Each file operation is expressed as a hunk with one of:
  - `*** Add File: <path>`
  - `*** Update File: <path>` (optionally includes a move directive such as `*** Move to: <new-path>`)
  - `*** Delete File: <path>`
- Updates include `@@` chunk markers; the parser verifies and derives new file content from the chunks.

**Behavior (OpenCode):**
- **Validation**:
  - If `patch_text` is empty, throws `patch_text is required`.
  - Parses `patch_text`; parse failures raise `apply_patch verification failed: <error>`.
  - Rejects empty patch bundles (exact `*** Begin Patch\n*** End Patch`) with `patch rejected: empty patch`.
  - If parsing yields no hunks, raises `apply_patch verification failed: no hunks found`.
- **Path resolution**: each hunk path is resolved against the project directory (workspace working directory).
- **External directory gating**: for every affected path (including `movePath`), requests `external_directory` permission if the target is outside the project boundary.
- **Per-hunk verification**:
  - **add**: normalizes new file contents to end with a trailing newline.
  - **update**: requires the target file to exist and not be a directory; otherwise raises `apply_patch verification failed: Failed to read file to update: <filePath>`. Derives new contents from the parsed chunks (verification failures raise `apply_patch verification failed: <error>`).
  - **move**: represented as an update hunk with a `move_path` (new path); writes the new file then deletes the old.
  - **delete**: reads the file content and then deletes it (read failures raise `apply_patch verification failed: <error>`).
- **Permission**: requests `edit` permission for the set of affected relative paths (relative to the worktree root). The permission metadata includes:
  - a combined `diff` of all changes
  - a per-file `files` structure including before/after, diff, additions, deletions, and move info
- **Apply**:
  - Creates parent directories for added/moved files (`mkdir -p` equivalent).
  - Writes updated/new file contents with UTF-8 encoding.
  - Deletes files for `delete` and the source file for `move`.
  - Notifies the file watcher/LSP of changes (implementation detail) and collects diagnostics.
- **Output**:
  - Starts with `Success. Updated the following files:` followed by one line per change:
    - `A <relativePath>` for add
    - `M <relativePath>` for update/move (relative path of the final target)
    - `D <relativePath>` for delete
  - If LSP errors exist for changed files, appends a per-file section:
    - `LSP errors detected in <relativePath>, please fix:` followed by pretty-printed diagnostics.
- **Return metadata**: includes `diff`, `files` (per-file before/after/diff/additions/deletions), and `diagnostics`.

**Example:**
```python
result = await apply_patch(
    patchText=\"\"\"*** Begin Patch
*** Add File: src/hello.py
+def hello():
+    print("hello")
*** End Patch\"\"\"
)
```

---

## 6. Security Architecture

The Security Module is a **critical component** that sits between the tools and the filesystem, ensuring all file operations are safe and authorized. This section provides a comprehensive specification of the security architecture.

### 6.1 Overview: Three Layers of Security

```
┌─────────────────────────────────────────────────────────────────┐
│                     USER/AGENT REQUEST                           │
│                  "Read /project/../../../etc/passwd"             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 1: PATH VALIDATION (Security Module)                      │
│  ─────────────────────────────────────────────────────────────  │
│  1. Resolve symlinks → get REAL path                            │
│  2. Normalize path → remove ../ traversals                       │
│  3. Check if real path is within workspace                       │
│  4. Check against denied patterns (.env, credentials)            │
│  5. REJECT if outside boundaries or matches denied pattern       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 2: PERMISSION CHECK (Permission System - Optional)        │
│  ─────────────────────────────────────────────────────────────  │
│  1. Check deny rules → BLOCK if matched                         │
│  2. Check allow rules → PERMIT if matched                        │
│  3. Check ask rules → PROMPT USER if matched                     │
│  4. Default → ASK for sensitive operations                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 3: OS-LEVEL SANDBOX (Optional, User-Provided)             │
│  ─────────────────────────────────────────────────────────────  │
│  • Linux: bubblewrap container                                   │
│  • macOS: seatbelt sandbox                                       │
│  • Docker: Container isolation                                   │
│  • Enforced at kernel level (last line of defense)              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FILE OPERATION EXECUTED                      │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 How Claude Code and OpenCode Handle Security

#### Claude Code's Approach (Production-Grade)

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Filesystem Isolation** | bubblewrap (Linux), seatbelt (macOS) | OS-level restriction to specific directories |
| **Network Isolation** | External proxy server | Validates all outgoing connections |
| **Permission System** | allow/deny/ask rules in settings.json | User-configurable access control |
| **Git Proxy** | Custom proxy with scoped credentials | Validates git operations before routing |

**Key Result:** Claude Code's sandbox reduces permission prompts by **84%** because safe operations are auto-allowed within the sandbox boundary.

**Configuration Example (`.claude/settings.json`):**
```json
{
  "permissions": {
    "allow": [
      "Read",
      "Glob",
      "Grep",
      "Bash(git status)",
      "Bash(npm test)"
    ],
    "deny": [
      "Bash(rm -rf *)",
      "Write(*.env)"
    ],
    "ask": [
      "Write",
      "Edit",
      "Bash"
    ]
  }
}
```

#### OpenCode's Approach (Has Known Vulnerability)

OpenCode has a **symlink escape vulnerability** that allows reading files outside the workspace:

```typescript
// OpenCode's VULNERABLE pattern
function containsPath(basePath: string, targetPath: string): boolean {
    // This checks the STRING path, not the REAL path
    return targetPath.startsWith(basePath);
}

// Attack Example:
// 1. Create symlink: ln -s /etc/passwd ./project/leak
// 2. Request: read("./project/leak")
// 3. containsPath("./project", "./project/leak") → TRUE ✅
// 4. fs.readFile("./project/leak") → follows symlink → reads /etc/passwd 🚨
```

**Lesson Learned:** Always resolve symlinks BEFORE validating paths.

### 6.3 Layer 1: SecurityContext (Path Validation)

The `SecurityContext` class is the core security primitive that validates all file paths.

**File:** `rawagents/tools/builtin/fs/_security.py`

```python
"""Security module for file system tools.

This module provides path validation and workspace boundary enforcement
to prevent path traversal attacks and unauthorized file access.

CRITICAL: All file operations MUST use this module for path validation.
"""

import os
import fnmatch
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field


class WorkspaceSecurityError(PermissionError):
    """Raised when a path access violates security constraints."""

    def __init__(self, message: str, path: str, resolved_path: Optional[str] = None):
        super().__init__(message)
        self.path = path
        self.resolved_path = resolved_path


@dataclass
class SecurityContext:
    """Security context for file system operations.

    This class enforces:
    1. Workspace boundary restrictions
    2. Symlink attack prevention
    3. Sensitive file pattern blocking

    Example:
        >>> ctx = SecurityContext(workspace="/home/user/project")
        >>> ctx.validate_path("/home/user/project/src/main.py")
        PosixPath('/home/user/project/src/main.py')

        >>> ctx.validate_path("/etc/passwd")
        WorkspaceSecurityError: Access denied: /etc/passwd is outside workspace

        >>> # Symlink attack prevention
        >>> # If ./project/leak -> /etc/passwd
        >>> ctx.validate_path("./project/leak")
        WorkspaceSecurityError: Access denied: ./project/leak resolves to
        /etc/passwd which is outside workspace /home/user/project
    """

    workspace: Optional[str] = None
    """Root directory for allowed file operations. If None, no restriction."""

    allow_symlinks_outside: bool = False
    """Whether to allow symlinks that point outside the workspace."""

    denied_patterns: list[str] = field(default_factory=lambda: [
        "*.env",
        "*.env.*",
        "*/.env",
        "*/.env.*",
        "*credentials*",
        "*secret*",
        "*.pem",
        "*.key",
        "*id_rsa*",
        "*id_ed25519*",
        "*.p12",
        "*.pfx",
        "*password*",
        "*token*",
    ])
    """Glob patterns for files that should never be accessed."""

    allowed_patterns: list[str] = field(default_factory=list)
    """Glob patterns that override denied_patterns (allowlist)."""

    max_file_size: int = 10 * 1024 * 1024  # 10MB
    """Maximum file size in bytes for read/write operations."""

    max_path_depth: int = 50
    """Maximum directory depth to prevent deeply nested attacks."""

    _resolved_workspace: Optional[Path] = field(default=None, init=False, repr=False)

    def __post_init__(self):
        """Resolve workspace path on initialization."""
        if self.workspace:
            self._resolved_workspace = Path(self.workspace).resolve()

    def validate_path(self, path: str, check_exists: bool = True) -> Path:
        """Validate a file path against security constraints.

        This method performs the following checks in order:
        1. Resolve ALL symlinks to get the canonical path
        2. Check path depth limit
        3. Check against denied patterns
        4. Verify path is within workspace boundary

        Args:
            path: The path to validate (can be relative or absolute)
            check_exists: If True, use strict resolution (file must exist).
                         If False, resolve parent for new files.

        Returns:
            The resolved, validated Path object.

        Raises:
            WorkspaceSecurityError: If the path violates any security constraint.
            FileNotFoundError: If check_exists=True and file doesn't exist.
        """
        original_path = path

        # Step 1: Resolve symlinks to get REAL path
        # This is CRITICAL for security - we must know the actual file location
        try:
            if check_exists:
                resolved = Path(path).resolve(strict=True)
            else:
                # For new files, resolve the parent directory
                resolved = Path(path).resolve(strict=False)
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {path}")
        except RuntimeError as e:
            # Circular symlink or too many levels
            raise WorkspaceSecurityError(
                f"Unable to resolve path (possible circular symlink): {path}",
                path=original_path
            )

        # Step 2: Check path depth
        if len(resolved.parts) > self.max_path_depth:
            raise WorkspaceSecurityError(
                f"Path exceeds maximum depth ({self.max_path_depth}): {path}",
                path=original_path,
                resolved_path=str(resolved)
            )

        # Step 3: Check denied patterns (unless in allowlist)
        resolved_str = str(resolved)

        # Check if explicitly allowed
        is_allowed = any(
            fnmatch.fnmatch(resolved_str, pattern) or
            fnmatch.fnmatch(resolved.name, pattern)
            for pattern in self.allowed_patterns
        )

        if not is_allowed:
            for pattern in self.denied_patterns:
                if fnmatch.fnmatch(resolved_str, pattern) or \
                   fnmatch.fnmatch(resolved.name, pattern):
                    raise WorkspaceSecurityError(
                        f"Access denied: {path} matches blocked pattern '{pattern}'",
                        path=original_path,
                        resolved_path=str(resolved)
                    )

        # Step 4: Check workspace boundary
        if self._resolved_workspace is not None:
            try:
                resolved.relative_to(self._resolved_workspace)
            except ValueError:
                raise WorkspaceSecurityError(
                    f"Access denied: {path} (resolves to {resolved}) "
                    f"is outside workspace {self._resolved_workspace}",
                    path=original_path,
                    resolved_path=str(resolved)
                )

        return resolved

    def validate_file_size(self, path: Path) -> None:
        """Validate file size is within limits.

        Args:
            path: Resolved path to check.

        Raises:
            WorkspaceSecurityError: If file exceeds size limit.
        """
        try:
            size = path.stat().st_size
            if size > self.max_file_size:
                raise WorkspaceSecurityError(
                    f"File too large: {path} is {size:,} bytes "
                    f"(max: {self.max_file_size:,} bytes)",
                    path=str(path)
                )
        except FileNotFoundError:
            pass  # File doesn't exist yet, skip size check

    def is_binary_file(self, path: Path, sample_size: int = 8192) -> bool:
        """Check if a file appears to be binary.

        Args:
            path: Path to check.
            sample_size: Number of bytes to sample.

        Returns:
            True if file appears to be binary.
        """
        try:
            with open(path, 'rb') as f:
                chunk = f.read(sample_size)
                # Check for null bytes (common in binary files)
                if b'\x00' in chunk:
                    return True
                # Check for high ratio of non-text bytes
                text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} |
                                       set(range(0x20, 0x100)) - {0x7f})
                non_text = sum(1 for b in chunk if b not in text_chars)
                return non_text / len(chunk) > 0.30 if chunk else False
        except (IOError, OSError):
            return False


# Global security context (thread-local in production)
_security_context: Optional[SecurityContext] = None


def set_security_context(ctx: SecurityContext) -> None:
    """Set the global security context.

    Args:
        ctx: The security context to use for all file operations.
    """
    global _security_context
    _security_context = ctx


def get_security_context() -> SecurityContext:
    """Get the current security context.

    Returns:
        The current security context, or a permissive default if none set.
    """
    global _security_context
    if _security_context is None:
        _security_context = SecurityContext()  # Permissive default
    return _security_context


def validate_path(path: str, check_exists: bool = True) -> Path:
    """Convenience function to validate a path using the global context.

    Args:
        path: The path to validate.
        check_exists: Whether the file must exist.

    Returns:
        The resolved, validated Path.
    """
    return get_security_context().validate_path(path, check_exists)
```

### 6.4 Layer 2: Permission System (Optional)

The Permission System provides user-configurable access control, similar to Claude Code's allow/deny/ask rules.

**File:** `rawagents/tools/permissions.py`

```python
"""Permission system for tool execution.

This module provides a configurable permission system that allows
users to define rules for what operations agents can perform.

Evaluation order:
1. Deny rules (always block)
2. Allow rules (always permit)
3. Ask rules (prompt user)
4. Default action
"""

from enum import Enum
from typing import Callable, Optional, Any
from dataclasses import dataclass, field
import fnmatch
import re


class PermissionAction(Enum):
    """Actions that can be taken for a permission check."""
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


@dataclass
class PermissionRule:
    """A single permission rule.

    Patterns support:
    - Tool name: "Read", "Write", "Bash"
    - Tool with args: "Bash(git *)", "Write(*.py)"
    - Wildcards: "*" matches any characters

    Examples:
        - "read" → matches all read operations
        - "Bash(git *)" → matches bash commands starting with "git "
        - "write(*.env)" → matches writing to .env files
    """
    pattern: str
    action: PermissionAction

    def matches(self, tool_name: str, args: dict) -> bool:
        """Check if this rule matches the given tool invocation."""
        # Parse pattern
        if "(" in self.pattern:
            # Pattern with args: "Bash(git *)"
            match = re.match(r"(\w+)\((.+)\)", self.pattern)
            if not match:
                return False
            pattern_tool, pattern_arg = match.groups()

            if not fnmatch.fnmatch(tool_name, pattern_tool):
                return False

            # Check args based on tool type
            if tool_name == "Bash" and "command" in args:
                return fnmatch.fnmatch(args["command"], pattern_arg)
            elif tool_name in ("read", "write", "edit", "apply_patch") and "filePath" in args:
                return fnmatch.fnmatch(args["filePath"], pattern_arg)

            return False
        else:
            # Simple tool name pattern
            return fnmatch.fnmatch(tool_name, self.pattern)


@dataclass
class PermissionConfig:
    """Configuration for the permission system.

    Example:
        >>> config = PermissionConfig(
        ...     allow=["read", "glob", "grep", "Bash(git status)"],
        ...     deny=["Bash(rm -rf *)", "write(*.env)"],
        ...     ask=["write", "edit", "Bash"],
        ...     default=PermissionAction.ASK
        ... )
    """
    allow: list[str] = field(default_factory=list)
    deny: list[str] = field(default_factory=list)
    ask: list[str] = field(default_factory=list)
    default: PermissionAction = PermissionAction.ASK

    def to_rules(self) -> list[PermissionRule]:
        """Convert config to ordered list of rules."""
        rules = []
        # Deny rules first (highest priority)
        for pattern in self.deny:
            rules.append(PermissionRule(pattern, PermissionAction.DENY))
        # Then allow rules
        for pattern in self.allow:
            rules.append(PermissionRule(pattern, PermissionAction.ALLOW))
        # Then ask rules
        for pattern in self.ask:
            rules.append(PermissionRule(pattern, PermissionAction.ASK))
        return rules


class PermissionManager:
    """Manages permission checks for tool execution.

    Example:
        >>> async def ask_user(tool: str, args: dict) -> bool:
        ...     response = input(f"Allow {tool}? [y/n] ")
        ...     return response.lower() == "y"

        >>> config = PermissionConfig(allow=["read"], deny=["Bash(rm *)"])
        >>> manager = PermissionManager(config, ask_callback=ask_user)

        >>> await manager.check_permission("read", {"filePath": "/foo.py"})
        True  # Allowed by rule

        >>> await manager.check_permission("Bash", {"command": "rm -rf /"})
        False  # Denied by rule
    """

    def __init__(
        self,
        config: PermissionConfig,
        ask_callback: Optional[Callable[[str, dict], Any]] = None,
    ):
        """Initialize the permission manager.

        Args:
            config: Permission configuration.
            ask_callback: Async function to call when asking user for permission.
                         Should return True to allow, False to deny.
        """
        self.config = config
        self.rules = config.to_rules()
        self.ask_callback = ask_callback

    async def check_permission(self, tool_name: str, args: dict) -> bool:
        """Check if a tool execution is allowed.

        Args:
            tool_name: Name of the tool being invoked.
            args: Arguments passed to the tool.

        Returns:
            True if execution is allowed, False otherwise.
        """
        # Check rules in order
        for rule in self.rules:
            if rule.matches(tool_name, args):
                if rule.action == PermissionAction.DENY:
                    return False
                elif rule.action == PermissionAction.ALLOW:
                    return True
                elif rule.action == PermissionAction.ASK:
                    if self.ask_callback:
                        return await self.ask_callback(tool_name, args)
                    return False  # Deny if no callback

        # Default action
        if self.config.default == PermissionAction.ALLOW:
            return True
        elif self.config.default == PermissionAction.DENY:
            return False
        else:  # ASK
            if self.ask_callback:
                return await self.ask_callback(tool_name, args)
            return False
```

### 6.5 Layer 3: OS-Level Sandbox (User-Provided)

RawAgents does not implement OS-level sandboxing directly but provides guidance for users who want this additional security layer.

#### Linux: bubblewrap

```bash
# Run agent in isolated environment
bwrap \
    --ro-bind /usr /usr \
    --ro-bind /lib /lib \
    --ro-bind /lib64 /lib64 \
    --bind /home/user/project /workspace \
    --unshare-net \
    --die-with-parent \
    python -m rawagents.agent
```

#### macOS: sandbox-exec (seatbelt)

```bash
# Create sandbox profile
cat > agent.sb << 'EOF'
(version 1)
(deny default)
(allow file-read* (subpath "/home/user/project"))
(allow file-write* (subpath "/home/user/project"))
(deny network*)
EOF

# Run with sandbox
sandbox-exec -f agent.sb python -m rawagents.agent
```

#### Docker

```dockerfile
# Dockerfile.agent
FROM python:3.11-slim
WORKDIR /workspace
COPY requirements.txt .
RUN pip install -r requirements.txt
# Run as non-root user
USER 1000:1000
```

```bash
# Run with limited permissions
docker run --rm \
    -v /home/user/project:/workspace:rw \
    --network none \
    --read-only \
    --tmpfs /tmp \
    agent-image python -m rawagents.agent
```

### 6.6 Security Testing Requirements

All file system tools MUST pass these security tests:

**File:** `tests/tools/builtin/fs/test_security.py`

```python
"""Security tests for file system tools.

These tests verify that the security module properly prevents:
1. Path traversal attacks via ../
2. Symlink escape attacks
3. Access to sensitive files
4. Operations outside workspace
"""

import pytest
import os
import tempfile
from pathlib import Path
from rawagents.tools.builtin.fs._security import (
    SecurityContext,
    WorkspaceSecurityError,
    validate_path,
    set_security_context,
)


class TestPathTraversal:
    """Test protection against ../ path traversal."""

    def test_blocks_parent_directory_escape(self, temp_workspace):
        ctx = SecurityContext(workspace=str(temp_workspace))
        set_security_context(ctx)

        with pytest.raises(WorkspaceSecurityError) as exc:
            validate_path(str(temp_workspace / ".." / "etc" / "passwd"))

        assert "outside workspace" in str(exc.value)

    def test_blocks_absolute_path_outside(self, temp_workspace):
        ctx = SecurityContext(workspace=str(temp_workspace))
        set_security_context(ctx)

        with pytest.raises(WorkspaceSecurityError):
            validate_path("/etc/passwd")


class TestSymlinkEscape:
    """Test protection against symlink attacks."""

    def test_blocks_symlink_pointing_outside(self, temp_workspace):
        """Symlinks pointing outside workspace should be blocked."""
        ctx = SecurityContext(workspace=str(temp_workspace))
        set_security_context(ctx)

        # Create symlink inside workspace pointing outside
        symlink = temp_workspace / "evil_link"
        symlink.symlink_to("/etc/passwd")

        with pytest.raises(WorkspaceSecurityError) as exc:
            validate_path(str(symlink))

        assert "outside workspace" in str(exc.value)
        assert "/etc/passwd" in str(exc.value)  # Shows resolved path

    def test_blocks_chained_symlinks(self, temp_workspace):
        """Chained symlinks that eventually escape should be blocked."""
        ctx = SecurityContext(workspace=str(temp_workspace))
        set_security_context(ctx)

        # Create chain: link1 -> link2 -> /etc/passwd
        with tempfile.TemporaryDirectory() as outside:
            outside_link = Path(outside) / "link2"
            outside_link.symlink_to("/etc/passwd")

            inside_link = temp_workspace / "link1"
            inside_link.symlink_to(outside_link)

            with pytest.raises(WorkspaceSecurityError):
                validate_path(str(inside_link))


class TestDeniedPatterns:
    """Test protection of sensitive files."""

    @pytest.mark.parametrize("filename", [
        ".env",
        ".env.local",
        "config/.env",
        "credentials.json",
        "secrets.yaml",
        "id_rsa",
        "server.key",
        "password.txt",
    ])
    def test_blocks_sensitive_files(self, temp_workspace, filename):
        ctx = SecurityContext(workspace=str(temp_workspace))
        set_security_context(ctx)

        # Create the sensitive file
        sensitive_file = temp_workspace / filename
        sensitive_file.parent.mkdir(parents=True, exist_ok=True)
        sensitive_file.write_text("secret")

        with pytest.raises(WorkspaceSecurityError) as exc:
            validate_path(str(sensitive_file))

        assert "blocked pattern" in str(exc.value)

    def test_allowlist_overrides_denylist(self, temp_workspace):
        """Explicitly allowed patterns should override denied patterns."""
        ctx = SecurityContext(
            workspace=str(temp_workspace),
            denied_patterns=["*.env"],
            allowed_patterns=["*.env.example"]
        )
        set_security_context(ctx)

        example_file = temp_workspace / ".env.example"
        example_file.write_text("# Example config")

        # Should NOT raise
        result = validate_path(str(example_file))
        assert result == example_file.resolve()


class TestResourceLimits:
    """Test resource limit enforcement."""

    def test_blocks_deeply_nested_paths(self, temp_workspace):
        ctx = SecurityContext(workspace=str(temp_workspace), max_path_depth=10)
        set_security_context(ctx)

        # Create deeply nested path
        deep_path = temp_workspace
        for i in range(20):
            deep_path = deep_path / f"dir{i}"
        deep_path.mkdir(parents=True, exist_ok=True)
        test_file = deep_path / "file.txt"
        test_file.write_text("test")

        with pytest.raises(WorkspaceSecurityError) as exc:
            validate_path(str(test_file))

        assert "exceeds maximum depth" in str(exc.value)

    def test_blocks_large_files(self, temp_workspace):
        ctx = SecurityContext(
            workspace=str(temp_workspace),
            max_file_size=1024  # 1KB limit
        )
        set_security_context(ctx)

        large_file = temp_workspace / "large.txt"
        large_file.write_text("x" * 2048)  # 2KB

        resolved = ctx.validate_path(str(large_file))

        with pytest.raises(WorkspaceSecurityError) as exc:
            ctx.validate_file_size(resolved)

        assert "too large" in str(exc.value)


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        # Create some test files
        (workspace / "test.py").write_text("print('hello')")
        (workspace / "subdir").mkdir()
        (workspace / "subdir" / "nested.py").write_text("# nested")
        yield workspace
```

### 6.7 Security References

| Resource | URL | Description |
|----------|-----|-------------|
| **Claude Code Sandboxing** | [anthropic.com/engineering/claude-code-sandboxing](https://www.anthropic.com/engineering/claude-code-sandboxing) | Official sandboxing architecture |
| **OpenCode Symlink Vulnerability** | [dev.to/pachilo/reading-outside-the-lines](https://dev.to/pachilo/reading-outside-the-lines-symlink-escape-in-opencodes-file-api-5f81) | Detailed vulnerability analysis |
| **MCP Filesystem Advisory** | [GHSA-q66q-fx2p-7w4m](https://github.com/modelcontextprotocol/servers/security/advisories/GHSA-q66q-fx2p-7w4m) | Similar vulnerability in MCP |
| **Gemini CLI Issue** | [github.com/google-gemini/gemini-cli/issues/1121](https://github.com/google-gemini/gemini-cli/issues/1121) | Same pattern in Gemini CLI |
| **bubblewrap** | [github.com/containers/bubblewrap](https://github.com/containers/bubblewrap) | Linux sandboxing tool |
| **CodeJail** | [github.com/openedx/codejail](https://github.com/openedx/codejail) | Python code sandboxing |

---

## 7. Implementation Approach

### 7.1 Core Module Structure

```python
# rawagents/tools/builtin/fs/__init__.py

from rawagents.tools.builtin.fs.read import read
from rawagents.tools.builtin.fs.write import write
from rawagents.tools.builtin.fs.edit import edit
from rawagents.tools.builtin.fs.list import list
from rawagents.tools.builtin.fs.glob import glob
from rawagents.tools.builtin.fs.grep import grep
from rawagents.tools.builtin.fs.multiedit import multiedit
from rawagents.tools.builtin.fs.apply_patch import apply_patch

__all__ = ["read", "write", "edit", "list", "glob", "grep", "multiedit", "apply_patch"]
```

### 7.2 Tool Implementation Pattern

Each tool MUST follow this pattern, integrating with the security module:

```python
# rawagents/tools/builtin/fs/read.py

from typing import Annotated
from rawagents.tools import tool
from rawagents.tools.builtin.fs._security import (
    validate_path,
    get_security_context,
    WorkspaceSecurityError,
)


@tool
async def read(
    filePath: Annotated[str, "The absolute or relative path to the file to read"],
    offset: Annotated[int, "The line number to start reading from (0-indexed)"] = 0,
    limit: Annotated[int, "The maximum number of lines to read"] = 2000,
) -> str:
    """Read file contents with line numbers.

    Returns the file content with line numbers in cat -n format:
    `     1\tline contents`
    Lines are numbered starting from 1 (displayed), even when offset is 0-indexed.

    Security:
        - Path is validated against workspace boundaries
        - Symlinks are resolved before validation
        - Sensitive files (.env, credentials) are blocked

    Example:
        >>> await read("/project/main.py", offset=0, limit=50)
        "     1\\tdef main():\\n     2\\t    print('Hello')\\n"
    """
    # SECURITY: Validate path first
    try:
        resolved_path = validate_path(filePath, check_exists=True)
    except WorkspaceSecurityError as e:
        return f"Error: {e}"
    except FileNotFoundError:
        return f"Error: File not found: {filePath}"

    # NOTE: Implementation details omitted here; see Section 5.1 for full OpenCode-parity behavior:
    # - binary/media detection
    # - byte-based truncation
    # - exact output formatting and error strings

    # Minimal sketch of cat -n style formatting:
    lines = ["def main():\n", "    print('Hello')\n"]  # placeholder
    selected_lines = lines[offset : offset + limit]
    out = []
    for i, line in enumerate(selected_lines):
        line_num = offset + i + 1
        out.append(f"{line_num:>6}\t{line}")  # Right-aligned, tab separator
    return "".join(out)
```

---

## 8. Reference Implementations

### 8.1 Read Tool References

| Source | Location | Notes |
|--------|----------|-------|
| **OpenCode** | [github.com/sst/opencode/.../read.ts](https://github.com/sst/opencode/blob/dev/packages/opencode/src/tool/read.ts) | TypeScript, cat -n format |
| **Claude Code** | [gist.github.com/bgauryy/...](https://gist.github.com/bgauryy/0cdb9aa337d01ae5bd0c803943aa36bd) | Tool specification |
| **LangChain** | [github.com/langchain-ai/.../read.py](https://github.com/langchain-ai/langchain/tree/master/libs/community/langchain_community/tools/file_management/read.py) | Python, simple |
| **Strands Tools** | [github.com/strands-agents/tools/.../file_read.py](https://github.com/strands-agents/tools/blob/main/src/strands_tools/file_read.py) | Python, 10 modes |
| **MCP Filesystem** | [github.com/safurrier/mcp-filesystem](https://github.com/safurrier/mcp-filesystem) | Token-efficient |

### 8.2 Write Tool References

| Source | Location | Notes |
|--------|----------|-------|
| **OpenCode** | [github.com/sst/opencode/.../write.ts](https://github.com/sst/opencode/blob/dev/packages/opencode/src/tool/write.ts) | TypeScript |
| **LangChain** | [github.com/langchain-ai/.../write.py](https://github.com/langchain-ai/langchain/tree/master/libs/community/langchain_community/tools/file_management/write.py) | Python |

### 8.3 Edit Tool References

| Source | Location | Notes |
|--------|----------|-------|
| **OpenCode** | [github.com/sst/opencode/.../edit.ts](https://github.com/sst/opencode/blob/dev/packages/opencode/src/tool/edit.ts) | String replacement |
| **Anthropic text_editor** | [github.com/cablehead/anthropic-text-editor](https://github.com/cablehead/anthropic-text-editor) | Rust reference |
| **OpenHands** | [github.com/OpenHands/OpenHands/.../str_replace_editor](https://github.com/OpenHands/OpenHands) | Known issues documented |
| **Claude Quickstarts** | [github.com/anthropics/claude-quickstarts/.../edit.py](https://github.com/anthropics/claude-quickstarts) | Python |

### 8.4 Glob Tool References

| Source | Location | Notes |
|--------|----------|-------|
| **OpenCode** | [github.com/sst/opencode/.../glob.ts](https://github.com/sst/opencode/blob/dev/packages/opencode/src/tool/glob.ts) | Sorts by mtime |
| **Python pathlib** | [docs.python.org/3/library/pathlib.html](https://docs.python.org/3/library/pathlib.html) | Built-in |
| **wcmatch** | [github.com/facelessuser/wcmatch](https://github.com/facelessuser/wcmatch) | Extended patterns |

### 8.5 Grep Tool References

| Source | Location | Notes |
|--------|----------|-------|
| **OpenCode** | [github.com/sst/opencode/.../grep.ts](https://github.com/sst/opencode/blob/dev/packages/opencode/src/tool/grep.ts) | Ripgrep wrapper |
| **ripgrep-python** | [pypi.org/project/ripgrep-python](https://pypi.org/project/ripgrep-python/) | Native Rust binding |
| **rpygrep** | [pypi.org/project/rpygrep](https://pypi.org/project/rpygrep/) | Type-safe, async |
| **ripgrepy** | [github.com/securisec/ripgrepy](https://github.com/securisec/ripgrepy) | Method chaining |

### 8.6 ApplyPatch Tool References

| Source | Location | Notes |
|--------|----------|-------|
| **OpenCode** | [github.com/sst/opencode/.../apply_patch.ts](https://github.com/sst/opencode/blob/dev/packages/opencode/src/tool/apply_patch.ts) | V4A format |
| **OpenAI Codex** | [github.com/openai/codex/.../apply_patch](https://github.com/openai/codex/blob/main/codex-rs/apply-patch/apply_patch_tool_instructions.md) | V4A format spec |
| **codex-apply-patch** | [pypi.org/project/codex-apply-patch](https://pypi.org/project/codex-apply-patch/) | Python package |
| **Aider** | [github.com/Aider-AI/aider/.../editblock_coder.py](https://github.com/Aider-AI/aider/blob/main/aider/coders/editblock_coder.py) | Unified diff |

---

## 9. Testing Strategy

### 9.1 Test Structure

```
tests/tools/builtin/fs/
├── conftest.py              # Shared fixtures
├── test_read.py
├── test_write.py
├── test_edit.py
├── test_list.py
├── test_glob.py
├── test_grep.py
├── test_multiedit.py
├── test_apply_patch.py
└── test_security.py         # Security-specific tests (see Section 6.6)
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
- Resource limit enforcement

**Integration Tests:**
- Tool chaining (read → edit → write)
- Concurrent operations
- Large file handling
- Security context integration

### 9.3 Fixtures

```python
# tests/tools/builtin/fs/conftest.py

import pytest
import tempfile
from pathlib import Path
from rawagents.tools.builtin.fs._security import SecurityContext, set_security_context


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
def secure_workspace(temp_workspace):
    """Create a workspace with security context configured."""
    ctx = SecurityContext(workspace=str(temp_workspace))
    set_security_context(ctx)
    yield temp_workspace


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
│   ├── _security.py         # SecurityContext, path validation (Section 6.3)
│   ├── _utils.py            # Shared utilities
│   ├── read.py              # Read tool
│   ├── write.py             # Write tool
│   ├── edit.py              # Edit tool
│   ├── list.py              # List tool
│   ├── glob.py              # Glob tool
│   ├── grep.py              # Grep tool
│   ├── multiedit.py         # MultiEdit tool (P1)
│   └── apply_patch.py       # ApplyPatch tool (P2)
├── permissions.py           # PermissionManager (Section 6.4)
├── web/                     # Web tools (future)
├── shell/                   # Shell tools (future)
└── agent/                   # Agent orchestration tools (future)
```

---

## 11. Development Process

### 11.1 Iterative Implementation

**IMPORTANT:** This PRD should be implemented **sequentially**, one tool at a time:

```
For each tool in [read, write, edit, list, glob, grep, multiedit, apply_patch]:

    1. Research
       - Study reference implementations listed in Section 8
       - Understand edge cases and known issues
       - Finalize implementation approach

    2. Test First
       - Write comprehensive tests before implementation
       - Cover happy path, edge cases, and error scenarios
       - Include security tests (CRITICAL - see Section 6.6)

    3. Implement
       - Follow the pattern in Section 7.2
       - ALWAYS integrate with SecurityContext
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
| Phase 0 | `_security.py` | None (implement first!) |
| Phase 1 | `read`, `list`, `glob` | _security (read-only) |
| Phase 2 | `write`, `edit` | read (for verification) |
| Phase 3 | `grep` | ripgrep CLI available |
| Phase 4 | `multiedit` | edit |
| Phase 5 | `apply_patch` | patch parser (Codex-style) |

### 11.3 Definition of Done

A tool is complete when:

- [ ] All tests pass (>90% coverage)
- [ ] **Security tests pass** (symlink, traversal, patterns)
- [ ] Integrates with SecurityContext
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

# Note: `glob` / `grep` use ripgrep CLI (rg) as the backend (OpenCode parity).
# This is an external dependency, not a Python package dependency.

# Optional: for `apply_patch` parsing, use a Codex-style parser implementation.
# (Alternatively, vendor/port OpenCode's patch parser logic.)
codex-apply-patch = ">=0.1"  # optional
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
- [Tool Executor PRD](./003_tool_executor_v1.md)
- [Loops PRD](./004_loops_v1.md)

---

## Appendix C: Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Feb 2026 | Initial PRD |
| 1.1 | Feb 2026 | Aligned filesystem tools/specs to OpenCode (Claude Code-inspired): `list`, `glob`, `grep`, `multiedit`, `apply_patch`; marked non-OpenCode tools as out of scope for parity |
| 1.2 | Feb 2026 | Fixed output formats and parameters to match OpenCode/Claude Code: cat -n style for read, Unicode tree for list, 5 verified edit strategies, atomic multiedit with rollback, absolute paths required, LSP diagnostics output format |
