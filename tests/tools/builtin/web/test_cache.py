"""Tests for AsyncTTLCache with TTL, eviction, and thundering herd."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from rawagents.tools.builtin.web._cache import AsyncTTLCache, CacheEntry


class TestCacheEntry:
    """Test CacheEntry behavior."""

    async def test_set_and_get(self, cache: AsyncTTLCache) -> None:
        """Set a cache entry and retrieve it."""
        await cache.set("http://example.com", "hello")
        result = await cache.get("http://example.com")
        assert result == "hello"

    async def test_cache_miss(self, cache: AsyncTTLCache) -> None:
        """Missing key returns None."""
        result = await cache.get("http://missing.com")
        assert result is None

    async def test_entry_expiry(self) -> None:
        """Expired entries should not be returned."""
        entry = CacheEntry(
            content="old",
            timestamp=datetime(2020, 1, 1, tzinfo=UTC),
            ttl_seconds=60,
        )
        assert entry.is_expired() is True

    async def test_ttl_zero_disables_cache(self) -> None:
        """BUG FIX #1: ttl_seconds=0 should mean always expired."""
        entry = CacheEntry(
            content="test",
            timestamp=datetime.now(UTC),
            ttl_seconds=0,
        )
        assert entry.is_expired() is True


class TestAsyncTTLCache:
    """Test AsyncTTLCache advanced behavior."""

    async def test_lru_eviction(self) -> None:
        """When cache is full, oldest entry should be evicted."""
        cache = AsyncTTLCache(max_size=2, ttl=600)
        await cache.set("url1", "content1")
        await cache.set("url2", "content2")
        await cache.set("url3", "content3")  # Should evict url1

        assert await cache.get("url1") is None
        assert await cache.get("url2") == "content2"
        assert await cache.get("url3") == "content3"

    async def test_thundering_herd(self) -> None:
        """Only one coroutine should fetch; others should wait."""
        cache = AsyncTTLCache(max_size=10, ttl=60)

        # First caller gets should_fetch=True
        content1, should_fetch1 = await cache.get_or_wait("url")
        assert should_fetch1 is True
        assert content1 is None

        # Second caller gets should_fetch=False (in-flight)
        content2, should_fetch2 = await cache.get_or_wait("url")
        assert should_fetch2 is False
        assert content2 is None

        # Simulate fetch completion
        await cache.set("url", "fetched_content")

        # Now the content is available
        result = await cache.get("url")
        assert result == "fetched_content"

    async def test_cancel_inflight(self) -> None:
        """Cancelling an in-flight fetch should release waiters."""
        cache = AsyncTTLCache(max_size=10, ttl=60)

        _, should_fetch = await cache.get_or_wait("url")
        assert should_fetch is True

        # Start a waiter task
        async def waiter():
            return await cache.wait_for_inflight("url")

        task = asyncio.create_task(waiter())

        # Cancel the in-flight fetch
        await cache.cancel_inflight("url")

        # Waiter should return None (no content cached)
        result = await task
        assert result is None

    async def test_max_size_boundary(self) -> None:
        """Cache should respect max_size exactly."""
        cache = AsyncTTLCache(max_size=3, ttl=600)
        await cache.set("a", "1")
        await cache.set("b", "2")
        await cache.set("c", "3")

        # All three should be present
        assert await cache.get("a") == "1"
        assert await cache.get("b") == "2"
        assert await cache.get("c") == "3"

        # Adding one more should evict the oldest
        await cache.set("d", "4")
        assert len(cache.cache) == 3

    async def test_clear_releases_waiters(self) -> None:
        """clear() should set all in-flight events."""
        cache = AsyncTTLCache(max_size=10, ttl=60)

        # Create in-flight entries
        _, _ = await cache.get_or_wait("url1")
        _, _ = await cache.get_or_wait("url2")

        # Start waiters
        async def waiter(url: str):
            return await cache.wait_for_inflight(url)

        task1 = asyncio.create_task(waiter("url1"))
        task2 = asyncio.create_task(waiter("url2"))

        # Allow tasks to start waiting
        await asyncio.sleep(0)

        # Clear should release all waiters
        await cache.clear()

        result1 = await task1
        result2 = await task2
        assert result1 is None
        assert result2 is None
        assert len(cache._in_flight) == 0
