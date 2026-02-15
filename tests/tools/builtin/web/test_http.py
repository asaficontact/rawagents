"""Tests for HTTP client and Cloudflare retry transport."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import httpx

from rawagents.tools.builtin.web._http import (
    CloudflareRetryTransport,
    close_http_client,
    get_http_client,
)


class TestHTTPClient:
    """Test HTTP client creation and management."""

    async def test_client_creation(self) -> None:
        """get_http_client should return an AsyncClient."""
        # Ensure clean state
        await close_http_client()

        client = await get_http_client()
        assert isinstance(client, httpx.AsyncClient)
        assert not client.is_closed

        # Clean up
        await close_http_client()

    async def test_cloudflare_retry(self) -> None:
        """Should retry with simplified UA on 403 + cf-mitigated header."""
        transport = CloudflareRetryTransport()

        # Create mock responses
        blocked_response = httpx.Response(
            403,
            headers={"cf-mitigated": "challenge"},
            request=httpx.Request("GET", "https://example.com"),
        )
        success_response = httpx.Response(
            200,
            request=httpx.Request("GET", "https://example.com"),
        )

        with patch.object(
            httpx.AsyncHTTPTransport,
            "handle_async_request",
            new_callable=AsyncMock,
            side_effect=[blocked_response, success_response],
        ):
            request = httpx.Request("GET", "https://example.com")
            result = await transport.handle_async_request(request)
            assert result.status_code == 200

    async def test_singleton_behavior(self) -> None:
        """Multiple calls should return the same client."""
        await close_http_client()

        client1 = await get_http_client()
        client2 = await get_http_client()
        assert client1 is client2

        await close_http_client()

    async def test_cleanup(self) -> None:
        """close_http_client should close and reset the client."""
        await close_http_client()

        client = await get_http_client()
        assert not client.is_closed

        await close_http_client()
        # After close, getting a new client should create a new one
        client2 = await get_http_client()
        assert client2 is not client

        await close_http_client()

    async def test_concurrent_creation_uses_lock(self) -> None:
        """Concurrent calls should not create duplicate clients (H2)."""
        await close_http_client()

        # Launch multiple concurrent get_http_client calls
        results = await asyncio.gather(
            get_http_client(),
            get_http_client(),
            get_http_client(),
        )

        # All should return the same client instance
        assert results[0] is results[1]
        assert results[1] is results[2]

        await close_http_client()

    async def test_follow_redirects_disabled(self) -> None:
        """Client should have follow_redirects=False (C1)."""
        await close_http_client()

        client = await get_http_client()
        assert client.follow_redirects is False

        await close_http_client()
