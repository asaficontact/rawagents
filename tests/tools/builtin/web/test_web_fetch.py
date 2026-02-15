"""Tests for web_fetch tool."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import rawagents.tools.builtin.web.web_fetch  # noqa: F401
from rawagents.tools.builtin.web import (
    WebContext,
    set_web_context,
)
from rawagents.tools.builtin.web.web_fetch import web_fetch

from .conftest import MockContentProcessor


# Get the actual module object (not the re-exported function)
_wf_module = sys.modules["rawagents.tools.builtin.web.web_fetch"]


def _make_stream_response(
    content: str = "<h1>Hello</h1><p>World</p>",
    status_code: int = 200,
    headers: dict | None = None,
    url: str = "https://example.com",
    charset_encoding: str | None = "utf-8",
) -> MagicMock:
    """Create a mock streaming response."""
    response = MagicMock()
    response.status_code = status_code
    response.reason_phrase = "OK" if status_code == 200 else "Error"
    response.url = httpx.URL(url)
    response.charset_encoding = charset_encoding
    response.headers = headers or {"content-type": "text/html; charset=utf-8"}

    async def aiter_bytes():
        yield content.encode("utf-8")

    response.aiter_bytes = aiter_bytes
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=False)
    return response


@pytest.fixture(autouse=True)
def _reset_cache():
    """Reset the module-level cache between tests."""
    _wf_module._url_cache = None
    _wf_module._url_cache_params = None
    yield
    _wf_module._url_cache = None
    _wf_module._url_cache_params = None


class TestWebFetch:
    """Test web_fetch tool behavior."""

    async def test_basic_fetch(self, web_context: WebContext) -> None:
        """Basic fetch should return converted content."""
        response = _make_stream_response()

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=response)

        with patch(
            "rawagents.tools.builtin.web.web_fetch.get_http_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await web_fetch(url="https://example.com")

        assert "Hello" in result
        assert "World" in result

    async def test_markdown_format(self, web_context: WebContext) -> None:
        """Markdown format should produce markdown output."""
        response = _make_stream_response(content="<h1>Title</h1><p>Content</p>")

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=response)

        with patch(
            "rawagents.tools.builtin.web.web_fetch.get_http_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await web_fetch(url="https://example.com", format="markdown")

        assert "# Title" in result

    async def test_text_format(self, web_context: WebContext) -> None:
        """Text format should strip HTML tags."""
        response = _make_stream_response(content="<h1>Title</h1><p>Content</p>")

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=response)

        with patch(
            "rawagents.tools.builtin.web.web_fetch.get_http_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await web_fetch(url="https://example.com", format="text")

        assert "<h1>" not in result
        assert "Title" in result

    async def test_cache_hit(self) -> None:
        """Second fetch of same URL should use cache."""
        ctx = WebContext(
            allow_localhost=True,
            allow_private_ips=True,
            max_requests_per_minute=100,
            cache_ttl=300,  # Enable cache
        )
        set_web_context(ctx)

        response = _make_stream_response()
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=response)

        with patch(
            "rawagents.tools.builtin.web.web_fetch.get_http_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            # First fetch - should call HTTP
            result1 = await web_fetch(url="https://example.com")
            assert "Hello" in result1

            # Second fetch - should use cache (stream not called again)
            mock_client.stream = MagicMock(
                side_effect=RuntimeError("Should not be called")
            )
            result2 = await web_fetch(url="https://example.com")
            assert "Hello" in result2

        set_web_context(None)

    async def test_timeout_error(self, web_context: WebContext) -> None:
        """Timeout should return error message."""
        mock_client = AsyncMock()
        timeout_response = MagicMock()
        timeout_response.__aenter__ = AsyncMock(
            side_effect=httpx.ReadTimeout("timed out")
        )
        timeout_response.__aexit__ = AsyncMock(return_value=False)
        mock_client.stream = MagicMock(return_value=timeout_response)

        with patch(
            "rawagents.tools.builtin.web.web_fetch.get_http_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await web_fetch(url="https://example.com")

        assert "Error" in result
        assert "timed out" in result

    async def test_large_response_truncation(self, web_context: WebContext) -> None:
        """Content exceeding max_content_chars should be truncated."""
        web_context.max_content_chars = 50
        large_html = "<p>" + "x" * 200 + "</p>"
        response = _make_stream_response(content=large_html)

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=response)

        with patch(
            "rawagents.tools.builtin.web.web_fetch.get_http_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await web_fetch(url="https://example.com")

        assert "truncated" in result.lower()

    async def test_invalid_url(self, web_context: WebContext) -> None:
        """Invalid URL should return error."""
        result = await web_fetch(url="ftp://example.com")
        assert "Error" in result

    async def test_ssrf_blocked(self) -> None:
        """SSRF attempts should be blocked."""
        ctx = WebContext(
            allow_localhost=False,
            allow_private_ips=False,
            max_requests_per_minute=100,
            cache_ttl=0,
        )
        set_web_context(ctx)

        with patch.object(
            ctx,
            "_resolve_hostname",
            new_callable=AsyncMock,
            return_value="10.0.0.1",
        ):
            result = await web_fetch(url="http://internal.example.com")

        assert "Error" in result
        assert "private" in result.lower()
        set_web_context(None)

    async def test_custom_processor(self, web_context: WebContext) -> None:
        """Custom ContentProcessor should be applied."""
        processor = MockContentProcessor()
        web_context.content_processor = processor  # type: ignore[assignment]

        response = _make_stream_response()
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=response)

        with patch(
            "rawagents.tools.builtin.web.web_fetch.get_http_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await web_fetch(
                url="https://example.com",
                prompt="extract info",
            )

        assert "[PROCESSED]" in result
        assert len(processor.calls) == 1
        assert processor.calls[0]["prompt"] == "extract info"

    async def test_cache_disabled(self, web_context: WebContext) -> None:
        """With cache_ttl=0, no caching should occur."""
        assert web_context.cache_ttl == 0

        response = _make_stream_response()
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=response)

        with patch(
            "rawagents.tools.builtin.web.web_fetch.get_http_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await web_fetch(url="https://example.com")

        assert "Hello" in result

    async def test_http_error_status(self, web_context: WebContext) -> None:
        """HTTP error status should return error message."""
        response = _make_stream_response(status_code=404)
        response.reason_phrase = "Not Found"

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=response)

        with patch(
            "rawagents.tools.builtin.web.web_fetch.get_http_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await web_fetch(url="https://example.com")

        assert "Error" in result
        assert "404" in result

    async def test_malformed_content_length(self, web_context: WebContext) -> None:
        """Non-numeric Content-Length should not crash (H1)."""
        response = _make_stream_response(
            headers={"content-type": "text/html", "content-length": "12, 34"}
        )

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=response)

        with patch(
            "rawagents.tools.builtin.web.web_fetch.get_http_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await web_fetch(url="https://example.com")

        assert "Hello" in result  # Should succeed despite malformed header

    async def test_unknown_charset_fallback(self, web_context: WebContext) -> None:
        """Unknown charset should fall back to UTF-8 (H8)."""
        response = _make_stream_response(
            charset_encoding="x-user-defined",
        )

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=response)

        with patch(
            "rawagents.tools.builtin.web.web_fetch.get_http_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await web_fetch(url="https://example.com")

        assert "Hello" in result  # Should fall back to utf-8

    async def test_cache_recreated_on_context_change(self) -> None:
        """New WebContext with different TTL should create new cache (C3)."""
        ctx1 = WebContext(
            allow_localhost=True,
            allow_private_ips=True,
            max_requests_per_minute=100,
            cache_ttl=300,
            cache_max_size=50,
        )
        set_web_context(ctx1)

        response = _make_stream_response()
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=response)

        with patch(
            "rawagents.tools.builtin.web.web_fetch.get_http_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            await web_fetch(url="https://example.com")

        cache1 = _wf_module._url_cache
        assert cache1 is not None
        assert cache1.ttl == 300

        # Change context with different cache params
        ctx2 = WebContext(
            allow_localhost=True,
            allow_private_ips=True,
            max_requests_per_minute=100,
            cache_ttl=600,
            cache_max_size=100,
        )
        set_web_context(ctx2)

        mock_client.stream = MagicMock(return_value=_make_stream_response())

        with patch(
            "rawagents.tools.builtin.web.web_fetch.get_http_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            await web_fetch(url="https://other.com")

        cache2 = _wf_module._url_cache
        assert cache2 is not None
        assert cache2.ttl == 600
        assert cache2 is not cache1  # New cache was created

        set_web_context(None)

    async def test_cancellation_cleans_inflight(self) -> None:
        """BaseException during fetch should call cancel_inflight (M3)."""
        ctx = WebContext(
            allow_localhost=True,
            allow_private_ips=True,
            max_requests_per_minute=100,
            cache_ttl=300,
        )
        set_web_context(ctx)

        mock_client = AsyncMock()
        error_response = MagicMock()
        error_response.__aenter__ = AsyncMock(side_effect=KeyboardInterrupt)
        error_response.__aexit__ = AsyncMock(return_value=False)
        mock_client.stream = MagicMock(return_value=error_response)

        with (
            patch(
                "rawagents.tools.builtin.web.web_fetch.get_http_client",
                new_callable=AsyncMock,
                return_value=mock_client,
            ),
            pytest.raises(KeyboardInterrupt),
        ):
            await web_fetch(url="https://example.com")

        # After KeyboardInterrupt, the inflight entry should be cleaned up
        cache = _wf_module._url_cache
        assert cache is not None
        assert "https://example.com" not in cache._in_flight

        set_web_context(None)

    async def test_text_plain_passthrough(self, web_context: WebContext) -> None:
        """text/plain content should skip HTML conversion (PRD gap)."""
        response = _make_stream_response(
            content="Hello, this is plain text with <tags>.",
            headers={"content-type": "text/plain"},
        )

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=response)

        with patch(
            "rawagents.tools.builtin.web.web_fetch.get_http_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await web_fetch(url="https://example.com/file.txt")

        # Should NOT be converted — tags preserved
        assert "<tags>" in result

    async def test_text_markdown_passthrough(self, web_context: WebContext) -> None:
        """text/markdown content should skip HTML conversion (PRD gap)."""
        md_content = "# Title\n\nSome **bold** text."
        response = _make_stream_response(
            content=md_content,
            headers={"content-type": "text/markdown"},
        )

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=response)

        with patch(
            "rawagents.tools.builtin.web.web_fetch.get_http_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await web_fetch(url="https://example.com/readme.md")

        assert result == md_content

    async def test_invalid_format(self, web_context: WebContext) -> None:
        """Format not in (markdown, text, html) should return error."""
        result = await web_fetch(url="https://example.com", format="json")
        assert "Error" in result
        assert "Format must be" in result

    async def test_redirect_blocked_ssrf(self, web_context: WebContext) -> None:
        """Redirect to private IP should be blocked (C1)."""
        web_context.allow_private_ips = False
        web_context.allow_localhost = False

        redirect_response = _make_stream_response(
            status_code=302,
            headers={
                "content-type": "text/html",
                "location": "http://169.254.169.254/metadata",
            },
        )

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=redirect_response)

        with patch(
            "rawagents.tools.builtin.web.web_fetch.get_http_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await web_fetch(url="https://example.com")

        assert "Error" in result
        assert "Redirect blocked" in result

    async def test_redirect_no_location(self, web_context: WebContext) -> None:
        """Redirect with no Location header should return error (C1)."""
        redirect_response = _make_stream_response(
            status_code=301,
            headers={"content-type": "text/html"},
        )

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=redirect_response)

        with patch(
            "rawagents.tools.builtin.web.web_fetch.get_http_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await web_fetch(url="https://example.com")

        assert "Error" in result
        assert "no Location" in result

    async def test_too_many_redirects(self, web_context: WebContext) -> None:
        """More than 5 redirects should return error (C1)."""
        redirect_response = _make_stream_response(
            status_code=302,
            headers={
                "content-type": "text/html",
                "location": "https://example.com/next",
            },
        )

        mock_client = AsyncMock()
        # Always return a redirect
        mock_client.stream = MagicMock(return_value=redirect_response)

        with patch(
            "rawagents.tools.builtin.web.web_fetch.get_http_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await web_fetch(url="https://example.com")

        assert "Error" in result
        assert "Too many redirects" in result
