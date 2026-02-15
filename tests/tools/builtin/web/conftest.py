"""Shared test fixtures for web tools tests.

Follows the same fixture pattern as shell tools (conftest.py).
"""

from __future__ import annotations

import pytest

from rawagents.tools.builtin.web import (
    SearchResult,
    WebContext,
    set_web_context,
)
from rawagents.tools.builtin.web._cache import AsyncTTLCache


# ── WebContext Fixtures ──────────────────────────────────────


@pytest.fixture
def web_context():
    """Default WebContext with permissive settings for testing."""
    ctx = WebContext(
        allow_localhost=True,
        allow_private_ips=True,
        max_requests_per_minute=100,
        max_search_per_minute=100,
        cache_ttl=0,  # Disable caching in tests by default
    )
    set_web_context(ctx)
    yield ctx
    set_web_context(None)  # Clean up


@pytest.fixture
def restricted_context():
    """Locked-down WebContext for security tests."""
    ctx = WebContext(
        allowed_domains=["docs.python.org", "github.com"],
        blocked_domains=["evil.com", "attacker.net"],
        allow_localhost=False,
        allow_private_ips=False,
    )
    set_web_context(ctx)
    yield ctx
    set_web_context(None)


# ── Mock Search Provider ─────────────────────────────────────


class MockSearchProvider:
    """Mock search provider for unit tests."""

    def __init__(self, results: list[SearchResult] | None = None):
        self._results = (
            results
            if results is not None
            else [
                SearchResult(
                    title="Test Result",
                    url="https://example.com",
                    snippet="A test search result.",
                    source="mock",
                ),
            ]
        )
        self.last_search_kwargs: dict = {}

    async def search(
        self,
        query: str,
        *,
        num_results: int = 10,
        allowed_domains: list[str] | None = None,
        blocked_domains: list[str] | None = None,
    ) -> list[SearchResult]:
        self.last_search_kwargs = {
            "query": query,
            "num_results": num_results,
            "allowed_domains": allowed_domains,
            "blocked_domains": blocked_domains,
        }
        return self._results[:num_results]

    @property
    def name(self) -> str:
        return "mock"


@pytest.fixture
def mock_provider():
    """Mock SearchProvider for web_search tests."""
    return MockSearchProvider()


# ── Mock Content Processor ───────────────────────────────────


class MockContentProcessor:
    """Mock ContentProcessor that tracks calls."""

    def __init__(self):
        self.calls: list[dict] = []

    async def process(self, content: str, url: str, prompt: str, format: str) -> str:
        self.calls.append(
            {
                "content": content,
                "url": url,
                "prompt": prompt,
                "format": format,
            }
        )
        return f"[PROCESSED] {content[:100]}"


@pytest.fixture
def mock_processor():
    """Mock ContentProcessor for web_fetch tests."""
    return MockContentProcessor()


# ── Cache Fixture ────────────────────────────────────────────


@pytest.fixture
def cache():
    """Fresh AsyncTTLCache for cache tests."""
    return AsyncTTLCache(max_size=10, ttl=60)
