"""Web fetch tool for RawAgents.

Fetches web page content, converts to markdown/text/html, with
caching, SSRF prevention, and optional content processing.
"""

from __future__ import annotations

from typing import Annotated
from urllib.parse import urljoin

import httpx

from rawagents.tools import tool
from rawagents.tools.builtin.web._cache import AsyncTTLCache
from rawagents.tools.builtin.web._context import (
    RateLimitExceededError,
    SSRFError,
    URLValidationError,
    WebContext,
    get_web_context,
)
from rawagents.tools.builtin.web._conversion import convert_html_to_format
from rawagents.tools.builtin.web._http import get_http_client


__all__ = ["web_fetch"]


# Binary content types that should not be fetched
_BINARY_CONTENT_TYPES = {
    "image/",
    "audio/",
    "video/",
    "application/octet-stream",
    "application/zip",
    "application/gzip",
    "application/pdf",
}

# Module-level cache singleton
_url_cache: AsyncTTLCache | None = None
_url_cache_params: tuple[int, int] | None = None

# Text content types that skip HTML conversion
_TEXT_PASSTHROUGH_TYPES = {"text/plain", "text/markdown"}

_MAX_REDIRECTS = 5


def _get_cache(ctx: WebContext) -> AsyncTTLCache:
    """Get or create the module-level URL cache singleton."""
    global _url_cache, _url_cache_params  # noqa: PLW0603
    params = (ctx.cache_ttl, ctx.cache_max_size)
    if _url_cache is None or _url_cache_params != params:
        _url_cache = AsyncTTLCache(
            max_size=ctx.cache_max_size,
            ttl=ctx.cache_ttl,
        )
        _url_cache_params = params
    return _url_cache


def _is_binary_content_type(content_type: str) -> bool:
    """Check if content type is binary."""
    ct = content_type.lower().split(";")[0].strip()
    return any(ct.startswith(prefix) for prefix in _BINARY_CONTENT_TYPES)


def _is_text_passthrough(content_type: str) -> bool:
    """Check if content type should skip HTML conversion."""
    ct = content_type.lower().split(";")[0].strip()
    return ct in _TEXT_PASSTHROUGH_TYPES


@tool
async def web_fetch(  # noqa: PLR0912
    url: Annotated[str, "The URL to fetch (must start with http:// or https://)"],
    prompt: Annotated[str, "Context for what to extract"] = "",
    format: Annotated[str, "Output format: markdown, text, or html"] = "markdown",
    timeout: Annotated[int, "Request timeout in seconds (max 120)"] = 30,
) -> str:
    """Fetch a web page and return its content.

    Fetches the URL, converts HTML to the requested format, and optionally
    processes content via a ContentProcessor. Results are cached for 15 minutes
    by default.
    """
    # Validate format
    if format not in ("markdown", "text", "html"):
        return "Error: Format must be 'markdown', 'text', or 'html'"

    # Get context
    ctx = get_web_context()

    # Validate URL
    try:
        _, hostname = await ctx.validate_url(url)
    except (URLValidationError, SSRFError) as e:
        return str(e)

    # Check rate limit
    try:
        ctx.check_rate_limit("fetch")
    except RateLimitExceededError as e:
        return str(e)

    # Validate timeout
    timeout = min(max(timeout, 1), ctx.max_timeout)

    # Check cache (if enabled)
    use_cache = ctx.cache_ttl > 0
    cache = _get_cache(ctx) if use_cache else None
    html_content: str | None = None
    is_text_passthrough = False

    if cache is not None:
        cached, should_fetch = await cache.get_or_wait(url)
        if cached is not None:
            # Cache hit — convert and return
            html_content = cached
        elif not should_fetch:
            # Another coroutine is fetching — wait for it
            html_content = await cache.wait_for_inflight(url)
    else:
        should_fetch = True

    # Fetch if not cached
    if html_content is None:
        try:
            result = await _fetch_with_redirects(
                url, hostname, ctx, timeout, cache, should_fetch
            )
            if isinstance(result, str):
                return result
            html_content, is_text_passthrough = result

        except BaseException:
            if cache is not None and should_fetch:
                await cache.cancel_inflight(url)
            raise

    # Skip HTML conversion for text/plain and text/markdown
    if is_text_passthrough:
        content = html_content  # type: ignore[assignment]
    else:
        # Convert HTML to requested format
        content = convert_html_to_format(html_content, format)  # type: ignore[arg-type]

    # Apply content processor if set
    if ctx.content_processor is not None:
        try:
            content = await ctx.content_processor.process(content, url, prompt, format)
        except Exception as e:
            return f"Error: Content processing failed: {e}"

    # Truncate if needed
    if len(content) > ctx.max_content_chars:
        content = content[: ctx.max_content_chars]
        content += f"\n\n[Content truncated at 100KB. Full page available at: {url}]"

    return content


async def _fetch_with_redirects(  # noqa: PLR0911, PLR0912, PLR0915
    url: str,
    hostname: str,
    ctx: WebContext,
    timeout: int,
    cache: AsyncTTLCache | None,
    should_fetch: bool,
) -> tuple[str, bool] | str:
    """Fetch URL with manual redirect following and SSRF validation.

    Returns (content, is_text_passthrough) on success, or error string.
    """
    current_url = url

    for _redirect_num in range(_MAX_REDIRECTS + 1):
        try:
            client = await get_http_client(user_agent=ctx.user_agent)

            async with client.stream(
                "GET",
                current_url,
                timeout=httpx.Timeout(timeout),
            ) as response:
                # Handle redirects manually (follow_redirects=False)
                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get("location")
                    if not location:
                        if cache is not None and should_fetch:
                            await cache.cancel_inflight(url)
                        return "Error: Redirect with no Location header"
                    next_url = urljoin(current_url, location)
                    # SSRF check on redirect target
                    try:
                        _, _ = await ctx.validate_url(next_url)
                    except (URLValidationError, SSRFError) as e:
                        if cache is not None and should_fetch:
                            await cache.cancel_inflight(url)
                        return f"Error: Redirect blocked: {e}"
                    current_url = next_url
                    continue

                # Check Content-Length before reading
                content_length = response.headers.get("content-length")
                if content_length:
                    try:
                        if int(content_length) > ctx.max_response_bytes:
                            if cache is not None and should_fetch:
                                await cache.cancel_inflight(url)
                            return "Error: Response exceeds 5MB size limit"
                    except ValueError:
                        pass  # Malformed header — proceed with streaming check

                # Check for binary content
                content_type = response.headers.get("content-type", "")
                if _is_binary_content_type(content_type):
                    if cache is not None and should_fetch:
                        await cache.cancel_inflight(url)
                    return f"Error: Cannot fetch binary content (Content-Type: {content_type.split(';')[0].strip()})"

                # Check HTTP status
                if response.status_code >= 400:
                    if cache is not None and should_fetch:
                        await cache.cancel_inflight(url)
                    return (
                        f"Error: HTTP {response.status_code}: {response.reason_phrase}"
                    )

                # Stream response body
                chunks: list[bytes] = []
                total_bytes = 0
                async for chunk in response.aiter_bytes():
                    total_bytes += len(chunk)
                    if total_bytes > ctx.max_response_bytes:
                        if cache is not None and should_fetch:
                            await cache.cancel_inflight(url)
                        return "Error: Response exceeds 5MB size limit"
                    chunks.append(chunk)

                # Decode with charset fallback
                charset = response.charset_encoding or "utf-8"
                try:
                    text_content = b"".join(chunks).decode(charset, errors="replace")
                except (LookupError, UnicodeDecodeError):
                    text_content = b"".join(chunks).decode("utf-8", errors="replace")

            # Check for text passthrough (text/plain, text/markdown)
            is_passthrough = _is_text_passthrough(content_type)

            # Cache raw content
            if cache is not None:
                await cache.set(url, text_content)

            return text_content, is_passthrough

        except httpx.TimeoutException:
            if cache is not None and should_fetch:
                await cache.cancel_inflight(url)
            return f"Error: Request timed out after {timeout} seconds"

        except httpx.RequestError as e:
            if cache is not None and should_fetch:
                await cache.cancel_inflight(url)
            return f"Error: Failed to connect to {hostname}: {e}"

    # Exhausted redirect limit
    if cache is not None and should_fetch:
        await cache.cancel_inflight(url)
    return "Error: Too many redirects"
