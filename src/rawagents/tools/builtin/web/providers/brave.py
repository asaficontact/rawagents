"""Brave Search provider -- the built-in default.

Brave Search is the default provider, matching what Claude Code uses
under the hood. Free tier: 2,000 searches/month.

Requires: BRAVE_API_KEY environment variable
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

from rawagents.tools.builtin.web._context import domain_matches
from rawagents.tools.builtin.web._http import get_http_client
from rawagents.tools.builtin.web._types import SearchError, SearchResult


__all__ = ["BraveSearchProvider"]


class BraveSearchProvider:
    """Brave Search API provider.

    This is the only built-in provider. For other providers (Tavily, Exa,
    Google, etc.), implement the SearchProvider Protocol -- see _types.py
    docstring for a complete example.

    Args:
        api_key: Brave Search API key. Defaults to BRAVE_API_KEY env var.
    """

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.environ.get("BRAVE_API_KEY")
        if not self._api_key:
            raise SearchError(
                "BRAVE_API_KEY not set. Get a free key at https://brave.com/search/api/"
            )

    @property
    def name(self) -> str:
        return "brave"

    async def search(
        self,
        query: str,
        *,
        num_results: int = 10,
        allowed_domains: list[str] | None = None,
        blocked_domains: list[str] | None = None,
    ) -> list[SearchResult]:
        """Execute web search via Brave Search API."""
        import httpx  # noqa: PLC0415

        try:
            client = await get_http_client()
            response = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={
                    "q": query,
                    "count": min(num_results, 20),
                },
                headers={
                    "X-Subscription-Token": self._api_key,
                    "Accept": "application/json",
                },
                timeout=15.0,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            raise SearchError(
                f"Brave Search API error: HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SearchError(f"Brave Search request failed: {e}") from e

        # Parse results
        results: list[SearchResult] = []
        for item in data.get("web", {}).get("results", []):
            url = item.get("url", "")
            domain = _extract_domain(url)

            # Apply domain filtering
            if allowed_domains and not domain_matches(domain, allowed_domains):
                continue
            if blocked_domains and domain_matches(domain, blocked_domains):
                continue

            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=url,
                    snippet=item.get("description", ""),
                    source="brave",
                )
            )

        return results[:num_results]


def _extract_domain(url: str) -> str:
    """Extract domain from URL."""
    return urlparse(url).hostname or ""
