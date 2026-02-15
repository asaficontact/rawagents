"""Tests for BraveSearchProvider."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from rawagents.tools.builtin.web._types import SearchError, SearchResult
from rawagents.tools.builtin.web.providers.brave import BraveSearchProvider


def _make_brave_response(results: list[dict] | None = None) -> MagicMock:
    """Create a mock Brave API response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"web": {"results": results or []}}
    return mock_response


class TestBraveSearchProvider:
    """Test BraveSearchProvider behavior."""

    async def test_successful_search(self) -> None:
        """Successful search should return SearchResult list."""
        mock_response = _make_brave_response(
            [
                {
                    "title": "Python Docs",
                    "url": "https://docs.python.org",
                    "description": "Official Python documentation",
                },
            ]
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch(
            "rawagents.tools.builtin.web.providers.brave.get_http_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            provider = BraveSearchProvider(api_key="test-key")
            results = await provider.search("python docs")

        assert len(results) == 1
        assert results[0].title == "Python Docs"
        assert results[0].source == "brave"

    async def test_missing_api_key(self) -> None:
        """Should raise SearchError when no API key available."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove BRAVE_API_KEY if it exists
            env = dict(os.environ)
            env.pop("BRAVE_API_KEY", None)
            with (
                patch.dict(os.environ, env, clear=True),
                pytest.raises(SearchError, match="BRAVE_API_KEY"),
            ):
                BraveSearchProvider()

    async def test_api_error_429(self) -> None:
        """HTTP 429 should raise SearchError."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Rate limited",
            request=MagicMock(),
            response=mock_response,
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch(
            "rawagents.tools.builtin.web.providers.brave.get_http_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            provider = BraveSearchProvider(api_key="test-key")
            with pytest.raises(SearchError, match="HTTP 429"):
                await provider.search("test")

    async def test_request_error(self) -> None:
        """Network error should raise SearchError."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        with patch(
            "rawagents.tools.builtin.web.providers.brave.get_http_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            provider = BraveSearchProvider(api_key="test-key")
            with pytest.raises(SearchError, match="request failed"):
                await provider.search("test")

    async def test_result_parsing(self) -> None:
        """Results should be properly parsed into SearchResult objects."""
        mock_response = _make_brave_response(
            [
                {
                    "title": "Result 1",
                    "url": "https://r1.com",
                    "description": "First",
                },
                {
                    "title": "Result 2",
                    "url": "https://r2.com",
                    "description": "Second",
                },
            ]
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch(
            "rawagents.tools.builtin.web.providers.brave.get_http_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            provider = BraveSearchProvider(api_key="test-key")
            results = await provider.search("test", num_results=5)

        assert len(results) == 2
        assert isinstance(results[0], SearchResult)
        assert results[1].url == "https://r2.com"

    async def test_domain_filtering(self) -> None:
        """Domain filtering should exclude non-matching results."""
        mock_response = _make_brave_response(
            [
                {
                    "title": "Allowed",
                    "url": "https://docs.python.org/page",
                    "description": "ok",
                },
                {
                    "title": "Blocked",
                    "url": "https://spam.com/page",
                    "description": "bad",
                },
            ]
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch(
            "rawagents.tools.builtin.web.providers.brave.get_http_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            provider = BraveSearchProvider(api_key="test-key")
            results = await provider.search(
                "test",
                allowed_domains=["docs.python.org"],
            )

        assert len(results) == 1
        assert results[0].title == "Allowed"

    async def test_empty_results(self) -> None:
        """Empty results should return empty list."""
        mock_response = _make_brave_response([])

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch(
            "rawagents.tools.builtin.web.providers.brave.get_http_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            provider = BraveSearchProvider(api_key="test-key")
            results = await provider.search("nothing")

        assert results == []

    async def test_uses_shared_http_client(self) -> None:
        """Brave provider should use the shared HTTP client (M1)."""
        mock_response = _make_brave_response([])

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch(
            "rawagents.tools.builtin.web.providers.brave.get_http_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ) as mock_get_client:
            provider = BraveSearchProvider(api_key="test-key")
            await provider.search("test")
            mock_get_client.assert_called_once()

    async def test_blocked_domains_filtering(self) -> None:
        """Domain in blocked list should be excluded from results."""
        mock_response = _make_brave_response(
            [
                {
                    "title": "Good",
                    "url": "https://good.com/page",
                    "description": "ok",
                },
                {
                    "title": "Bad",
                    "url": "https://blocked.com/page",
                    "description": "bad",
                },
            ]
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch(
            "rawagents.tools.builtin.web.providers.brave.get_http_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            provider = BraveSearchProvider(api_key="test-key")
            results = await provider.search(
                "test",
                blocked_domains=["blocked.com"],
            )

        assert len(results) == 1
        assert results[0].title == "Good"

    async def test_blocked_domain_suffix_match(self) -> None:
        """sub.blocked.com should match blocked.com in block list."""
        mock_response = _make_brave_response(
            [
                {
                    "title": "Subdomain",
                    "url": "https://sub.blocked.com/page",
                    "description": "blocked subdomain",
                },
            ]
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch(
            "rawagents.tools.builtin.web.providers.brave.get_http_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            provider = BraveSearchProvider(api_key="test-key")
            results = await provider.search(
                "test",
                blocked_domains=["blocked.com"],
            )

        assert len(results) == 0

    async def test_num_results_limit(self) -> None:
        """Should only return up to num_results items."""
        mock_response = _make_brave_response(
            [
                {"title": f"R{i}", "url": f"https://r{i}.com", "description": f"d{i}"}
                for i in range(10)
            ]
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch(
            "rawagents.tools.builtin.web.providers.brave.get_http_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            provider = BraveSearchProvider(api_key="test-key")
            results = await provider.search("test", num_results=3)

        assert len(results) == 3
