# Raw Agents — Tool Gap Analysis
## Comparison with Claude Code & OpenCode

**Date:** February 8, 2026
**Scope:** All built-in tools in Raw Agents vs. Claude Code and OpenCode agent frameworks

---

## 1. Current Raw Agents Tool Inventory (11 tools)

### File System Tools (8 tools)

| Tool | File | Summary |
|------|------|---------|
| `read` | `fs/read.py` | Read files with line numbers, streaming for large files, media/binary detection |
| `write` | `fs/write.py` | Create/overwrite files with read-before-edit enforcement and auto-mkdir |
| `edit` | `fs/edit.py` | String find-and-replace with 5 fallback strategies (Simple → LineTrimmed → BlockAnchor → WhitespaceNormalized → IndentationFlexible) |
| `glob` | `fs/glob.py` | Pattern-based file search with mtime sorting |
| `grep` | `fs/grep.py` | Regex content search with ripgrep backend (Python fallback) |
| `list_dir` | `fs/list.py` | Directory listing with Unicode tree output |
| `multiedit` | `fs/multiedit.py` | Atomic multi-edit with rollback |
| `apply_patch` | `fs/apply_patch.py` | Codex V4A patch format (Add/Update/Delete/Move) |

### Shell Tools (3 tools)

| Tool | File | Summary |
|------|------|---------|
| `bash` | `shell/bash.py` | Shell execution with timeouts, background mode, 100+ deny patterns |
| `bash_output` | `shell/bash_output.py` | Read output from background processes |
| `kill_shell` | `shell/kill_shell.py` | Terminate background processes (SIGTERM → SIGKILL) |

---

## 2. Claude Code Tool Inventory (15+ tools)

| Tool | Present in Raw Agents? | Notes |
|------|----------------------|-------|
| `Read` | ✅ Yes | Raw Agents equivalent: `read` |
| `Write` | ✅ Yes | Raw Agents equivalent: `write` |
| `Edit` | ✅ Yes | Raw Agents equivalent: `edit` |
| `Glob` | ✅ Yes | Raw Agents equivalent: `glob` |
| `Grep` | ✅ Yes | Raw Agents equivalent: `grep` |
| `Bash` | ✅ Yes | Raw Agents equivalent: `bash` |
| `NotebookEdit` | ❌ **MISSING** | Jupyter notebook cell editing (replace/insert/delete) |
| `WebSearch` | ❌ **MISSING** | Web search for current information |
| `WebFetch` | ❌ **MISSING** | Fetch and process web page content |
| `TodoWrite` | ❌ **MISSING** | Structured task list management |
| `Task` (subagent spawning) | ❌ **MISSING** | Spawn specialized subagents for parallel work |
| `AskUserQuestion` | ❌ **MISSING** | Interactive user clarification with multiple-choice |
| `EnterPlanMode` / `ExitPlanMode` | ❌ **MISSING** | Plan mode for implementation planning |
| `Skill` | ❌ **MISSING** | Invoke specialized skill bundles |
| `TaskOutput` / `TaskStop` | ❌ **MISSING** | Monitor and stop background agent tasks |

---

## 3. OpenCode Tool Inventory (18+ tools)

| Tool | Present in Raw Agents? | Notes |
|------|----------------------|-------|
| `read` | ✅ Yes | |
| `write` | ✅ Yes | |
| `edit` | ✅ Yes | |
| `multiedit` | ✅ Yes | |
| `glob` | ✅ Yes | |
| `grep` | ✅ Yes | |
| `bash` | ✅ Yes | |
| `apply_patch` | ✅ Yes | |
| `codesearch` | ❌ **MISSING** | Semantic/structural code search (beyond grep) |
| `lsp` | ❌ **MISSING** | Language Server Protocol integration (go-to-definition, find-references, diagnostics) |
| `websearch` | ❌ **MISSING** | Web search (uses Exa AI) |
| `webfetch` | ❌ **MISSING** | Fetch and parse web content |
| `batch` | ❌ **MISSING** | Batch operations for processing multiple items |
| `task` | ❌ **MISSING** | Subagent/task spawning |
| `todo` | ❌ **MISSING** | Todo/task tracking |
| `plan` | ❌ **MISSING** | Plan creation and management |
| `question` | ❌ **MISSING** | Interactive user question/clarification |
| `skill` | ❌ **MISSING** | Skill system for domain-specific instructions |
| `external-directory` | ❌ **MISSING** | Access to directories outside workspace |

---

## 4. Complete List of Missing Tools

### Tier 1 — Critical (core agent capabilities both Claude Code and OpenCode have)

These are tools that **both** Claude Code and OpenCode provide and that are essential for a production-quality coding agent:

#### 1. `WebSearch`
- **What it does:** Searches the web for up-to-date information, documentation, error messages, library APIs, etc.
- **Why it matters:** Agents need access to current information beyond training data. Used constantly for looking up docs, Stack Overflow answers, API references.
- **Claude Code:** Built-in `WebSearch` tool with domain filtering
- **OpenCode:** `websearch.ts` using Exa AI integration
- **Implementation notes:** Could integrate with Tavily, Exa, SerpAPI, or Brave Search. Needs query input, optional domain filters, returns titles + URLs + snippets.

#### 2. `WebFetch`
- **What it does:** Fetches a specific URL, converts HTML to markdown/text, and processes it with a prompt.
- **Why it matters:** After finding URLs via search, agents need to actually read web content — documentation pages, README files, API docs, blog posts.
- **Claude Code:** Built-in `WebFetch` with HTML-to-markdown conversion and AI summarization
- **OpenCode:** `webfetch.ts` for URL content retrieval
- **Implementation notes:** Needs URL fetch, HTML→markdown conversion (e.g., html2text, markdownify), optional content summarization, response caching.

#### 3. `TodoWrite` / `TodoRead`
- **What it does:** Creates and manages structured task lists with status tracking (pending → in_progress → completed).
- **Why it matters:** For multi-step tasks, todo lists help the agent track progress, show the user what's happening, and avoid losing track of subtasks.
- **Claude Code:** `TodoWrite` with status states and structured format
- **OpenCode:** `todo.ts` for task tracking
- **Implementation notes:** In-memory todo list with serializable state. Each todo has: content, activeForm (present tense), status. List persists across tool calls within a session.

#### 4. `Task` (Subagent Spawning)
- **What it does:** Launches independent subagents to handle complex subtasks in parallel. Each subagent gets its own context and tool access.
- **Why it matters:** Enables parallelization (research multiple things simultaneously), context isolation (don't pollute the main conversation with large explorations), and specialization (different agents for different jobs).
- **Claude Code:** `Task` tool with typed subagents (Explore, Plan, Bash, general-purpose)
- **OpenCode:** `task.ts` with configurable subagents
- **Implementation notes:** Requires an agent loop implementation. Each subagent runs an independent LLM conversation with a subset of tools. Returns result to parent agent. Needs: agent_type, prompt, max_turns, optional model override.

#### 5. `AskUserQuestion`
- **What it does:** Presents structured questions to the user with multiple-choice options for gathering preferences, clarifying requirements, or getting decisions.
- **Why it matters:** Instead of the agent guessing, it can pause and ask the user for direction. Prevents wasted work on wrong approaches.
- **Claude Code:** `AskUserQuestion` with multi-select, options, headers
- **OpenCode:** `question.ts` for user interaction
- **Implementation notes:** Structured question format with options array. Each option has label + description. Supports multi-select. Returns user's selection(s).

---

### Tier 2 — Important (present in one or both, significant capability gaps)

#### 6. `NotebookEdit`
- **What it does:** Edits Jupyter notebook (.ipynb) cells — replace cell content, insert new cells, delete cells. Handles cell types (code/markdown).
- **Why it matters:** Data science and ML workflows live in notebooks. Without this, agents can't help with notebook-based development.
- **Claude Code:** Full `NotebookEdit` with replace/insert/delete modes
- **OpenCode:** Not present (handles notebooks through raw file editing)
- **Implementation notes:** Parse .ipynb JSON, manipulate cells array. Needs: notebook_path, cell_number (0-indexed), new_source, cell_type, edit_mode (replace/insert/delete).

#### 7. `Plan` / `EnterPlanMode` / `ExitPlanMode`
- **What it does:** Transitions the agent into a "planning mode" where it explores the codebase and designs an implementation approach before writing code. User approves the plan before execution begins.
- **Why it matters:** For non-trivial tasks, planning prevents wasted effort. The agent explores first, proposes an approach, gets approval, then executes.
- **Claude Code:** `EnterPlanMode` + `ExitPlanMode` with plan file writing
- **OpenCode:** `plan.ts` for plan management
- **Implementation notes:** State machine: normal → plan_mode → execution. In plan mode, agent can only use read-only tools (Read, Glob, Grep, WebSearch). Plan written to a file. ExitPlanMode signals user approval needed.

#### 8. `Skill`
- **What it does:** Invokes pre-built capability bundles (skills) that provide domain-specific instructions, tool restrictions, and workflows.
- **Why it matters:** Skills enable extensibility — users can add new capabilities without modifying the core agent. Skills for document creation, code review, deployment, etc.
- **Claude Code:** `Skill` tool with YAML frontmatter skill definitions
- **OpenCode:** `skill.ts` with markdown-based skill system
- **Implementation notes:** Skill registry. Each skill is a markdown file with instructions that get injected into the system prompt when activated. Skills can restrict available tools, provide examples, and define workflows.

#### 9. `LSP` (Language Server Protocol)
- **What it does:** Integrates with language servers for code intelligence — go-to-definition, find-references, hover info, diagnostics, code actions, rename symbols.
- **Why it matters:** Enables the agent to understand code semantically, not just textually. Finding all references to a function, getting type info, understanding call hierarchies.
- **Claude Code:** Not built-in (relies on grep/glob for code search)
- **OpenCode:** `lsp.ts` with full LSP integration
- **Implementation notes:** LSP client that connects to language servers (TypeScript, Python, Go, Rust, etc.). Key operations: textDocument/definition, textDocument/references, textDocument/hover, textDocument/diagnostics. Requires running language server processes.

#### 10. `CodeSearch`
- **What it does:** Semantic code search that goes beyond simple regex grep — understands code structure, can find implementations, usages, and related code.
- **Why it matters:** In large codebases, grep misses things. Semantic search finds conceptually related code even when naming varies.
- **Claude Code:** Not built-in (relies on grep/glob)
- **OpenCode:** `codesearch.ts` for structural code search
- **Implementation notes:** Could use tree-sitter for AST-based search, or integrate with code search services. Falls back to ripgrep with intelligent query construction.

---

### Tier 3 — Nice-to-Have (present in one framework, less critical)

#### 11. `Batch`
- **What it does:** Runs batch operations to process multiple items at once (parallel tool calls, bulk file operations).
- **Why it matters:** Efficiency for repetitive operations — rename 50 files, lint 20 modules, etc.
- **Claude Code:** Not a separate tool (handled through parallel tool calls)
- **OpenCode:** `batch.ts` for batch processing
- **Implementation notes:** Takes an array of operations and executes them (potentially in parallel). Could be implemented as a meta-tool that wraps other tools.

#### 12. `ExternalDirectory`
- **What it does:** Provides access to directories outside the configured workspace boundary.
- **Why it matters:** Sometimes agents need to read from node_modules, system libraries, or reference projects outside the workspace.
- **Claude Code:** Not a separate tool (workspace is flexible)
- **OpenCode:** `external-directory.ts` for external access
- **Implementation notes:** Requires explicit user permission. Adds temporary read-only access to a specific external path. Security implications need careful handling.

#### 13. `TaskOutput` / `TaskStop`
- **What it does:** Monitor running subagent tasks, retrieve their output, and stop them if needed.
- **Why it matters:** Companion tools to `Task` for managing long-running subagent operations.
- **Claude Code:** `TaskOutput` (blocking/non-blocking) and `TaskStop`
- **OpenCode:** Managed through the task system
- **Implementation notes:** Task registry with IDs. TaskOutput polls or blocks for completion. TaskStop sends cancellation signal.

---

## 5. Summary Comparison Matrix

| Tool Category | Raw Agents | Claude Code | OpenCode |
|--------------|-----------|-------------|----------|
| **File Read** | ✅ read | ✅ Read | ✅ read |
| **File Write** | ✅ write | ✅ Write | ✅ write |
| **File Edit** | ✅ edit | ✅ Edit | ✅ edit |
| **Multi-Edit** | ✅ multiedit | ❌ (removed in v2) | ✅ multiedit |
| **Apply Patch** | ✅ apply_patch | ❌ (not built-in) | ✅ apply_patch |
| **Glob** | ✅ glob | ✅ Glob | ✅ glob |
| **Grep** | ✅ grep | ✅ Grep | ✅ grep |
| **Directory List** | ✅ list_dir | ❌ (uses Bash ls) | ❌ (uses Bash ls) |
| **Shell** | ✅ bash | ✅ Bash | ✅ bash |
| **Background Output** | ✅ bash_output | ✅ TaskOutput | ❌ |
| **Kill Process** | ✅ kill_shell | ✅ TaskStop | ❌ |
| **Web Search** | ❌ | ✅ WebSearch | ✅ websearch |
| **Web Fetch** | ❌ | ✅ WebFetch | ✅ webfetch |
| **Todo/Task List** | ❌ | ✅ TodoWrite | ✅ todo |
| **Subagent/Task** | ❌ | ✅ Task | ✅ task |
| **User Question** | ❌ | ✅ AskUserQuestion | ✅ question |
| **Plan Mode** | ❌ | ✅ EnterPlanMode / ExitPlanMode | ✅ plan |
| **Notebook Edit** | ❌ | ✅ NotebookEdit | ❌ |
| **Skill System** | ❌ | ✅ Skill | ✅ skill |
| **LSP Integration** | ❌ | ❌ | ✅ lsp |
| **Code Search** | ❌ | ❌ | ✅ codesearch |
| **Batch Operations** | ❌ | ❌ | ✅ batch |
| **External Directory** | ❌ | ❌ | ✅ external-directory |

---

## 6. Raw Agents Unique Strengths

Tools and features Raw Agents has that are notable:

1. **`list_dir`** — Neither Claude Code nor OpenCode have a dedicated directory listing tool (both use `bash ls`). Raw Agents has a proper tool with Unicode tree output and default ignore patterns.

2. **`multiedit`** — Atomic multi-edit with rollback. Claude Code removed this in v2, but it's genuinely useful for coordinated changes.

3. **`apply_patch`** — V4A Codex-style patch format. Claude Code doesn't have this built-in (it uses Edit). OpenCode has it.

4. **5-Strategy Edit Fallback** — Raw Agents' edit tool tries 5 replacement strategies, making it more resilient to LLM formatting variations than either Claude Code or OpenCode.

5. **Security Architecture** — 3-layer security (path validation + permissions + sandbox), 100+ shell deny patterns, read-before-edit enforcement, TOCTOU file locking. This is more comprehensive than what's publicly visible in either Claude Code or OpenCode.

---

## 7. Recommended Implementation Priority

Based on impact and implementation complexity:

| Priority | Tool | Effort | Impact |
|----------|------|--------|--------|
| **P0** | `WebSearch` | Medium | Very High — agents are severely limited without web access |
| **P0** | `WebFetch` | Medium | Very High — complements WebSearch |
| **P0** | `TodoWrite` | Low | High — simple in-memory state, big UX improvement |
| **P0** | `AskUserQuestion` | Low | High — enables interactive clarification |
| **P1** | `Task` (subagents) | High | Very High — enables parallelism and context isolation |
| **P1** | `Plan` mode | Medium | High — prevents wasted work on complex tasks |
| **P1** | `Skill` system | Medium | High — extensibility mechanism |
| **P2** | `NotebookEdit` | Low | Medium — needed for data science workflows |
| **P2** | `LSP` | High | Medium — semantic code understanding |
| **P2** | `CodeSearch` | Medium | Medium — better than grep for large codebases |
| **P3** | `Batch` | Low | Low — convenience, not essential |
| **P3** | `ExternalDirectory` | Low | Low — edge case |
| **P3** | `TaskOutput/TaskStop` | Low | Low — companion to Task tool |

---

## 8. Total Missing Tool Count

**Raw Agents is missing 13 tools** that Claude Code and/or OpenCode provide:

1. WebSearch
2. WebFetch
3. TodoWrite / TodoRead
4. Task (subagent spawning)
5. AskUserQuestion
6. NotebookEdit
7. EnterPlanMode / ExitPlanMode
8. Skill
9. LSP
10. CodeSearch
11. Batch
12. ExternalDirectory
13. TaskOutput / TaskStop

Of these, **5 are critical** (WebSearch, WebFetch, TodoWrite, Task, AskUserQuestion) — both Claude Code and OpenCode have them, and they represent fundamental capabilities that any production coding agent needs.
