"""Tests for web_search tool."""

from __future__ import annotations

import os
from unittest.mock import patch

from rawagents.tools.builtin.web import (
    SearchResult,
    WebContext,
)
from rawagents.tools.builtin.web._types import SearchError
from rawagents.tools.builtin.web.web_search import web_search

from .conftest import MockSearchProvider


class TestWebSearch:
    """Test web_search tool behavior."""

    async def test_basic_search(self, web_context: WebContext) -> None:
        """Basic search should return formatted results."""
        provider = MockSearchProvider()
        web_context.search_provider = provider

        result = await web_search(query="test query")
        assert "Test Result" in result
        assert "https://example.com" in result
        assert "1." in result

    async def test_no_provider_no_env(self, web_context: WebContext) -> None:
        """Should return error when no provider and no BRAVE_API_KEY."""
        with patch.dict(os.environ, {}, clear=True):
            env = dict(os.environ)
            env.pop("BRAVE_API_KEY", None)
            with patch.dict(os.environ, env, clear=True):
                result = await web_search(query="test")
                assert "Error" in result
                assert "No search provider" in result

    async def test_empty_results(self, web_context: WebContext) -> None:
        """Empty results should return 'No results found' message."""
        provider = MockSearchProvider(results=[])
        web_context.search_provider = provider

        result = await web_search(query="nothing")
        assert "No results found" in result

    async def test_both_domain_lists_error(self, web_context: WebContext) -> None:
        """Using both allowed and blocked domains should return error."""
        provider = MockSearchProvider()
        web_context.search_provider = provider

        result = await web_search(
            query="test",
            allowed_domains=["a.com"],
            blocked_domains=["b.com"],
        )
        assert "Error" in result
        assert "Cannot use both" in result

    async def test_provider_error(self, web_context: WebContext) -> None:
        """Provider error should return error message."""

        class FailingProvider:
            async def search(self, query, **kwargs):
                raise SearchError("API down")

            @property
            def name(self):
                return "failing"

        web_context.search_provider = FailingProvider()  # type: ignore[assignment]
        result = await web_search(query="test")
        assert "Error" in result
        assert "Search failed" in result

    async def test_result_formatting(self, web_context: WebContext) -> None:
        """Results should be formatted as numbered markdown links."""
        provider = MockSearchProvider(
            results=[
                SearchResult("First", "https://a.com", "Snippet A", "mock"),
                SearchResult("Second", "https://b.com", "Snippet B", "mock"),
            ]
        )
        web_context.search_provider = provider

        result = await web_search(query="test")
        assert "1. [First](https://a.com)" in result
        assert "2. [Second](https://b.com)" in result
        assert "Snippet A" in result
        assert "Snippet B" in result

    async def test_empty_query_error(self, web_context: WebContext) -> None:
        """Empty query should return error."""
        result = await web_search(query="")
        assert "Error" in result
        assert "cannot be empty" in result

    async def test_non_search_error_caught(self, web_context: WebContext) -> None:
        """Non-SearchError exceptions should be caught (H7)."""

        class BuggyProvider:
            async def search(self, query, **kwargs):
                raise RuntimeError("unexpected crash")

            @property
            def name(self):
                return "buggy"

        web_context.search_provider = BuggyProvider()  # type: ignore[assignment]
        result = await web_search(query="test")
        assert "Error" in result
        assert "Unexpected search error" in result

    async def test_results_header_line(self, web_context: WebContext) -> None:
        """Output should start with 'Found N results for ...' (PRD gap)."""
        provider = MockSearchProvider(
            results=[
                SearchResult("R1", "https://r1.com", "s1", "mock"),
                SearchResult("R2", "https://r2.com", "s2", "mock"),
            ]
        )
        web_context.search_provider = provider

        result = await web_search(query="python asyncio")
        assert result.startswith("Found 2 results for 'python asyncio':")

    async def test_query_whitespace_stripped(self, web_context: WebContext) -> None:
        """Query whitespace should be stripped before passing to provider (PRD gap)."""
        provider = MockSearchProvider()
        web_context.search_provider = provider

        await web_search(query="  python  ")
        assert provider.last_search_kwargs["query"] == "python"

    async def test_num_results_clamped_to_20(self, web_context: WebContext) -> None:
        """num_results > 20 should be clamped to 20."""
        provider = MockSearchProvider()
        web_context.search_provider = provider

        await web_search(query="test", num_results=50)
        assert provider.last_search_kwargs["num_results"] == 20

    async def test_whitespace_only_query(self, web_context: WebContext) -> None:
        """Whitespace-only query should return empty query error."""
        result = await web_search(query="   ")
        assert "Error" in result
        assert "cannot be empty" in result
