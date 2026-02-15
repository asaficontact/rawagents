# Web Tools

The web module provides two tools -- `web_search` and `web_fetch` -- for searching and retrieving content from the internet. Both tools use a pluggable provider architecture defined through Python protocols, so you can swap in any search backend (Brave, Tavily, Exa, Google, DuckDuckGo) without changing calling code.

Zero-config usage requires only a `BRAVE_API_KEY` environment variable. For custom providers or tighter security, configure a `WebContext`.

```python
from rawagents.tools.builtin.web import web_search, web_fetch

results = await web_search("python asyncio")
content = await web_fetch("https://docs.python.org")
```

---

## Web Context

All web tool behaviour is controlled through a single `WebContext` dataclass, following the same context-variable pattern used by `SecurityContext` (filesystem) and `ShellSecurityContext` (shell).

```python
from rawagents.tools.builtin.web import WebContext, set_web_context

ctx = WebContext(
    allowed_domains=["docs.python.org", "github.com"],
    max_requests_per_minute=20,
)
set_web_context(ctx)
```

### Fields

#### Domain Filtering

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `allowed_domains` | `list[str]` | `[]` | If non-empty, only allow requests to these domains. |
| `blocked_domains` | `list[str]` | `[]` | Domains that are always blocked (e.g., internal networks). |

Domain matching uses exact match or subdomain suffix -- `"example.com"` matches both `example.com` and `sub.example.com` but not `not-example.com`.

#### SSRF Prevention

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `allow_localhost` | `bool` | `False` | Whether to allow localhost (`127.0.0.1`, `::1`). |
| `allow_private_ips` | `bool` | `False` | Whether to allow RFC 1918 private IPs (`10.x`, `172.16.x`, `192.168.x`). |

#### Response Limits

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_response_bytes` | `int` | `5242880` (5 MB) | Maximum HTTP response size before rejecting. |
| `max_content_chars` | `int` | `100000` (100K chars) | Maximum text content to return (content is truncated beyond this). |

#### Timeouts

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `default_timeout` | `int` | `30` | Default request timeout in seconds. |
| `max_timeout` | `int` | `120` | Maximum allowed request timeout in seconds. |

#### Rate Limiting

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_requests_per_minute` | `int` | `30` | Maximum web fetch requests per minute. |
| `max_search_per_minute` | `int` | `10` | Maximum search requests per minute. |

#### Provider

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `search_provider` | `SearchProvider \| None` | `None` | The search provider instance. If `None`, auto-creates `BraveSearchProvider` from the `BRAVE_API_KEY` env var at first search call. |

#### Content Processing

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `content_processor` | `ContentProcessor \| None` | `None` | Optional processor applied to fetched content before returning to the agent. Runs after HTML-to-format conversion but before truncation. |

#### Caching

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `cache_ttl` | `int` | `900` (15 min) | Cache time-to-live in seconds. Set to `0` to disable caching. |
| `cache_max_size` | `int` | `128` | Maximum number of URLs to keep in cache (LRU eviction). |

#### HTTP Client

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `user_agent` | `str` | `"RawAgents/1.0 (+https://github.com/tawab-safi/rawagents)"` | User-Agent header for HTTP requests. |
| `max_retries` | `int` | `2` | Number of retries for failed requests. |
| `retry_on_cloudflare` | `bool` | `True` | Whether to retry with a simplified UA when Cloudflare blocks. |

### Context Accessors

```python
from rawagents.tools.builtin.web import get_web_context, set_web_context, WebContext

# Set a context for the current async task
set_web_context(WebContext(allowed_domains=["example.com"]))

# Retrieve the current context (creates permissive defaults if none is set)
ctx = get_web_context()

# Clear the context
set_web_context(None)
```

`get_web_context(allow_permissive=True)` returns a default `WebContext()` when none has been set. Pass `allow_permissive=False` to raise `WebSecurityError` instead.

---

## Tool Reference

### `web_search`

Search the web using a pluggable search provider.

```python
@tool
async def web_search(
    query: Annotated[str, "The search query"],
    num_results: Annotated[int, "Number of results to return (max 20)"] = 10,
    allowed_domains: Annotated[
        list[str] | None, "Only return results from these domains"
    ] = None,
    blocked_domains: Annotated[
        list[str] | None, "Exclude results from these domains"
    ] = None,
) -> str:
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | `str` | required | The search query. |
| `num_results` | `int` | `10` | Number of results to return. Clamped to a maximum of 20. |
| `allowed_domains` | `list[str] \| None` | `None` | If set, only return results from these domains. |
| `blocked_domains` | `list[str] \| None` | `None` | If set, exclude results from these domains. |

**Behaviour:**

- Returns numbered results in markdown format.
- By default uses Brave Search (requires `BRAVE_API_KEY` env var), or a custom provider set on `WebContext.search_provider`.
- `allowed_domains` and `blocked_domains` are mutually exclusive -- passing both returns an error.
- Subject to the `max_search_per_minute` rate limit (default 10/min).

**Example:**

```python
results = await web_search("python asyncio tutorial", num_results=5)
results = await web_search("site search", allowed_domains=["docs.python.org"])
```

### `web_fetch`

Fetch a web page and return its content.

```python
@tool
async def web_fetch(
    url: Annotated[str, "The URL to fetch (must start with http:// or https://)"],
    prompt: Annotated[str, "Context for what to extract"] = "",
    format: Annotated[str, "Output format: markdown, text, or html"] = "markdown",
    timeout: Annotated[int, "Request timeout in seconds (max 120)"] = 30,
) -> str:
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | `str` | required | The URL to fetch. Must start with `http://` or `https://`. |
| `prompt` | `str` | `""` | Context describing what to extract. Passed to the `ContentProcessor` if one is configured. |
| `format` | `str` | `"markdown"` | Output format: `"markdown"`, `"text"`, or `"html"`. |
| `timeout` | `int` | `30` | Request timeout in seconds. Clamped between 1 and `max_timeout` (default 120). |

**Behaviour:**

- Validates the URL scheme (http/https only) and hostname against domain allow/block lists.
- Performs SSRF prevention by resolving the hostname and blocking private, loopback, link-local, and reserved IP addresses (unless `allow_localhost` or `allow_private_ips` is enabled).
- Follows redirects manually (up to 5 hops), validating each redirect target for SSRF.
- Rejects binary content types (images, audio, video, PDFs, archives).
- Streams the response body and enforces `max_response_bytes` (default 5 MB).
- Converts HTML to the requested format (markdown by default). Text and markdown content types (`text/plain`, `text/markdown`) skip HTML conversion.
- Runs the `ContentProcessor` pipeline if one is configured on the `WebContext`.
- Truncates output to `max_content_chars` (default 100K characters).
- Caches raw fetched content with a TTL of `cache_ttl` (default 15 minutes) and an LRU eviction policy capped at `cache_max_size` (default 128 entries). Set `cache_ttl=0` to disable caching.
- Subject to the `max_requests_per_minute` rate limit (default 30/min).

**Content processing pipeline:**

```
HTTP fetch -> HTML conversion -> ContentProcessor -> Truncation -> Return
```

**Example:**

```python
content = await web_fetch("https://docs.python.org/3/library/asyncio.html")
content = await web_fetch(
    "https://example.com/article",
    prompt="Extract the main article text",
    format="text",
    timeout=60,
)
```

---

## Protocols

The web module defines two protocols for pluggable behaviour. Both are `@runtime_checkable`.

### `SearchProvider`

```python
@runtime_checkable
class SearchProvider(Protocol):

    async def search(
        self,
        query: str,
        *,
        num_results: int = 10,
        allowed_domains: list[str] | None = None,
        blocked_domains: list[str] | None = None,
    ) -> list[SearchResult]: ...

    @property
    def name(self) -> str: ...
```

| Method | Description |
|--------|-------------|
| `search(query, *, num_results, allowed_domains, blocked_domains)` | Execute a web search and return a list of `SearchResult`. Raises `SearchError` on failure. |
| `name` (property) | Provider name for logging and identification. |

### `ContentProcessor`

```python
@runtime_checkable
class ContentProcessor(Protocol):

    async def process(
        self,
        content: str,
        url: str,
        prompt: str,
        format: str,
    ) -> str: ...
```

| Method | Description |
|--------|-------------|
| `process(content, url, prompt, format)` | Process fetched content before returning to the agent. Receives content already converted to the requested format. The `format` parameter is one of `"markdown"`, `"text"`, or `"html"`. |

### `SearchResult`

```python
@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str
```

| Field | Type | Description |
|-------|------|-------------|
| `title` | `str` | Result title. |
| `url` | `str` | Result URL. |
| `snippet` | `str` | Short description or excerpt. |
| `source` | `str` | Provider name that produced this result (e.g., `"brave"`). |

---

## Custom Provider Example

Implement the `SearchProvider` protocol to plug in any search backend. The Tavily example below is taken from the `_types.py` module docstring:

```python
from rawagents.tools.builtin.web import (
    SearchProvider,
    SearchResult,
    WebContext,
    set_web_context,
)


class TavilySearchProvider:
    def __init__(self, api_key: str):
        self._api_key = api_key

    async def search(
        self,
        query: str,
        *,
        num_results: int = 10,
        allowed_domains: list[str] | None = None,
        blocked_domains: list[str] | None = None,
    ) -> list[SearchResult]:
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={"query": query, "max_results": num_results},
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            data = response.json()
            return [
                SearchResult(
                    title=r["title"],
                    url=r["url"],
                    snippet=r["content"],
                    source="tavily",
                )
                for r in data["results"]
            ]

    @property
    def name(self) -> str:
        return "tavily"


# Wire it up
ctx = WebContext(search_provider=TavilySearchProvider(api_key="tvly-..."))
set_web_context(ctx)
```

You can verify protocol conformance at runtime:

```python
assert isinstance(TavilySearchProvider("key"), SearchProvider)
```

---

## Built-in Providers

### `BraveSearchProvider`

The only built-in provider. Brave Search offers a free tier of 2,000 searches per month.

```python
from rawagents.tools.builtin.web.providers.brave import BraveSearchProvider
```

**Constructor:**

```python
class BraveSearchProvider:
    def __init__(self, api_key: str | None = None): ...
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | `str \| None` | `None` | Brave Search API key. Falls back to the `BRAVE_API_KEY` environment variable if `None`. Raises `SearchError` if neither is available. |

**Configuration:**

1. Set the `BRAVE_API_KEY` environment variable (recommended). The provider is auto-created on first search call when no explicit `search_provider` is set on the `WebContext`.
2. Or pass the key explicitly:

```python
from rawagents.tools.builtin.web import WebContext, set_web_context
from rawagents.tools.builtin.web.providers.brave import BraveSearchProvider

ctx = WebContext(search_provider=BraveSearchProvider(api_key="BSA..."))
set_web_context(ctx)
```

Get a free API key at <https://brave.com/search/api/>.

---

## Error Classes

All errors inherit from `WebSecurityError`, which itself extends `PermissionError`.

| Class | When Raised |
|-------|-------------|
| `WebSecurityError` | Base class for all web security errors. Has `url` and `reason` attributes. |
| `URLValidationError` | URL parsing failed, scheme is not http/https, domain is blocked, or domain is not in the allow list. |
| `SSRFError` | Hostname resolves to a private, loopback, link-local, or reserved IP address. |
| `RateLimitExceededError` | The per-minute rate limit for fetch or search operations has been exceeded. |

The tool functions catch these exceptions and return `"Error: ..."` strings rather than propagating them, following the standard RawAgents tool error convention.

Two additional exceptions are defined in `_types.py` for provider-level errors:

| Class | When Raised |
|-------|-------------|
| `SearchError` | A search provider encountered an error (API failure, missing key, etc.). |
| `FetchError` | A web fetch operation failed. |

---

## Exports

Everything is available from the top-level package import:

```python
from rawagents.tools.builtin.web import (
    # Tools
    web_search,
    web_fetch,
    # Context
    WebContext,
    get_web_context,
    set_web_context,
    # Protocols and types
    SearchProvider,
    ContentProcessor,
    SearchResult,
    # Built-in provider
    BraveSearchProvider,
    # Errors
    WebSecurityError,
    URLValidationError,
    SSRFError,
    RateLimitExceededError,
    SearchError,
    FetchError,
    # Utilities
    domain_matches,
    close_http_client,
)
```
