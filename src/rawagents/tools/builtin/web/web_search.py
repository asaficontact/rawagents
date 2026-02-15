"""Web search tool for RawAgents.

Dispatches to a pluggable SearchProvider (Brave built-in, or custom).
"""

from __future__ import annotations

import os
from typing import Annotated

from rawagents.tools import tool
from rawagents.tools.builtin.web._context import (
    RateLimitExceededError,
    get_web_context,
)
from rawagents.tools.builtin.web._types import SearchError


__all__ = ["web_search"]


@tool
async def web_search(  # noqa: PLR0911
    query: Annotated[str, "The search query"],
    num_results: Annotated[int, "Number of results to return (max 20)"] = 10,
    allowed_domains: Annotated[
        list[str] | None, "Only return results from these domains"
    ] = None,
    blocked_domains: Annotated[
        list[str] | None, "Exclude results from these domains"
    ] = None,
) -> str:
    """Search the web using a pluggable search provider.

    Returns numbered results in markdown format. By default uses Brave Search
    (requires BRAVE_API_KEY env var), or a custom provider via WebContext.
    """
    # Normalize and validate query
    query = query.strip()
    if not query:
        return "Error: Search query cannot be empty"

    # Reject if both domain lists specified
    if allowed_domains and blocked_domains:
        return "Error: Cannot use both allowed_domains and blocked_domains"

    # Get context and check rate limit
    ctx = get_web_context()
    try:
        ctx.check_rate_limit("search")
    except RateLimitExceededError as e:
        return str(e)

    # Get provider: from context or auto-create Brave
    provider = ctx.search_provider
    if provider is None:
        # Try to auto-create BraveSearchProvider from env
        brave_key = os.environ.get("BRAVE_API_KEY")
        if not brave_key:
            return (
                "Error: No search provider configured. Set BRAVE_API_KEY "
                "environment variable, or pass a custom SearchProvider to WebContext."
            )
        try:
            from rawagents.tools.builtin.web.providers.brave import (  # noqa: PLC0415
                BraveSearchProvider,
            )

            provider = BraveSearchProvider(api_key=brave_key)
        except SearchError as e:
            return f"Error: {e}"

    # Execute search
    try:
        results = await provider.search(
            query,
            num_results=min(num_results, 20),
            allowed_domains=allowed_domains,
            blocked_domains=blocked_domains,
        )
    except SearchError as e:
        return f"Error: Search failed: {e}"
    except Exception as e:
        return f"Error: Unexpected search error: {e}"

    # Format results
    if not results:
        return "No results found."

    lines: list[str] = [f"Found {len(results)} results for '{query}':\n"]
    for i, result in enumerate(results, 1):
        lines.append(f"{i}. [{result.title}]({result.url})")
        if result.snippet:
            lines.append(f"   {result.snippet}")
        lines.append("")

    return "\n".join(lines).strip()
