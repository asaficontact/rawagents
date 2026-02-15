"""Tests for ContentProcessor integration with web_fetch."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx

import rawagents.tools.builtin.web.web_fetch as _wf_module
from rawagents.tools.builtin.web import (
    WebContext,
    set_web_context,
)
from rawagents.tools.builtin.web.web_fetch import web_fetch

from .conftest import MockContentProcessor


def _make_stream_response(
    content: str = "<h1>Hello</h1><p>World</p>",
    url: str = "https://example.com",
) -> MagicMock:
    """Create a mock streaming response."""
    response = MagicMock()
    response.status_code = 200
    response.reason_phrase = "OK"
    response.url = httpx.URL(url)
    response.charset_encoding = "utf-8"
    response.headers = {"content-type": "text/html; charset=utf-8"}

    async def aiter_bytes():
        yield content.encode("utf-8")

    response.aiter_bytes = aiter_bytes
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=False)
    return response


class TestContentProcessor:
    """Test ContentProcessor integration."""

    async def test_processor_called_with_correct_args(self) -> None:
        """ContentProcessor should receive content, url, prompt, format."""
        processor = MockContentProcessor()
        ctx = WebContext(
            allow_localhost=True,
            allow_private_ips=True,
            max_requests_per_minute=100,
            cache_ttl=0,
            content_processor=processor,  # type: ignore[arg-type]
        )
        set_web_context(ctx)

        # Reset cache
        _wf_module._url_cache = None

        response = _make_stream_response()
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=response)

        with patch(
            "rawagents.tools.builtin.web.web_fetch.get_http_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            await web_fetch(
                url="https://example.com",
                prompt="extract features",
                format="markdown",
            )

        assert len(processor.calls) == 1
        call = processor.calls[0]
        assert call["url"] == "https://example.com"
        assert call["prompt"] == "extract features"
        assert call["format"] == "markdown"
        assert len(call["content"]) > 0

        set_web_context(None)

    async def test_processor_chaining_with_truncation(self) -> None:
        """Processor output should be truncated if too long."""

        class LongProcessor:
            async def process(self, content, url, prompt, format):
                return "X" * 200_000  # Very long output

        ctx = WebContext(
            allow_localhost=True,
            allow_private_ips=True,
            max_requests_per_minute=100,
            cache_ttl=0,
            content_processor=LongProcessor(),  # type: ignore[arg-type]
            max_content_chars=100,
        )
        set_web_context(ctx)

        _wf_module._url_cache = None

        response = _make_stream_response()
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=response)

        with patch(
            "rawagents.tools.builtin.web.web_fetch.get_http_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await web_fetch(url="https://example.com")

        assert "truncated" in result.lower()
        set_web_context(None)

    async def test_processor_error_handling(self) -> None:
        """Processor error should return error message."""

        class FailingProcessor:
            async def process(self, content, url, prompt, format):
                raise ValueError("Processing exploded")

        ctx = WebContext(
            allow_localhost=True,
            allow_private_ips=True,
            max_requests_per_minute=100,
            cache_ttl=0,
            content_processor=FailingProcessor(),  # type: ignore[arg-type]
        )
        set_web_context(ctx)

        _wf_module._url_cache = None

        response = _make_stream_response()
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=response)

        with patch(
            "rawagents.tools.builtin.web.web_fetch.get_http_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await web_fetch(url="https://example.com")

        assert "Error" in result
        assert "Content processing failed" in result
        set_web_context(None)

    async def test_processor_modifies_content(self) -> None:
        """Processor should be able to modify content."""

        class UpperProcessor:
            async def process(self, content, url, prompt, format):
                return content.upper()

        ctx = WebContext(
            allow_localhost=True,
            allow_private_ips=True,
            max_requests_per_minute=100,
            cache_ttl=0,
            content_processor=UpperProcessor(),  # type: ignore[arg-type]
        )
        set_web_context(ctx)

        _wf_module._url_cache = None

        response = _make_stream_response(content="<p>hello world</p>")
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=response)

        with patch(
            "rawagents.tools.builtin.web.web_fetch.get_http_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await web_fetch(url="https://example.com")

        assert "HELLO WORLD" in result
        set_web_context(None)

    async def test_no_processor_passthrough(self) -> None:
        """Without processor, content should pass through unchanged."""
        ctx = WebContext(
            allow_localhost=True,
            allow_private_ips=True,
            max_requests_per_minute=100,
            cache_ttl=0,
            content_processor=None,
        )
        set_web_context(ctx)

        _wf_module._url_cache = None

        response = _make_stream_response(content="<p>hello world</p>")
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=response)

        with patch(
            "rawagents.tools.builtin.web.web_fetch.get_http_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await web_fetch(url="https://example.com")

        assert "hello world" in result
        set_web_context(None)
