"""Web tools for RawAgents.

Quick Start:
    # Set BRAVE_API_KEY env var, then:
    from rawagents.tools.builtin.web import web_search, web_fetch

    results = await web_search("python asyncio")
    content = await web_fetch("https://docs.python.org")

Custom Config:
    from rawagents.tools.builtin.web import WebContext, set_web_context

    ctx = WebContext(
        allowed_domains=["docs.python.org"],
        max_requests_per_minute=20,
    )
    set_web_context(ctx)

Custom Provider:
    from rawagents.tools.builtin.web import WebContext, set_web_context

    ctx = WebContext(search_provider=MyCustomProvider())
    set_web_context(ctx)

Custom Content Processing:
    from rawagents.tools.builtin.web import WebContext, set_web_context

    ctx = WebContext(content_processor=MyProcessor())
    set_web_context(ctx)
"""

# Unified Context
from rawagents.tools.builtin.web._context import (
    RateLimitExceededError,
    SSRFError,
    URLValidationError,
    WebContext,
    WebSecurityError,
    domain_matches,
    get_web_context,
    set_web_context,
)

# HTTP
from rawagents.tools.builtin.web._http import close_http_client

# Types and Protocols
from rawagents.tools.builtin.web._types import (
    ContentProcessor,
    FetchError,
    SearchError,
    SearchProvider,
    SearchResult,
)

# Built-in Provider
from rawagents.tools.builtin.web.providers import BraveSearchProvider

# Tools
from rawagents.tools.builtin.web.web_fetch import web_fetch
from rawagents.tools.builtin.web.web_search import web_search


__all__ = [
    "BraveSearchProvider",
    "ContentProcessor",
    "FetchError",
    "RateLimitExceededError",
    "SSRFError",
    "SearchError",
    "SearchProvider",
    "SearchResult",
    "URLValidationError",
    "WebContext",
    "WebSecurityError",
    "close_http_client",
    "domain_matches",
    "get_web_context",
    "set_web_context",
    "web_fetch",
    "web_search",
]
