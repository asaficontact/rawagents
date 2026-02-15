"""URL response caching with TTL and thundering herd prevention."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime


__all__ = [
    "AsyncTTLCache",
    "CacheEntry",
]


@dataclass
class CacheEntry:
    """A cache entry with TTL."""

    content: str
    timestamp: datetime
    ttl_seconds: int

    def is_expired(self) -> bool:
        """Check if this cache entry has expired.

        BUG FIX #1: ttl_seconds <= 0 means caching is disabled,
        so entries are always considered expired.
        """
        if self.ttl_seconds <= 0:
            return True
        elapsed = (datetime.now(UTC) - self.timestamp).total_seconds()
        return elapsed > self.ttl_seconds


class AsyncTTLCache:
    """Async-safe TTL cache with thundering herd prevention.

    Concurrent requests for the same URL share a single in-flight fetch
    via asyncio.Event, preventing duplicate HTTP requests.
    """

    def __init__(self, max_size: int = 128, ttl: int = 900):
        self.max_size = max_size
        self.ttl = ttl
        self.cache: dict[str, CacheEntry] = {}
        self.lock = asyncio.Lock()
        self._in_flight: dict[str, asyncio.Event] = {}

    async def get(self, url: str) -> str | None:
        """Get cached content for URL."""
        async with self.lock:
            entry = self.cache.get(url)
            if entry is None:
                return None
            if entry.is_expired():
                del self.cache[url]
                return None
            return entry.content

    async def get_or_wait(self, url: str) -> tuple[str | None, bool]:
        """Get cached content, or signal that caller should fetch.

        Returns:
            Tuple of (content_or_None, should_fetch).
            If should_fetch is True, caller must fetch and call set().
        """
        async with self.lock:
            entry = self.cache.get(url)
            if entry is not None and not entry.is_expired():
                return entry.content, False

            if url in self._in_flight:
                return None, False  # Another coroutine is fetching

            self._in_flight[url] = asyncio.Event()
            return None, True  # Caller should fetch

    async def wait_for_inflight(self, url: str) -> str | None:
        """Wait for an in-flight fetch to complete."""
        event = self._in_flight.get(url)
        if event:
            await event.wait()
        return await self.get(url)

    async def set(self, url: str, content: str) -> None:
        """Cache content and notify waiters."""
        async with self.lock:
            if len(self.cache) >= self.max_size:
                oldest_url = min(
                    self.cache.keys(),
                    key=lambda u: self.cache[u].timestamp,
                )
                del self.cache[oldest_url]

            self.cache[url] = CacheEntry(
                content=content,
                timestamp=datetime.now(UTC),
                ttl_seconds=self.ttl,
            )

            event = self._in_flight.pop(url, None)
            if event:
                event.set()

    async def cancel_inflight(self, url: str) -> None:
        """Cancel an in-flight fetch (e.g., on error)."""
        async with self.lock:
            event = self._in_flight.pop(url, None)
            if event:
                event.set()

    async def clear(self) -> None:
        """Clear all cache entries and in-flight tracking."""
        async with self.lock:
            self.cache.clear()
            for event in self._in_flight.values():
                event.set()
            self._in_flight.clear()
