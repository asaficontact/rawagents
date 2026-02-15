"""Shared HTTP client with Cloudflare retry logic.

Matches OpenCode's approach: retry with simplified UA on Cloudflare 403.
"""

from __future__ import annotations

import asyncio

import httpx


__all__ = [
    "CloudflareRetryTransport",
    "close_http_client",
    "get_http_client",
]


class CloudflareRetryTransport(httpx.AsyncHTTPTransport):
    """Retries with simplified UA on Cloudflare 403 + cf-mitigated header."""

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        response = await super().handle_async_request(request)

        if response.status_code == 403 and "cf-mitigated" in response.headers:
            request.headers["user-agent"] = "RawAgents/1.0"
            response = await super().handle_async_request(request)

        return response


# Module-level shared client for connection pooling
_http_client: httpx.AsyncClient | None = None
_http_lock = asyncio.Lock()


async def get_http_client(
    user_agent: str = "RawAgents/1.0 (+https://github.com/tawab-safi/rawagents)",
) -> httpx.AsyncClient:
    """Get or create shared async HTTP client."""
    global _http_client  # noqa: PLW0603
    async with _http_lock:
        if _http_client is None or _http_client.is_closed:
            transport = CloudflareRetryTransport()
            _http_client = httpx.AsyncClient(
                transport=transport,
                follow_redirects=False,
                headers={"user-agent": user_agent},
            )
        return _http_client


async def close_http_client() -> None:
    """Close the shared HTTP client."""
    global _http_client  # noqa: PLW0603
    async with _http_lock:
        if _http_client is not None and not _http_client.is_closed:
            await _http_client.aclose()
        _http_client = None
