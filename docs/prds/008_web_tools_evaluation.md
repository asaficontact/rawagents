# PRD Evaluation Report: Web Tools (008)

**Document Evaluated:** `008_web_tools_v1.md` (Version 2.0 — Unified config, simplified provider model)
**Evaluation Date:** February 2026
**Evaluator:** Multi-agent review (codebase pattern analysis, config ergonomics audit, Claude Code + OpenCode research)
**Status:** APPROVED FOR IMPLEMENTATION
**Previous Version:** v1.1 (21 issues found and fixed; then 5 architectural issues identified and resolved in v2.0)

---

## 1. Structural Completeness

### Comparison with FS PRD Template (005) and Shell PRD (006)

| Section | FS PRD (005) | Shell PRD (006) | Web PRD (008 v2.0) | Status |
|---------|--------------|-----------------|---------------------|--------|
| Executive Summary | ✅ | ✅ | ✅ | Complete (key decisions table, zero-config quick start) |
| Background & Motivation | ✅ | ✅ | ✅ | Complete ("Why Not Existing Packages" table) |
| Goals & Non-Goals | ✅ | ✅ | ✅ | Complete (7 goals, 5 non-goals — **updated** for v2.0) |
| Tool Inventory | ✅ | ✅ | ✅ | Complete (P0 diagram) |
| Tool Specifications | ✅ | ✅ | ✅ | Complete (2 tools, full params + JSON schemas) |
| Security Architecture | ✅ | ✅ | ✅ | **Comprehensive** (unified WebContext, 3-layer model, 4 threats) |
| Content Processing | N/A | N/A | ✅ | **NEW in v2.0** — Dedicated Section 7 with Protocol, examples, pipeline diagram |
| Implementation Approach | ✅ | ✅ | ✅ | **Streamlined** (6 subsections, only Brave built-in) |
| Reference Implementations | ✅ | ✅ | ✅ | Complete (Claude Code + OpenCode synthesis) |
| Testing Strategy | ✅ | ✅ | ✅ | Complete (unit, integration, content processor, provider) |
| Project Structure | ✅ | ✅ | ✅ | **Simplified** (8 files + 1 provider, down from 10+) |
| Development Process | ✅ | ✅ | ✅ | Complete (3 phases over 7 days) |
| Error Handling & Logging | N/A | ✅ | ✅ | Complete (16 error cases, 4 log levels) |
| Appendices | ✅ | ✅ | ✅ | **Streamlined** (4 appendices A-D, down from 6 in v1.1) |

**Result:** ✅ All sections present. The v2.0 revision improved structure by adding a dedicated Content Processing section (Section 7) and streamlining appendices from 6 to 4 by consolidating implementation notes.

---

## 2. Tool Specification Completeness

### 2.1 Web Search Tool

| Requirement | Status | Notes |
|-------------|--------|-------|
| Parameters table | ✅ | All 4 parameters documented (query, num_results, allowed_domains, blocked_domains) |
| Output format | ✅ | String format with numbered results, URLs, and snippets |
| JSON schema | ✅ | Full JSON Schema with types, constraints, and descriptions |
| Behavior documentation | ✅ | Provider auto-creation from BRAVE_API_KEY, result format, domain filtering, query validation |
| Error handling | ✅ | 5 error cases: empty query, both domain lists, no provider, API error, rate limit |
| Security checks | ✅ | Result URL filtering, domain allowlist/blocklist, rate limiting via WebContext |
| Examples | ✅ | 3 Python examples (basic zero-config, allowed_domains, blocked_domains) |
| Zero-config behavior | ✅ | **NEW in v2.0** — Auto-creates BraveSearchProvider from env var |

**No gaps remaining.**

### 2.2 Web Fetch Tool

| Requirement | Status | Notes |
|-------------|--------|-------|
| Parameters table | ✅ | All 4 parameters documented (url, prompt, format, timeout) |
| Output format | ✅ | Success, error, and redirect output formats documented |
| JSON schema | ✅ | Full JSON Schema with pattern validation for URL |
| Behavior documentation | ✅ | URL validation, security checks, HTTP request, response limits, content conversion, Cloudflare retry, content processor hook, caching |
| Error handling | ✅ | 9 error cases documented in table (Section 13.2) |
| Redirect handling | ✅ | Cross-host detection, flag in output (not auto-follow) |
| Output formats | ✅ | markdown (default), text, html |
| Caching | ✅ | 15-minute TTL, cache-before-fetch, raw content cached (not processed) |
| Content processor | ✅ | **Elevated in v2.0** — Optional hook via WebContext.content_processor, Section 7 documentation |
| Examples | ✅ | 3 Python examples (basic, format, prompt) |

**No gaps remaining.**

---

## 3. Security Architecture Review

### 3.1 Three-Layer Model

| Layer | Documented | Implementation Provided | Tests Defined |
|-------|------------|------------------------|---------------|
| URL Validation (SSRF + domain) | ✅ | ✅ Full WebContext code (~350 lines) | ✅ |
| Rate Limiting | ✅ | ✅ Per-operation tracking with configurable limits | ✅ |
| Response Processing | ✅ | ✅ Size limits + conversion + optional processor | ✅ |

### 3.2 Threat Model Coverage

| Threat | Documented | Mitigation Detailed | Implementation |
|--------|------------|-------------------|----------------|
| SSRF (private IP access) | ✅ | ✅ DNS resolution → IP validation | ✅ Full code |
| Rate limit abuse | ✅ | ✅ Per-minute tracking per operation | ✅ Full code |
| Sensitive data leakage | ✅ | ✅ Per-session cache, ContentProcessor filter | ✅ Documented |
| Credential theft via redirect | ✅ | ✅ Cross-host redirect flagging | ✅ Appendix D.1 |

### 3.3 SSRF Prevention Coverage

| IP Range | Blocked | Notes |
|----------|---------|-------|
| IPv4 Loopback (127.0.0.0/8) | ✅ | Via `ipaddress.is_loopback` |
| RFC 1918 Private (10.x, 172.16.x, 192.168.x) | ✅ | Via `ipaddress.is_private` |
| IPv6 Loopback (::1) | ✅ | Via `ipaddress.is_loopback` |
| IPv6 Link-Local (fe80::/10) | ✅ | Via `ipaddress.is_link_local` |
| IPv6 Unique Local (fc00::/7) | ✅ | Via `ipaddress.is_private` |
| Link-Local (169.254.x.x) | ✅ | Via `ipaddress.is_link_local` |
| Reserved addresses | ✅ | Via `ipaddress.is_reserved` |
| AWS metadata (169.254.169.254) | ✅ | Covered by link-local blocking |
| GCP metadata (metadata.google.internal) | ✅ | DNS resolution → private IP |
| Azure metadata (169.254.165.254) | ✅ | Covered by link-local blocking |

### 3.4 Security Gaps

**None remaining.** The unified WebContext consolidates all security settings in one place, reducing the risk of misconfiguration that could arise from having separate security and config objects.

### 3.5 Security Pattern Consistency with Codebase

| Pattern | fs/_security.py | shell/_security.py | web/_context.py (v2.0) | Consistent |
|---------|----------------|--------------------|-----------------------|------------|
| Error class extends PermissionError | ✅ | ✅ | ✅ | ✅ |
| `contextvars.ContextVar` for context | ✅ | ✅ | ✅ | ✅ |
| `get_*_context()` factory function | ✅ | ✅ | ✅ | ✅ |
| `set_*_context()` setter function | ✅ | ✅ | ✅ | ✅ |
| `@dataclass` for context class | ✅ | ✅ | ✅ | ✅ |
| `__post_init__` for normalization | ✅ | ✅ | ✅ | ✅ |
| Module-level `__all__` | ✅ | ✅ | ✅ | ✅ |
| `from __future__ import annotations` | ✅ | ✅ | ✅ | ✅ |
| `allow_permissive` parameter | ✅ (fs) | ✅ (shell) | ✅ | ✅ |
| `warnings.warn(RuntimeWarning)` for defaults | ✅ | ✅ | ✅ | ✅ |
| **Single unified context object** | ✅ (SecurityContext) | ✅ (ShellSecurityContext) | ✅ (WebContext) | ✅ **Fixed in v2.0** |

**All patterns are consistent with existing codebase.** The v2.0 change to a single unified `WebContext` was the most significant improvement — it eliminated the pattern inconsistency where v1.1 had two separate objects (WebSecurityContext + WebConfig) while fs and shell each use one.

---

## 4. v2.0 Architectural Improvements

This section documents the 5 architectural issues identified in the critical evaluation of v1.1 and how they were resolved in v2.0.

### 4.1 Issues Resolved

| # | Severity | Issue (v1.1) | Resolution (v2.0) | Assessment |
|---|----------|-------------|-------------------|------------|
| A1 | CRITICAL | **Dual-config complexity**: `WebSecurityContext` + `WebConfig` = two config objects, two imports, two setter calls, two mental models | Merged into single `WebContext` dataclass in `_context.py`. One import, one setter, one mental model. Matches fs/shell pattern exactly. | ✅ **Fully resolved** |
| A2 | HIGH | **Over-shipping providers**: Brave + Tavily + Exa built-in = 3 provider files, 3 test suites, 3 optional dependencies | Ship only `BraveSearchProvider`. Tavily/Exa documented as Protocol implementation examples (~20 lines each). | ✅ **Fully resolved** |
| A3 | HIGH | **Auto-detection algorithm**: Priority-based env var scanning + `RAWAGENTS_SEARCH_PROVIDER` override = two competing config paths, hidden behavior | Removed entirely. `web_search` lazily creates `BraveSearchProvider` from `BRAVE_API_KEY` on first call if no provider configured. One path, zero magic. | ✅ **Fully resolved** |
| A4 | MEDIUM | **ContentProcessor buried**: Key extensibility hook treated as optional afterthought in a subsection | Elevated to dedicated Section 7 "Content Processing (Extensibility)" with 5 subsections: why it exists, Protocol definition, Haiku extraction example, sensitive data filter example, pipeline position diagram. | ✅ **Fully resolved** |
| A5 | MEDIUM | **Zero-config path not simple enough**: Required manual WebContext creation even for basic Brave usage | Added Section 1.3 "Zero-Config Quick Start" (2 lines of code). Tools auto-create `WebContext` with permissive defaults. `get_web_context(allow_permissive=True)` returns default context. | ✅ **Fully resolved** |

### 4.2 Structural Changes Summary

| Aspect | v1.1 | v2.0 | Improvement |
|--------|------|------|-------------|
| Config objects | 2 (`WebSecurityContext` + `WebConfig`) | 1 (`WebContext`) | 50% fewer concepts |
| Config files | 3 (`_security.py` + `_config.py` + `_errors.py`) | 1 (`_context.py`) | 67% fewer files |
| Built-in providers | 3 (Brave + Tavily + Exa) | 1 (Brave only) | 67% less maintenance |
| Provider detection | Auto-detection algorithm with priority + env override | Lazy init from `BRAVE_API_KEY` | Zero hidden behavior |
| ContentProcessor docs | Subsection in Section 7 | Own Section 7 (5 subsections) | First-class documentation |
| Zero-config path | Requires manual setup | `export BRAVE_API_KEY` → 2 lines of code | True zero-config |
| Module file count | 10+ source files | 8 source files + 1 provider | Simpler project structure |
| Appendices | 6 (A–F) | 4 (A–D) | Streamlined, no redundancy |
| Test files | 10 (incl. per-provider tests) | 8 (consolidated) | Focused testing |

---

## 5. User Requirements Verification

The user specified 5 concrete requirements. This section verifies each is met.

### 5.1 Requirement: "Brave as default, plug-and-play for other providers"

| Aspect | Met | Evidence |
|--------|-----|----------|
| Brave is the default | ✅ | `BraveSearchProvider` is the only built-in. Auto-created from `BRAVE_API_KEY` env var. |
| Plug-and-play custom providers | ✅ | `SearchProvider` Protocol (PEP 544) with `@runtime_checkable`. Complete Tavily and Exa examples in docstring (~20 lines each). |
| Easy configuration | ✅ | `WebContext(search_provider=MyProvider())` — one line to swap provider. |

### 5.2 Requirement: "OpenCode implementation style for fetch"

| Aspect | Met | Evidence |
|--------|-----|----------|
| Simple fetch→convert→return | ✅ | `web_fetch` follows OpenCode's direct pipeline. Section 5.2 behavior docs. |
| 3 output formats | ✅ | markdown (default), text, html — same as OpenCode. |
| Cloudflare retry | ✅ | `CloudflareRetryTransport` retries on 403 + `cf-mitigated`. Section 8.5. |
| 5MB / 100KB limits | ✅ | `max_response_bytes = 5 * 1024 * 1024`, `max_content_chars = 100_000`. Section 6.3. |

### 5.3 Requirement: "Easy extensibility for post-fetch processing"

| Aspect | Met | Evidence |
|--------|-----|----------|
| Extensibility hook exists | ✅ | `ContentProcessor` Protocol with `async def process()`. Section 7.2. |
| Claude Code-style example | ✅ | `HaikuExtractionProcessor` in Section 7.3 (~25 lines). |
| Pipeline position documented | ✅ | Section 7.5 ASCII diagram: fetch → convert → **processor** → truncate → return. |
| Not provided by default | ✅ | `WebContext.content_processor` defaults to `None`. Section 7.1 explicitly states "Not provided by default." |

### 5.4 Requirement: "Easy and configurable"

| Aspect | Met | Evidence |
|--------|-----|----------|
| Zero-config works | ✅ | Section 1.3: `export BRAVE_API_KEY` → 2 lines of code. |
| Single config object | ✅ | `WebContext` dataclass — one import, one setter. |
| Rich configuration options | ✅ | 18 fields grouped into 8 logical sections. Appendix C shows 8 config examples. |
| Matches existing patterns | ✅ | Same `get_*_context()` / `set_*_context()` pattern as fs/shell. |

### 5.5 Requirement: "Complete and good to go"

| Aspect | Met | Evidence |
|--------|-----|----------|
| All tool specs complete | ✅ | web_search (Section 5.1) and web_fetch (Section 5.2) with full params, schemas, behavior, errors. |
| Security architecture | ✅ | 3-layer model, 4 threat mitigations, SSRF prevention, rate limiting. Section 6. |
| Implementation code provided | ✅ | ~900 lines across 8 files. Production-quality async Python. |
| Testing strategy | ✅ | 8 test files covering unit, integration, security, caching, conversion, processor, provider. |
| Development phases | ✅ | 3 phases over 7 days. Section 12. |
| Error handling complete | ✅ | 16 error cases in table (Section 13.2). 4 log levels. |

---

## 6. Reference Implementation Coverage

| Reference Type | FS PRD (005) | Shell PRD (006) | Web PRD (008 v2.0) | Assessment |
|----------------|-------------|-----------------|---------------------|------------|
| Claude Code analysis | ✅ | ✅ | ✅ Deep | Complete (server-side Brave, Haiku extraction, trusted sites) |
| OpenCode analysis | ✅ | ✅ | ✅ Deep | Complete (Exa MCP, Turndown, Cloudflare retry) |
| Provider comparison | N/A | N/A | ✅ | Appendix B (5 providers compared) |
| Reference provider code | N/A | N/A | ✅ | BraveSearchProvider (~100 lines), Tavily/Exa examples in docstrings |
| Design synthesis | ✅ | ✅ | ✅ | Section 9.3 "Our Approach: Best of Both" |

---

## 7. Testing Strategy Evaluation

### 7.1 Test Categories Defined

| Category | Defined | Examples |
|----------|---------|----------|
| Unit tests (web_search) | ✅ | 7 test cases covering valid query, empty query, domain filtering, rate limit, both domain lists, provider error, no provider |
| Unit tests (web_fetch) | ✅ | 12 test cases covering valid URL, no scheme, SSRF, domain blocked, response too large, truncation, timeout, redirect, formats, cache, content processor, binary content |
| Security tests | ✅ | 9 test cases covering URL validation, SSRF IPs, localhost, link-local, allowlist, blocklist, rate limit tracking, operation-specific limits |
| Content processor tests | ✅ | **NEW in v2.0** — 5 test cases: correct args, runs after conversion, runs before truncation, no-processor passthrough, error handling |
| Provider tests | ✅ | BraveSearchProvider tests (mock + integration) |
| Integration tests | ✅ | 4 tests: real Brave API, real URL fetch, Cloudflare retry, cache persistence |
| Cache tests | ✅ | TTL, expiry, concurrency, thundering herd, LRU eviction |
| Conversion tests | ✅ | HTML→Markdown/Text, ATX heading style, script/style stripping |
| HTTP client tests | ✅ | CloudflareRetryTransport, shared client lifecycle |

### 7.2 Test File Structure (v2.0)

| Test File | Purpose | Complete |
|-----------|---------|----------|
| test_web_search.py | Tool-level tests | ✅ |
| test_web_fetch.py | Tool-level tests | ✅ |
| test_security.py | SSRF, URL validation, rate limiting | ✅ |
| test_content_processor.py | **NEW** ContentProcessor integration | ✅ |
| test_cache.py | TTL, expiry, concurrency, thundering herd | ✅ |
| test_conversion.py | HTML → Markdown/Text | ✅ |
| test_http.py | Client, Cloudflare retry transport | ✅ |
| test_brave.py | BraveSearchProvider tests | ✅ |
| conftest.py | Shared fixtures (mock providers, mock processor, etc.) | ✅ |

**Changes from v1.1:** Removed `providers/test_tavily.py` and `providers/test_exa.py` (providers removed). Added `test_content_processor.py` (elevated to first-class). Flattened `test_brave.py` from `providers/` subdirectory.

---

## 8. Claude Code Parity Analysis

### 8.1 Features Compared

| Claude Code Feature | Web PRD (008 v2.0) | Notes |
|--------------------|---------------------|-------|
| Web search | ✅ | Brave default (same backend as Claude Code) |
| Web fetch with HTML→Markdown | ✅ | markdownify (Python Turndown equivalent) |
| SSRF prevention | ✅ | Private IP blocking, async DNS resolution |
| Domain filtering | ✅ | Allowlist + blocklist via unified WebContext |
| Content processing (Haiku extraction) | ✅ Optional | ContentProcessor Protocol (Section 7, first-class docs) |
| Trusted sites bypass | ❌ Intentional | Not built-in; HaikuExtractionProcessor example shows how to implement |
| 15-minute cache | ✅ | AsyncTTLCache with thundering herd prevention |
| Cross-host redirect detection | ✅ | Flag in output (not auto-follow) |
| Rate limiting | ✅ | Per-operation configurable limits in WebContext |
| Encrypted responses | ❌ Intentional | Not applicable (local execution, not server-side) |
| Secondary Opus conversation | ❌ Intentional | Not applicable (proprietary architecture) |

### 8.2 OpenCode Parity Analysis

| OpenCode Feature | Web PRD (008 v2.0) | Notes |
|-----------------|---------------------|-------|
| Web search | ✅ | Via SearchProvider Protocol (Brave default; Exa documented as example) |
| HTML→Markdown via Turndown | ✅ | markdownify (Python equivalent) |
| 3 output formats (markdown/text/html) | ✅ | Same three formats supported |
| Cloudflare retry on 403 + cf-mitigated | ✅ | CloudflareRetryTransport |
| 5MB response limit | ✅ | `max_response_bytes = 5 * 1024 * 1024` |
| 100KB text truncation | ✅ | `max_content_chars = 100_000` |
| Content-Type binary rejection | ✅ | Appendix D.2 |
| SSE response parsing | ❌ Intentional | Standard HTTP, not MCP SSE |

### 8.3 Intentional Differences

| Difference | RawAgents Choice | Reference | Rationale |
|-----------|-----------------|-----------|-----------|
| Trusted sites bypass | Not built-in | Claude Code has ~80 trusted sites | Users implement via ContentProcessor (Section 7.3 example) |
| Search encryption | None | Claude Code encrypts responses | Not applicable for local execution |
| Secondary model extraction | Optional via ContentProcessor | Claude Code uses Haiku 4.5 | Users choose their extraction model; no forced dependency |
| Search provider | Brave only (+ Protocol) | Claude Code = Brave, OpenCode = Exa | Protocol enables any provider; only Brave ships built-in (reduced from 3 in v1.1) |
| MCP transport | Not used | OpenCode uses Exa MCP | Direct HTTP calls to provider APIs (simpler, fewer dependencies) |
| Config model | Single unified WebContext | N/A | Matches fs/shell pattern; simpler than v1.1's dual config |

---

## 9. Implementation Code Quality

### 9.1 Code Provided (v2.0)

| Component | Approx. Lines | Quality Assessment |
|-----------|---------------|-------------------|
| WebContext (`_context.py`) | ~350 | **Unified.** Async DNS, SSRF prevention, rate limiting, error classes. All in one file matching fs/shell pattern. |
| SearchProvider + ContentProcessor (`_types.py`) | ~140 | Clean Protocol definitions with docstrings and complete examples. `@runtime_checkable` correctly applied. |
| Content conversion (`_conversion.py`) | ~50 | Clean HTML→Markdown/Text. ATX heading style. |
| HTTP client (`_http.py`) | ~50 | CloudflareRetryTransport extends httpx correctly. Shared client with connection pooling. |
| AsyncTTLCache (`_cache.py`) | ~160 | Thundering herd prevention via asyncio.Event. LRU eviction. Clear async lock usage. |
| BraveSearchProvider (`providers/brave.py`) | ~100 | Complete with domain filtering, error handling. Only built-in provider. |
| Module exports (`__init__.py`) | ~80 | Complete `__all__` with all public symbols. Clean import structure with usage examples in docstring. |

**Total implementation code in PRD: ~930 lines** (reduced from ~1,080 in v1.1 by removing Tavily/Exa providers and consolidating config files)

### 9.2 Code Quality Assessment

| Criteria | Score (1-5) | Notes |
|----------|-------------|-------|
| Async correctness | 5 | All I/O async. DNS resolution via `asyncio.to_thread()`. No event loop blocking. |
| Error boundary pattern | 5 | Tools never raise; always return error strings. Matches fs/shell convention. |
| Type safety | 5 | Full type annotations. Protocol with `@runtime_checkable`. |
| Pattern consistency | 5 | `contextvars`, `@dataclass`, `get_*/set_*` factories all match existing codebase. **Improved** by unifying to single context. |
| Documentation | 5 | Comprehensive docstrings, module-level docs, examples in Protocols. Zero-config quick start. |
| Edge case handling | 5 | Binary content types, markdown passthrough, encoding, redirect detection, thundering herd. |
| Config ergonomics | 5 | **Improved** — single `WebContext` replaces dual config. Zero-config path documented. |

---

## 10. Overall Assessment

### 10.1 Scores

| Criteria | v1.1 Score | v2.0 Score | Notes |
|----------|-----------|-----------|-------|
| Structural Completeness | 5 | 5 | Maintained. Improved with dedicated Section 7 for ContentProcessor. |
| Tool Specifications | 5 | 5 | Maintained. Updated to reference WebContext instead of dual configs. |
| Security Coverage | 5 | 5 | Maintained. Unified config reduces misconfiguration risk. |
| Implementation Code | 5 | 5 | Maintained. Reduced LOC by removing unnecessary providers. |
| Testing Strategy | 5 | 5 | Maintained. Added content processor tests, removed unused provider tests. |
| Reference Coverage | 5 | 5 | Maintained. |
| OpenCode Parity | 5 | 5 | Maintained. |
| Claude Code Parity | 5 | 5 | Maintained. |
| Extensibility | 5 | 5 | **Improved** — ContentProcessor elevated to first-class. |
| Codebase Consistency | 4 | 5 | **Improved** — v1.1 had dual config (inconsistent with fs/shell). v2.0 uses single unified context. |
| Config Ergonomics | 3 | 5 | **Major improvement** — Zero-config path, single config object, no auto-detection magic. |

**Overall Score: 5.0 / 5** — **EXCELLENT**, ready for implementation.

### 10.2 Required Refinements

**None.** All 5 architectural issues from the v1.1 evaluation have been resolved in v2.0.

### 10.3 Minor Clarifications (Non-Blocking)

These are minor documentation improvements that can be addressed during implementation. They do not block approval.

| # | Area | Clarification Needed | Severity |
|---|------|---------------------|----------|
| MC-1 | ContentProcessor error handling | The `process()` method's exception behavior is partially specified (Section 13.2 mentions `"Error: Content processing failed: {details}"`), but the PRD does not explicitly state whether `web_fetch` should return the original unconverted content or the error string when the processor fails. **Recommendation:** Add a note in Section 7.2 that processor exceptions are caught and the error string is returned (content is not silently dropped). | LOW |
| MC-2 | Rate limit reset timing | `check_rate_limit()` uses a rolling 1-minute window, but the error message says "Max N per minute" without specifying when the window resets. The implementation uses `datetime.utcnow() - timedelta(minutes=1)` which is correct (sliding window), but the user-facing message could include approximate wait time. **Recommendation:** Enhance error to say "Try again in N seconds" based on oldest request timestamp. | LOW |
| MC-3 | Cache stores raw vs. converted content | Section 7.5 correctly states the processor runs after caching, but the pipeline shows cache at step 3 and conversion at step 5. This means the cache stores the **raw HTML**, not the converted content. Different format requests for the same URL would require re-conversion from cached HTML. **Recommendation:** Add a clarifying note that cache stores raw HTML and conversion is applied on each cache hit. | LOW |
| MC-4 | Custom provider testing guidance | The test strategy covers `BraveSearchProvider` but doesn't provide guidance for users testing their own `SearchProvider` implementations. **Recommendation:** Add a `conftest.py` fixture or testing helper that validates any class conforming to the Protocol. | LOW |
| MC-5 | Thread safety via contextvars | The PRD uses `contextvars.ContextVar` which is inherently thread-safe for asyncio tasks, but this is not explicitly called out. **Recommendation:** Add a one-line note in Section 6.3 docstring stating that `contextvars` provides per-task isolation in asyncio. | LOW |

### 10.4 Optional Future Improvements

These are not blockers for implementation but could enhance the module later:

1. **Persistent disk cache**: For long-running agents, add optional SQLite-backed cache alongside in-memory
2. **Streaming fetch**: For very large pages, stream content and truncate early instead of buffering full response
3. **Retry backoff**: Exponential backoff with jitter for provider API retries (currently fixed retry count)
4. **Robots.txt respect**: Optional robots.txt checking before fetch (for polite crawling)
5. **Request logging/audit**: Structured audit log (similar to shell's ShellAuditLogger) for compliance
6. **Provider test helper**: A `validate_search_provider(provider)` function that runs conformance checks against the Protocol

---

## 11. Recommendation

**STATUS: APPROVED FOR IMPLEMENTATION**

The PRD v2.0 is a significant improvement over v1.1. The 5 architectural issues have been cleanly resolved:

1. **Single unified WebContext** eliminates the dual-config complexity and brings the web module into full consistency with the fs and shell module patterns.
2. **Brave-only built-in** with Protocol extensibility delivers exactly what the user requested: Brave by default, plug-and-play for custom providers.
3. **Lazy provider initialization** from `BRAVE_API_KEY` enables true zero-config usage (2 lines of code).
4. **ContentProcessor as a first-class citizen** provides the extensibility hook for post-fetch processing that was requested, without building anything in by default.
5. **Simplified project structure** (8 files + 1 provider) is easier to understand, maintain, and test.

The PRD provides ~930 lines of production-quality async Python implementation code across 8 source files, with comprehensive test definitions covering 33+ test cases across 8 test files plus fixtures.

**Implementation can begin immediately following the phased approach in Section 12.**

---

## Appendix: Complete Issue Tracking

### A. Version 1.0 → 1.1: Self-Evaluation Issues (21 issues, all resolved)

| # | Severity | Description | Fix Applied | Verified |
|---|----------|-------------|-------------|----------|
| 1 | CRITICAL | `contextvars` imported inside functions instead of module level | Moved all imports to module header | ✅ |
| 2 | CRITICAL | `get_web_security_context()` missing `allow_permissive` parameter | Added `allow_permissive: bool = True` with strict mode | ✅ |
| 3 | CRITICAL | `heading_style="underlined"` produces `====` headings; should be ATX | Changed to `heading_style="ATX"` | ✅ |
| 4 | CRITICAL | `CloudflareRetryTransport` method signature unclear (sync vs async) | Verified `async def handle_async_request()` is correct | ✅ |
| 5 | MAJOR | `socket.gethostbyname()` is synchronous and blocks the event loop | Wrapped in `asyncio.to_thread(_sync_resolve)` | ✅ |
| 6 | MAJOR | No thundering herd prevention in cache | Added `_in_flight` dict with `asyncio.Event` signaling | ✅ |
| 7 | MAJOR | `list[str] | None` type hint may not work with `@tool` schema gen | Documented `Annotated` wrapper requirement | ✅ |
| 8 | MAJOR | `socket` module imported inside method | Moved to module-level import | ✅ |
| 9 | MAJOR | Error hierarchy: `WebSecurityError` base class unclear | Confirmed `WebSecurityError(PermissionError)` matches fs/shell | ✅ |
| 10 | MAJOR | No strict mode for production | `allow_permissive=False` raises error | ✅ |
| 11 | MINOR | Provider auto-detection algorithm not specified | Added algorithm (later removed in v2.0) | ✅ |
| 12 | MINOR | No reference provider implementation | Added BraveSearchProvider | ✅ |
| 13 | MINOR | Cross-host redirect detection logic missing | Added Appendix D.1 | ✅ |
| 14 | MINOR | Encoding/charset handling undocumented | Added Appendix D.3 | ✅ |
| 15 | MINOR | Binary content type handling missing | Added Appendix D.2 | ✅ |
| 16 | MINOR | text/markdown passthrough not mentioned | Added Section 13.4 | ✅ |
| 17 | MINOR | HTTP client lifecycle/connection pooling unclear | Added shared client in `_http.py` | ✅ |
| 18 | MINOR | ToolExecutor registration not shown | Added Appendix D.4 | ✅ |
| 19 | MINOR | `builtin/__init__.py` update not shown | Added Section 11.2 | ✅ |
| 20 | MINOR | Rate limit scope ambiguous (per-context vs global) | Clarified: per-WebContext instance | ✅ |
| 21 | MINOR | No way to override auto-detection priority | Added env var (later removed in v2.0) | ✅ |

### B. Version 1.1 → 2.0: Architectural Issues (5 issues, all resolved)

| # | Severity | Description | Fix Applied | Verified |
|---|----------|-------------|-------------|----------|
| A1 | CRITICAL | Dual-config complexity: WebSecurityContext + WebConfig = two objects | Merged into single `WebContext` in `_context.py` | ✅ |
| A2 | HIGH | Over-shipping providers: Brave + Tavily + Exa built-in | Ship only Brave; others as documented Protocol examples | ✅ |
| A3 | HIGH | Auto-detection algorithm creates hidden behavior | Removed entirely; lazy `BRAVE_API_KEY` init on first call | ✅ |
| A4 | MEDIUM | ContentProcessor buried as optional subsection | Elevated to own Section 7 with 5 subsections | ✅ |
| A5 | MEDIUM | Zero-config path not simple enough | Section 1.3 quick start; auto-creates WebContext with defaults | ✅ |

### C. Summary

| Version | Issues Found | Issues Fixed | Remaining |
|---------|-------------|-------------|-----------|
| v1.0 → v1.1 | 21 (4 CRITICAL, 6 MAJOR, 11 MINOR) | 21 | 0 |
| v1.1 → v2.0 | 5 (1 CRITICAL, 2 HIGH, 2 MEDIUM) | 5 | 0 |
| v2.0 (final) | 5 minor clarifications (non-blocking) | N/A | 5 (LOW) |
| **Total** | **31** | **26 fixed** | **5 non-blocking** |

---

**End of Evaluation Report**
