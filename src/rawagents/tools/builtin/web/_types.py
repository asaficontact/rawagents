"""Type definitions for web tools.

This module defines the pluggable protocols that users can implement
to customize web search and content processing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


__all__ = [
    "ContentProcessor",
    "FetchError",
    "SearchError",
    "SearchProvider",
    "SearchResult",
]


@runtime_checkable
class SearchProvider(Protocol):
    """Protocol for pluggable search backends.

    Brave is shipped built-in. Users implement this Protocol to add
    custom providers (Tavily, Exa, Google, DuckDuckGo, etc.) in ~20 lines.

    Example:
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
                        SearchResult(title=r["title"], url=r["url"],
                                     snippet=r["content"], source="tavily")
                        for r in data["results"]
                    ]

            @property
            def name(self) -> str:
                return "tavily"
    """

    async def search(
        self,
        query: str,
        *,
        num_results: int = 10,
        allowed_domains: list[str] | None = None,
        blocked_domains: list[str] | None = None,
    ) -> list[SearchResult]:
        """Execute a web search.

        Args:
            query: The search query.
            num_results: Number of results to return (default 10, max 20).
            allowed_domains: If set, only return results from these domains.
            blocked_domains: If set, exclude results from these domains.

        Returns:
            List of SearchResult objects.

        Raises:
            SearchError: If the search fails.
        """
        ...

    @property
    def name(self) -> str:
        """Provider name for logging/identification."""
        ...


@runtime_checkable
class ContentProcessor(Protocol):
    """Protocol for optional post-fetch content processing.

    Implement this to add custom processing to web_fetch results.
    The processor runs AFTER HTML->Markdown conversion but BEFORE
    content truncation.

    Pipeline:
        HTTP fetch -> HTML conversion -> ContentProcessor -> Truncation -> Return

    Example:
        class MyProcessor:
            async def process(self, content, url, prompt, format):
                if "docs.python.org" in url:
                    return content  # Trusted -- skip processing
                return await extract_with_haiku(content, prompt)

        ctx = WebContext(content_processor=MyProcessor())
        set_web_context(ctx)
    """

    async def process(
        self,
        content: str,
        url: str,
        prompt: str,
        format: str,
    ) -> str:
        """Process fetched content before returning to the agent.

        Args:
            content: The fetched content (already converted to requested format).
            url: The URL that was fetched.
            prompt: The extraction prompt/context from web_fetch call.
            format: The output format ("markdown", "text", or "html").

        Returns:
            Processed content string.
        """
        ...


@dataclass
class SearchResult:
    """A single search result."""

    title: str
    url: str
    snippet: str
    source: str


class SearchError(Exception):
    """Raised when search provider returns an error."""

    pass


class FetchError(Exception):
    """Raised when web fetch fails."""

    pass
