# Web Tools for Raw Agents — Research & Design Document

**Date:** February 8, 2026
**Scope:** WebSearch and WebFetch tool implementation strategy

---

## 1. How Claude Code Implements Web Tools

### 1.1 WebSearch — Architecture

Claude Code's WebSearch is **server-side**. It does not call a search API directly from the client. Instead:

1. The main Claude Code conversation (running Sonnet/Opus) encounters a `WebSearch` tool call
2. Claude Code spawns a **secondary conversation with Claude Opus** on Anthropic's servers
3. That secondary conversation calls Anthropic's built-in `web_search_20250305` server-side tool
4. The server-side tool calls **Brave Search** under the hood (confirmed by TechCrunch — 86.7% result overlap with Brave)
5. Results come back to the main conversation as structured `web_search_result` objects

**Parameters:**
- `query` (string): The search query
- `allowed_domains` (string[]): Only include results from these domains
- `blocked_domains` (string[]): Exclude results from these domains
- Cannot use both `allowed_domains` and `blocked_domains` simultaneously

**Output format:** Array of objects, each containing:
- `title`: Search result title
- `url`: Webpage URL
- `encrypted_content`: Encrypted content blob (prevents using the API as free web scraping)
- `page_age`: When the site was last crawled
- Citation objects with `encrypted_index` references

**Pricing:** $10 per 1,000 searches ($0.01/search) + standard token costs

**Key insight:** Claude Code's WebSearch is deeply integrated with Anthropic's infrastructure. The content encryption prevents third parties from using the search API as a free scraping service. This architecture is **not replicable** by third-party frameworks like Raw Agents — we need a different approach.

### 1.2 WebFetch — Architecture

Claude Code's WebFetch is **client-side**. Unlike WebSearch, it runs locally:

1. **Fetches HTML** using **Axios** HTTP client (plain HTTP, no JavaScript rendering)
2. **Converts HTML → Markdown** using **Turndown** (a JavaScript HTML-to-Markdown library)
3. **Trusted site check**: ~80 hardcoded documentation sites (python.org, react.dev, github.com, etc.)
   - If the site is trusted AND Content-Type is `text/markdown` AND content < 100K chars → **bypass AI processing entirely**, pass content directly to the main model
4. **Non-trusted sites**: Content goes through a **secondary conversation with Claude Haiku 4.5**
   - Haiku receives the markdown + the user's original question
   - Haiku extracts only the relevant information
   - Only the distilled output goes back to the main conversation (preserves context window)
5. **Copyright protection**: Non-trusted sites have a 125-character maximum for verbatim quotes

**Parameters:**
- `url` (string): The URL to fetch
- `prompt` (string): What information to extract from the page

**Limits:**
- 10 MB max fetch size
- 100 KB text truncation limit
- 15-minute URL cache (TTL)
- No JavaScript rendering (Axios is a plain HTTP client)
- Cross-host redirects are flagged, not followed automatically

**Key insight:** The two-model architecture (Haiku for extraction, Sonnet/Opus for reasoning) is clever for cost optimization but adds significant complexity. The trusted-sites shortcut is pragmatic. No JS rendering is a real limitation.

---

## 2. How OpenCode Implements Web Tools

### 2.1 WebSearch

OpenCode calls **Exa AI** via their MCP (Model Context Protocol) endpoint.

```typescript
const API_CONFIG = {
  BASE_URL: "https://mcp.exa.ai",
  ENDPOINTS: { SEARCH: "/mcp" },
  DEFAULT_NUM_RESULTS: 8,
}
```

**Parameters (Zod schema):**
- `query` (string, required): Search query
- `numResults` (number, optional, default 8): Number of results
- `livecrawl` (enum, optional): "fallback" | "preferred" — whether to live-crawl pages
- `type` (enum, optional): "auto" | "fast" | "deep" — search depth
- `contextMaxCharacters` (number, optional): Max characters for context optimization

**Execution flow:**
1. Request permission from user (via permission system)
2. POST a JSON-RPC request to `https://mcp.exa.ai/mcp` with method `tools/call` and tool name `web_search_exa`
3. Parse SSE (Server-Sent Events) response
4. Return first matching content with text and title
5. 25-second timeout

**Key insight:** OpenCode's approach is simple — a single HTTP call to Exa's MCP endpoint. No secondary model, no encrypted content. Results come back as plain text. The SSE parsing is a minor complexity. This is much simpler than Claude Code's architecture.

### 2.2 WebFetch

OpenCode uses **fetch + Turndown** (same Turndown library as Claude Code):

```typescript
const MAX_RESPONSE_SIZE = 5 * 1024 * 1024  // 5MB
const DEFAULT_TIMEOUT = 30 * 1000           // 30 seconds
const MAX_TIMEOUT = 120 * 1000              // 2 minutes
```

**Parameters (Zod schema):**
- `url` (string, required): The URL to fetch
- `format` (enum, optional): "text" | "markdown" | "html" — defaults to "markdown"
- `timeout` (number, optional): Seconds, capped at 120

**Execution flow:**
1. Validate URL starts with `http://` or `https://`
2. Request user permission with URL pattern
3. Fetch with appropriate Accept headers based on format
4. If Cloudflare blocks (403 + `cf-mitigated` header) → retry with simplified User-Agent
5. Check response size against 5MB limit
6. Convert based on format:
   - **markdown**: HTML → Turndown → Markdown; plain text passes through
   - **text**: HTML → HTMLRewriter text extraction; others pass through
   - **html**: Raw content returned as-is

**Turndown configuration:**
- Heading style: ATX (`#` syntax)
- Horizontal rule: `---`
- Bullet marker: `-`
- Code blocks: Fenced
- Removes: script, style, meta, link elements

**Key insight:** OpenCode's WebFetch is straightforward — no secondary model processing, no content summarization. It returns the full converted content directly to the main model. Simpler, but uses more context window. The Cloudflare retry is a nice touch.

---

## 3. Side-by-Side Comparison

| Aspect | Claude Code | OpenCode |
|--------|------------|----------|
| **Search provider** | Brave (via Anthropic servers) | Exa AI (direct API) |
| **Search architecture** | Server-side, encrypted results | Client-side, plain text |
| **Search cost** | $0.01/search | ~$0.005/search (Exa) |
| **Fetch HTTP client** | Axios (JavaScript) | fetch API (JavaScript) |
| **HTML→Markdown** | Turndown | Turndown |
| **Content processing** | Haiku 4.5 for extraction | None — returns full content |
| **Trusted sites bypass** | Yes (~80 sites) | No |
| **Caching** | 15-min TTL per URL | None visible |
| **JS rendering** | No | No |
| **Max fetch size** | 10 MB | 5 MB |
| **Content truncation** | 100 KB | None visible (5MB raw limit) |
| **Output format options** | markdown only | markdown / text / html |
| **Cross-host redirects** | Flagged, user must approve | Not explicitly handled |
| **Cloudflare bypass** | Not visible | Retry with simplified UA |
| **Copyright protection** | 125-char quote limit via Haiku | None |

**Key differences:**
1. **Claude Code is more complex** — two-model architecture, encrypted content, trusted site lists, copyright enforcement. This is enterprise-grade but impossible to replicate exactly.
2. **OpenCode is simpler** — direct API calls, full content return, no secondary model. Easier to implement and maintain.
3. **Both use Turndown** for HTML→Markdown, confirming it's the industry standard for this conversion.
4. **Neither supports JavaScript rendering** — both are limited to static HTML.

---

## 4. Implementation Options for Raw Agents

### 4.1 WebSearch — Provider Options

#### Option A: Tavily (Purpose-built for AI agents)

**Pros:**
- Built specifically for AI/RAG use cases — returns pre-processed, LLM-friendly content
- Aggregates content from up to 20 sources per query
- Python SDK available (`tavily-python`)
- Search + Extract in one API (can also extract content from URLs)
- 1,000 free credits/month
- Used widely in LangChain, LlamaIndex, CrewAI ecosystems

**Cons:**
- Credits don't roll over monthly
- $30/month for just 4,000 credits (expensive at moderate scale)
- Lock-in to proprietary API
- Can't self-host

**Pricing:** Free: 1,000 credits/mo → $30/mo: 4,000 → $100 add-on: 8,000 (no expiry) → PAYG: $0.008/credit

#### Option B: Exa AI (What OpenCode uses)

**Pros:**
- Semantic/neural search — understands meaning, not just keywords
- Excellent for code and documentation queries
- MCP endpoint available (JSON-RPC)
- 2,000 free searches (one-time, no expiry)
- `livecrawl` option for real-time content
- Fast: ~1.18s average response time

**Cons:**
- More complex pricing (varies by endpoint and result count)
- 5x price jump when requesting 26-100 results per query
- No official Python SDK (HTTP calls only)
- Newer company, less ecosystem adoption than Tavily

**Pricing:** ~$5/1K queries base → Free: 2,000 one-time searches

#### Option C: Brave Search API (What Claude Code uses under the hood)

**Pros:**
- Powers Claude Code's search — proven quality
- 2,000 free searches/month (ongoing, not one-time)
- Independent search index (not scraping Google)
- Straightforward REST API
- Good privacy posture
- MCP server available

**Cons:**
- Free tier limited to 1 req/s
- Returns links + snippets, not full content (need WebFetch to get content)
- $5/1K for Base AI, $9/1K for Pro AI
- Less AI-specific than Tavily or Exa

**Pricing:** Free: 2,000/mo @ 1 req/s → Base AI: $5/1K → Pro AI: $9/1K

#### Option D: DuckDuckGo (Free, no API key)

**Pros:**
- Completely free, no API key needed
- Python library: `duckduckgo-search` (pip install)
- Works immediately out of the box
- Privacy-focused
- `ddgs` metasearch library aggregates DDG + Bing + Yahoo

**Cons:**
- Unofficial — violates DDG's ToS for commercial use
- No guaranteed uptime or SLA
- Rate-limited (unclear limits, can get blocked)
- Lower quality results than purpose-built AI search
- No content extraction — returns links + snippets only
- Could break at any time

**Pricing:** Free (but legally questionable for commercial use)

#### Option E: SearXNG (Self-hosted, fully free)

**Pros:**
- Completely free and open source
- Self-hosted — full control, no API keys, no rate limits
- Aggregates from 70+ search engines (Google, Bing, Brave, etc.)
- JSON API endpoint
- LiteLLM already has SearXNG integration
- Can run in Docker with minimal resources (512MB RAM)
- Privacy-first — no tracking

**Cons:**
- Requires self-hosting (Docker setup)
- Results quality depends on underlying engines
- If you're the only user, your searches may be identifiable
- Public instances are rate-limited and unreliable
- More DevOps overhead

**Pricing:** Free (infrastructure costs only)

#### Option F: Provider-Agnostic / Pluggable (Recommended)

**Architecture:** Define a `SearchProvider` protocol (Python Protocol/ABC), then implement adapters for multiple providers. The user configures which provider to use via environment variables or configuration.

```
SearchProvider protocol
├── TavilyProvider
├── ExaProvider
├── BraveProvider
├── DuckDuckGoProvider
├── SearXNGProvider
└── Custom (user-defined)
```

**Pros:**
- No lock-in to any single provider
- Users choose based on their needs (free vs. quality vs. self-hosted)
- Consistent tool interface regardless of backend
- Follows Raw Agents' existing pattern of dependency injection
- Can default to a free option (Brave free tier or DDG) and upgrade

**Cons:**
- More code to write and maintain
- Need to normalize different response formats
- Testing across multiple providers

---

### 4.2 WebFetch — Implementation Options

#### Option A: httpx + markdownify (Pure Python, recommended)

**Pros:**
- `httpx` is the modern async HTTP client for Python (already common in the ecosystem)
- `markdownify` is the Python equivalent of Turndown — most popular HTML→Markdown library
- Both are well-maintained, pure Python
- httpx supports async natively (matches Raw Agents' async-first architecture)
- No external service dependency
- `trafilatura` can be used as a secondary option for intelligent content extraction (removes boilerplate)

**Cons:**
- No JavaScript rendering
- Need to handle encoding, redirects, timeouts manually (httpx handles most)
- markdownify output may need post-processing

**New dependencies:** `httpx`, `markdownify` (minimal additions)

#### Option B: Jina Reader API (External service)

**Pros:**
- Extremely simple: prepend `https://r.jina.ai/` to any URL
- Uses ReaderLM-v2 (1.5B model) for intelligent HTML→Markdown
- Handles complex pages better than rule-based conversion
- Free tier: 20 req/min without API key, 200 req/min with key
- Also handles PDFs

**Cons:**
- External dependency — service could go down or change pricing
- Pro tier: ~$5/1K extractions
- ReaderLM-v2 mode costs 3x tokens
- Adds latency (network round-trip to Jina servers)
- Less control over conversion behavior

#### Option C: Firecrawl (External service, premium)

**Pros:**
- Highest extraction quality (98% accuracy claimed)
- Handles JavaScript-rendered content
- AI-powered extraction with schema support
- Handles anti-bot protection

**Cons:**
- Expensive: $16-$333+/month
- Overkill for basic web fetching
- External dependency
- Credit-based pricing adds complexity

#### Option D: httpx + trafilatura (Pure Python, content-focused)

**Pros:**
- `trafilatura` is specifically designed for web content extraction
- Intelligent boilerplate removal (strips nav, ads, footers)
- Supports markdown output natively (`output_format='markdown'`)
- Handles metadata extraction (title, author, date)
- Can serve as a "smart" alternative to simple HTML→Markdown

**Cons:**
- Heavier dependency than markdownify
- May strip content too aggressively in some cases
- Less control over exact markdown formatting

#### Option E: httpx + markdownify + optional Haiku processing (Claude Code style)

**Pros:**
- Closest to Claude Code's architecture
- Uses a small/fast model to extract relevant content
- Preserves context window of the main agent
- Can leverage LiteLLM (already a dependency) to call any small model

**Cons:**
- Significantly more complex
- Adds latency (LLM call for every fetch)
- Adds cost (even Haiku costs $1/M input tokens)
- May over-extract or under-extract

---

### 4.3 WebSearch Architecture Options for Raw Agents

#### Architecture 1: Simple (OpenCode style)

```
User query → WebSearch tool → Search API → return results
```

- One HTTP call to search provider
- Returns results directly to the main model
- No secondary model processing

**Best for:** Simplicity, low latency, minimal cost

#### Architecture 2: Search + Auto-fetch (Tavily style)

```
User query → WebSearch tool → Search API (returns content) → return results with content
```

- Tavily's search already returns aggregated content from top results
- No separate fetch step needed for basic research
- WebFetch only needed when user has a specific URL

**Best for:** Research-heavy use cases, RAG applications

#### Architecture 3: Two-tier (Claude Code style)

```
User query → WebSearch tool → Search API → results
                                              ↓
                              (optional) Small model → summarized results
```

- Search returns links + snippets
- Optionally process through a small model for summarization
- Main model gets distilled results

**Best for:** Context window optimization at scale

---

## 5. Recommendation for Raw Agents

### 5.1 Recommended Approach: Provider-Agnostic with Smart Defaults

**WebSearch:**
- Implement a `SearchProvider` protocol with pluggable backends
- Ship with 3 built-in providers: **Brave** (default free), **Tavily**, **Exa**
- Default to Brave Search (2,000 free searches/month, proven quality — it's what Claude Code uses)
- User selects provider via environment variable: `RAWAGENTS_SEARCH_PROVIDER=brave|tavily|exa`
- API keys via standard env vars: `BRAVE_API_KEY`, `TAVILY_API_KEY`, `EXA_API_KEY`
- Architecture 1 (Simple) — direct results, no secondary model processing. Keep it lean.

**WebFetch:**
- Use **httpx** for async HTTP fetching (aligns with Raw Agents' async-first design)
- Use **markdownify** as the primary HTML→Markdown converter (Python equivalent of Turndown)
- Optionally use **trafilatura** as a "smart" extraction backend (user-configurable)
- Implement a 15-minute in-memory cache (matching Claude Code's approach)
- 5 MB max response size, 100 KB text truncation
- Support 3 output formats: markdown (default), text, html
- Handle Cloudflare retry (simplified User-Agent on 403)
- No secondary model processing — keep it simple like OpenCode

### 5.2 Recommended Tool Signatures

**`web_search` tool:**
```python
@tool
async def web_search(
    query: str,                           # Search query
    num_results: int = 8,                 # Number of results
    allowed_domains: list[str] | None,    # Domain whitelist
    blocked_domains: list[str] | None,    # Domain blacklist
) -> str:
    """Search the web for current information."""
```

**`web_fetch` tool:**
```python
@tool
async def web_fetch(
    url: str,                             # URL to fetch
    prompt: str = "",                     # What to extract (for description; not processed)
    format: Literal["markdown", "text", "html"] = "markdown",
    timeout: int = 30,                    # Seconds, max 120
) -> str:
    """Fetch and read web page content."""
```

### 5.3 Recommended Module Structure

```
src/rawagents/tools/builtin/web/
├── __init__.py               # Exports web_search, web_fetch
├── web_search.py             # WebSearch tool
├── web_fetch.py              # WebFetch tool
├── _providers/               # Search provider implementations
│   ├── __init__.py
│   ├── base.py               # SearchProvider protocol
│   ├── brave.py              # Brave Search adapter
│   ├── tavily.py             # Tavily adapter
│   └── exa.py                # Exa adapter
├── _conversion.py            # HTML→Markdown conversion utilities
├── _cache.py                 # URL response caching (15-min TTL)
└── _security.py              # URL validation, domain filtering, size limits
```

### 5.4 New Dependencies

Required additions to `pyproject.toml`:
```toml
dependencies = [
    # ... existing ...
    "httpx>=0.27.0,<1.0.0",        # Async HTTP client (for web_fetch + API calls)
    "markdownify>=0.14.0,<1.0.0",  # HTML→Markdown conversion
]

[project.optional-dependencies]
web = [
    "trafilatura>=2.0.0",  # Optional: intelligent content extraction
    "tavily-python>=0.5.0",  # Optional: Tavily SDK
]
```

### 5.5 Why This Approach

1. **Provider-agnostic search** — follows the same philosophy as LiteLLM (which Raw Agents already uses). Don't lock users into one search provider. Some users want free (Brave), some want AI-optimized (Tavily), some want semantic (Exa).

2. **httpx over aiohttp/requests** — httpx is the modern standard for async Python HTTP. It's what FastAPI and other modern frameworks use. aiohttp is older and has a larger API surface. requests is sync-only.

3. **markdownify over Turndown** — Turndown is JavaScript; Raw Agents is Python. markdownify is the closest Python equivalent and is the most popular Python HTML→Markdown library. It supports subclassing for customization.

4. **No secondary model processing** — Claude Code's Haiku extraction is clever but adds complexity, latency, and cost. Raw Agents should start simple (like OpenCode) and let users optionally add processing later. The main model is capable of reading raw markdown.

5. **Cache** — 15-minute TTL matches Claude Code. Prevents hammering the same URL during iterative research. In-memory cache is fine for single-session use.

6. **Brave as default** — it's what powers Claude Code's search, has a generous ongoing free tier (2,000/month), and the quality is proven. Users can upgrade to Tavily or Exa if they need more.

---

## 6. Implementation Complexity Estimate

| Component | Effort | Files |
|-----------|--------|-------|
| `SearchProvider` protocol + base | Low | 1 file |
| Brave provider | Medium | 1 file |
| Tavily provider | Low | 1 file (SDK does the work) |
| Exa provider | Medium | 1 file |
| `web_search` tool | Low | 1 file |
| `web_fetch` tool | Medium | 1 file |
| HTML→Markdown conversion | Low | 1 file |
| URL caching | Low | 1 file |
| Security (URL validation, domain filtering) | Medium | 1 file |
| Tests | Medium | 3-4 files |
| **Total** | **~3-5 days** | **~12 files** |

---

## 7. Key Sources

- [Inside Claude Code's Web Tools — Mikhail Shilkov](https://mikhail.io/2025/10/claude-code-web-tools/)
- [Reverse Engineering Claude Code Web Tools — Liran Yoffe](https://medium.com/@liranyoffe/reverse-engineering-claude-code-web-tools-1409249316c3)
- [How Claude Code Eats the Web — Giuseppe Gurgone](https://giuseppegurgone.com/claude-webfetch)
- [Anthropic Web Search Tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)
- [Anthropic Web Fetch Tool docs](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/web-fetch-tool)
- [Brave Search API](https://brave.com/search/api/)
- [Tavily Pricing](https://www.tavily.com/pricing)
- [Exa AI Pricing](https://exa.ai/pricing)
- [OpenCode WebSearch source](https://github.com/anomalyco/opencode/blob/dev/packages/opencode/src/tool/websearch.ts)
- [OpenCode WebFetch source](https://github.com/anomalyco/opencode/blob/dev/packages/opencode/src/tool/webfetch.ts)
- [Jina Reader API](https://jina.ai/reader/)
- [Firecrawl](https://www.firecrawl.dev/pricing)
- [markdownify (Python)](https://github.com/matthewwithanm/python-markdownify)
- [trafilatura (Python)](https://trafilatura.readthedocs.io/)
- [Brave + Anthropic — TechCrunch](https://techcrunch.com/2025/03/21/anthropic-appears-to-be-using-brave-to-power-web-searches-for-its-claude-chatbot/)
- [SERP API Comparison 2025 — DEV Community](https://dev.to/ritza/best-serp-api-comparison-2025-serpapi-vs-exa-vs-tavily-vs-scrapingdog-vs-scrapingbee-2jci)
- [Tavily Alternatives — WebSearchAPI](https://websearchapi.ai/blog/tavily-alternatives)
