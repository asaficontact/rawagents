"""Unified context for web tools.

This module provides the single configuration object for all web operations,
combining security settings, provider configuration, and runtime options.

PATTERN: Follows the same single-context pattern as:
  - fs/_security.py -> SecurityContext
  - shell/_security.py -> ShellSecurityContext

Example (zero-config):
    # Just set BRAVE_API_KEY env var, tools auto-create WebContext
    results = await web_search(query="python asyncio")

Example (explicit config):
    from rawagents.tools.builtin.web import WebContext, set_web_context
    ctx = WebContext(
        allowed_domains=["docs.python.org", "github.com"],
        max_requests_per_minute=20,
    )
    set_web_context(ctx)
"""

from __future__ import annotations

import asyncio
import contextvars
import ipaddress
import socket
import warnings
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from urllib.parse import urlparse


if TYPE_CHECKING:
    from ._types import ContentProcessor, SearchProvider


__all__ = [
    "RateLimitExceededError",
    "SSRFError",
    "URLValidationError",
    "WebContext",
    "WebSecurityError",
    "domain_matches",
    "get_web_context",
    "set_web_context",
]


# ──────────────────────────────────────────────────────────────
# Error Classes
# ──────────────────────────────────────────────────────────────


class WebSecurityError(PermissionError):
    """Raised when a web operation violates security constraints.

    Attributes:
        url: The URL that was rejected (if applicable).
        reason: Specific reason for rejection.
    """

    def __init__(
        self,
        message: str,
        url: str | None = None,
        reason: str | None = None,
    ):
        super().__init__(message)
        self.url = url
        self.reason = reason


class URLValidationError(WebSecurityError):
    """Raised when URL validation fails."""

    pass


class SSRFError(WebSecurityError):
    """Raised when SSRF attack is detected."""

    pass


class RateLimitExceededError(WebSecurityError):
    """Raised when rate limit is exceeded."""

    pass


# ──────────────────────────────────────────────────────────────
# Domain Matching Utility (shared by _context and brave.py)
# ──────────────────────────────────────────────────────────────


def domain_matches(domain: str, domain_list: list[str]) -> bool:
    """Check if domain matches any entry in list (exact or subdomain suffix).

    Uses exact match or subdomain suffix -- NOT substring.
    "example.com" matches "example.com" and "sub.example.com"
    but NOT "not-example.com" or "myexample.com".
    """
    domain_lower = domain.lower()
    return any(
        domain_lower == d.lower() or domain_lower.endswith("." + d.lower())
        for d in domain_list
    )


# ──────────────────────────────────────────────────────────────
# WebContext — Single Unified Configuration
# ──────────────────────────────────────────────────────────────


@dataclass
class WebContext:
    """Unified context for all web operations.

    Combines security settings, provider config, and runtime options
    in a single object — matching the pattern used by SecurityContext
    (fs module) and ShellSecurityContext (shell module).
    """

    # ── Domain Filtering ──────────────────────────────────────

    allowed_domains: list[str] = field(default_factory=list)
    """If non-empty, only allow requests to these domains."""

    blocked_domains: list[str] = field(default_factory=list)
    """Domains that are always blocked (e.g., internal networks)."""

    # ── Network Restrictions (SSRF Prevention) ────────────────

    allow_localhost: bool = False
    """Whether to allow localhost (127.0.0.1, ::1)."""

    allow_private_ips: bool = False
    """Whether to allow RFC 1918 private IPs (10.x, 172.16.x, 192.168.x)."""

    # ── Response Limits ───────────────────────────────────────

    max_response_bytes: int = 5 * 1024 * 1024  # 5MB
    """Maximum HTTP response size before rejecting."""

    max_content_chars: int = 100_000  # 100K characters
    """Maximum text content to return (for truncation)."""

    # ── Timeouts ──────────────────────────────────────────────

    default_timeout: int = 30  # seconds
    """Default request timeout."""

    max_timeout: int = 120  # seconds
    """Maximum allowed request timeout."""

    # ── Rate Limiting ─────────────────────────────────────────

    max_requests_per_minute: int = 30
    """Maximum web requests (fetch) per minute."""

    max_search_per_minute: int = 10
    """Maximum search requests per minute (more restrictive)."""

    # ── Search Provider ───────────────────────────────────────

    search_provider: SearchProvider | None = None
    """The SearchProvider instance. If None, auto-creates BraveSearchProvider
    from BRAVE_API_KEY env var at first search call."""

    # ── Content Processing ────────────────────────────────────

    content_processor: ContentProcessor | None = None
    """Optional processor applied to fetched content before returning
    to the agent."""

    # ── Caching ───────────────────────────────────────────────

    cache_ttl: int = 900  # 15 minutes
    """Cache time-to-live in seconds. Set to 0 to disable caching."""

    cache_max_size: int = 128
    """Maximum number of URLs to keep in cache (LRU eviction)."""

    # ── HTTP Client Settings ──────────────────────────────────

    user_agent: str = "RawAgents/1.0 (+https://github.com/tawab-safi/rawagents)"
    """User-Agent header for HTTP requests."""

    max_retries: int = 2
    """Number of retries for failed requests."""

    retry_on_cloudflare: bool = True
    """Whether to retry with simplified UA when Cloudflare blocks."""

    # ── Internal State (not set by user) ──────────────────────

    _request_times: dict[str, list[datetime]] = field(
        default_factory=lambda: defaultdict(list)
    )
    """Track request timestamps for rate limiting."""

    _dns_cache: dict[str, tuple[str, datetime]] = field(default_factory=dict)
    """Short-lived DNS cache to mitigate DNS rebinding TOCTOU."""

    # ── Initialization ────────────────────────────────────────

    def __post_init__(self) -> None:
        """Normalize domain lists."""
        self.allowed_domains = [d.lower().strip() for d in self.allowed_domains]
        self.blocked_domains = [d.lower().strip() for d in self.blocked_domains]

    # ── URL Validation ────────────────────────────────────────

    async def validate_url(self, url: str) -> tuple[str, str]:
        """Validate URL and return (normalized_url, hostname).

        Args:
            url: The URL to validate.

        Returns:
            Tuple of (normalized_url, hostname).

        Raises:
            URLValidationError: If URL is invalid.
            SSRFError: If SSRF attempt detected.
        """
        # Parse URL
        try:
            parsed = urlparse(url)
        except Exception as e:
            raise URLValidationError(
                f"Error: Invalid URL: {e}",
                url=url,
                reason="URL parsing failed",
            ) from e

        # Validate scheme
        if parsed.scheme not in ("http", "https"):
            raise URLValidationError(
                "Error: URL must start with http:// or https://",
                url=url,
                reason="Invalid scheme",
            )

        # Extract hostname
        hostname = parsed.hostname
        if not hostname:
            raise URLValidationError(
                "Error: Invalid URL: missing hostname",
                url=url,
                reason="No hostname in URL",
            )

        # Domain blocklist check (before DNS resolution)
        hostname_lower = hostname.lower()
        if self._is_domain_blocked(hostname_lower):
            raise URLValidationError(
                f"Error: Domain '{hostname}' is blocked",
                url=url,
                reason="Domain in blocklist",
            )

        # Domain allowlist check (before DNS resolution)
        if self.allowed_domains and not self._is_domain_allowed(hostname_lower):
            raise URLValidationError(
                f"Error: Domain '{hostname}' is not in allowed list",
                url=url,
                reason="Domain not in allowlist",
            )

        # Resolve hostname to IP (for SSRF prevention, async-safe)
        try:
            ip = await self._resolve_hostname(hostname)
        except Exception as exc:
            if hostname in ("localhost", "127.0.0.1", "::1"):
                raise SSRFError(
                    "Error: Cannot fetch localhost addresses",
                    url=url,
                    reason="Localhost is blocked",
                ) from exc
            raise URLValidationError(
                f"Error: Failed to resolve hostname: {hostname}",
                url=url,
                reason="DNS resolution failed",
            ) from exc

        # SSRF check: block private IPs
        if not self._is_ip_allowed(ip):
            raise SSRFError(
                f"Error: Cannot fetch private/internal URLs (resolved to {ip})",
                url=url,
                reason="Private IP address",
            )

        return url, hostname

    def check_rate_limit(self, operation: str = "fetch") -> None:
        """Check rate limit for an operation.

        Args:
            operation: Either "fetch" or "search".

        Raises:
            RateLimitExceededError: If rate limit exceeded.
        """
        now = datetime.now(UTC)
        one_minute_ago = now - timedelta(minutes=1)

        limit = (
            self.max_search_per_minute
            if operation == "search"
            else self.max_requests_per_minute
        )

        # Clean up old entries
        self._request_times[operation] = [
            t for t in self._request_times[operation] if t > one_minute_ago
        ]

        # Check limit
        if len(self._request_times[operation]) >= limit:
            raise RateLimitExceededError(
                f"Error: {operation.capitalize()} rate limit exceeded. "
                f"Max {limit} per minute.",
                reason="Rate limit exceeded",
            )

        # Record this request
        self._request_times[operation].append(now)

    # ── Private Helpers ───────────────────────────────────────

    def _is_domain_blocked(self, domain: str) -> bool:
        """Check if domain is in blocklist (exact or subdomain suffix)."""
        return domain_matches(domain, self.blocked_domains)

    def _is_domain_allowed(self, domain: str) -> bool:
        """Check if domain is in allowlist (exact or subdomain suffix)."""
        if not self.allowed_domains:
            return True
        return domain_matches(domain, self.allowed_domains)

    async def _resolve_hostname(self, hostname: str) -> str:
        """Resolve hostname to IP address (async-safe) with short-lived cache."""
        # Check DNS cache (60s TTL) to mitigate DNS rebinding
        cached = self._dns_cache.get(hostname)
        if cached:
            ip, ts = cached
            if (datetime.now(UTC) - ts).total_seconds() < 60:
                return ip

        def _sync_resolve() -> str:
            try:
                return socket.gethostbyname(hostname)
            except socket.gaierror:
                return socket.getaddrinfo(hostname, None)[0][4][0]

        ip = await asyncio.to_thread(_sync_resolve)
        self._dns_cache[hostname] = (ip, datetime.now(UTC))
        return ip

    def _is_ip_allowed(self, ip: str) -> bool:
        """Check if IP address is allowed."""
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False

        if not self.allow_localhost and addr.is_loopback:
            return False
        if not self.allow_private_ips and addr.is_private:
            return False
        if addr.is_link_local:
            return False
        return not addr.is_reserved


# ──────────────────────────────────────────────────────────────
# Context Variable Management
# ──────────────────────────────────────────────────────────────

_web_context: contextvars.ContextVar[WebContext | None] = contextvars.ContextVar(
    "web_context", default=None
)


def get_web_context(allow_permissive: bool = True) -> WebContext:
    """Get the current WebContext from context vars.

    Args:
        allow_permissive: If True (default), returns a permissive default
            context when none is set. If False, raises an error.

    Returns:
        The current WebContext.

    Raises:
        WebSecurityError: If allow_permissive=False and no context is set.
    """
    ctx = _web_context.get(None)
    if ctx is None:
        if not allow_permissive:
            raise WebSecurityError(
                "No WebContext set. Call set_web_context() before using web tools.",
                reason="No context configured",
            )
        warnings.warn(
            "No WebContext set. Using permissive defaults. "
            "Call set_web_context() for production use.",
            DeprecationWarning,
            stacklevel=2,
        )
        return WebContext()
    return ctx


# BUG FIX #2: Accept WebContext | None (not just WebContext)
def set_web_context(ctx: WebContext | None) -> None:
    """Set the WebContext in context vars.

    Args:
        ctx: The WebContext to set, or None to clear.
    """
    _web_context.set(ctx)
