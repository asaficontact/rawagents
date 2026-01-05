"""Tests for the Retriever class."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from rawagents.rag import Chunk, MemoryVectorStore, Retriever, SearchResult
from rawagents.rag.exceptions import RetrievalError


class MockEmbedder:
    """Mock embedder for testing."""

    def __init__(self, dim: int = 3) -> None:
        self._dimension = dim
        self._embed_calls: list[list[str]] = []

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        self._embed_calls.append(texts)
        # Return simple hash-based embeddings
        return [[hash(t) % 100 / 100, 0.5, 0.5] for t in texts]

    async def aembed(self, texts: list[str]) -> list[list[float]]:
        return self.embed(texts)


class MockReranker:
    """Mock reranker for testing."""

    def __init__(self, reverse: bool = False) -> None:
        self.reverse = reverse
        self.rerank_calls: list[tuple[str, int]] = []

    def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int = 5,
    ) -> list[SearchResult]:
        self.rerank_calls.append((query, len(results)))
        # Simply reverse order if configured
        if self.reverse:
            return list(reversed(results))[:top_k]
        return results[:top_k]

    async def arerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int = 5,
    ) -> list[SearchResult]:
        return self.rerank(query, results, top_k)


class TestRetriever:
    """Tests for Retriever."""

    def test_add_chunks_sync(self) -> None:
        """Add chunks synchronously."""
        embedder = MockEmbedder()
        store = MemoryVectorStore()
        retriever = Retriever(embedder, store)

        chunks = [
            Chunk(content="Hello world", id="c1"),
            Chunk(content="Goodbye world", id="c2"),
        ]
        retriever.add(chunks)

        assert len(retriever) == 2
        assert len(store) == 2

    @pytest.mark.asyncio
    async def test_add_chunks_async(self) -> None:
        """Add chunks asynchronously."""
        embedder = MockEmbedder()
        store = MemoryVectorStore()
        retriever = Retriever(embedder, store)

        chunks = [
            Chunk(content="Hello world", id="c1"),
        ]
        await retriever.aadd(chunks)

        assert len(retriever) == 1

    def test_add_empty_list(self) -> None:
        """Adding empty list is a no-op."""
        embedder = MockEmbedder()
        store = MemoryVectorStore()
        retriever = Retriever(embedder, store)

        retriever.add([])
        assert len(retriever) == 0

    def test_retrieve_basic(self) -> None:
        """Basic retrieval works."""
        embedder = MockEmbedder()
        store = MemoryVectorStore()
        retriever = Retriever(embedder, store)

        chunks = [
            Chunk(content="Python programming", id="c1"),
            Chunk(content="Java programming", id="c2"),
            Chunk(content="Cooking recipes", id="c3"),
        ]
        retriever.add(chunks)

        results = retriever.retrieve("programming", top_k=2)

        assert len(results) == 2
        assert all(isinstance(r, SearchResult) for r in results)
        assert all(isinstance(r.chunk, Chunk) for r in results)

    @pytest.mark.asyncio
    async def test_retrieve_async(self) -> None:
        """Async retrieval works."""
        embedder = MockEmbedder()
        store = MemoryVectorStore()
        retriever = Retriever(embedder, store)

        chunks = [Chunk(content="Test content", id="c1")]
        await retriever.aadd(chunks)

        results = await retriever.aretrieve("test", top_k=1)

        assert len(results) == 1

    def test_retrieve_with_reranker(self) -> None:
        """Reranker is applied when available."""
        embedder = MockEmbedder()
        store = MemoryVectorStore()
        reranker = MockReranker(reverse=True)
        retriever = Retriever(embedder, store, reranker=reranker)

        chunks = [
            Chunk(content="A", id="c1"),
            Chunk(content="B", id="c2"),
            Chunk(content="C", id="c3"),
        ]
        retriever.add(chunks)

        results = retriever.retrieve("query", top_k=2)

        # Reranker should have been called
        assert len(reranker.rerank_calls) == 1
        assert results is not None

    def test_retrieve_without_rerank(self) -> None:
        """Can disable reranking."""
        embedder = MockEmbedder()
        store = MemoryVectorStore()
        reranker = MockReranker()
        retriever = Retriever(embedder, store, reranker=reranker)

        chunks = [Chunk(content="Test", id="c1")]
        retriever.add(chunks)

        # Disable reranking
        results = retriever.retrieve("query", top_k=1, rerank=False)

        # Reranker should not be called
        assert len(reranker.rerank_calls) == 0
        assert len(results) == 1

    def test_retrieve_with_filters(self) -> None:
        """Metadata filters are passed through."""
        embedder = MockEmbedder()
        store = MemoryVectorStore()
        retriever = Retriever(embedder, store)

        # Note: filters are stored in VectorStore metadata, not Chunk metadata
        # The retriever stores chunks by ID and retrieves them from cache
        chunks = [
            Chunk(content="Article A", id="c1", metadata={"type": "article"}),
            Chunk(content="Video B", id="c2", metadata={"type": "video"}),
        ]
        retriever.add(chunks)

        # This test verifies filters parameter is accepted
        # (actual filtering depends on VectorStore implementation)
        results = retriever.retrieve("query", filters={"type": "article"})
        assert isinstance(results, list)

    def test_delete_chunks(self) -> None:
        """Chunks can be deleted."""
        embedder = MockEmbedder()
        store = MemoryVectorStore()
        retriever = Retriever(embedder, store)

        chunks = [
            Chunk(content="A", id="c1"),
            Chunk(content="B", id="c2"),
        ]
        retriever.add(chunks)
        assert len(retriever) == 2

        retriever.delete(["c1"])
        assert len(retriever) == 1

    def test_retrieve_empty_store(self) -> None:
        """Retrieving from empty store returns empty list."""
        embedder = MockEmbedder()
        store = MemoryVectorStore()
        retriever = Retriever(embedder, store)

        results = retriever.retrieve("query", top_k=5)
        assert results == []

    def test_top_k_respected(self) -> None:
        """Top-k limits results."""
        embedder = MockEmbedder()
        store = MemoryVectorStore()
        retriever = Retriever(embedder, store)

        chunks = [Chunk(content=f"Doc {i}", id=f"c{i}") for i in range(10)]
        retriever.add(chunks)

        results = retriever.retrieve("query", top_k=3)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_aretrieve_with_reranker(self) -> None:
        """Async retrieval uses async reranker."""
        embedder = MockEmbedder()
        store = MemoryVectorStore()
        reranker = MockReranker()
        retriever = Retriever(embedder, store, reranker=reranker)

        chunks = [Chunk(content="Test", id="c1")]
        await retriever.aadd(chunks)

        results = await retriever.aretrieve("query", top_k=1)

        assert len(reranker.rerank_calls) == 1

    def test_chunk_content_preserved(self) -> None:
        """Retrieved chunks have correct content."""
        embedder = MockEmbedder()
        store = MemoryVectorStore()
        retriever = Retriever(embedder, store)

        original_chunk = Chunk(
            content="Original content here",
            metadata={"source": "test"},
            id="my-id",
        )
        retriever.add([original_chunk])

        results = retriever.retrieve("query", top_k=1)

        assert len(results) == 1
        assert results[0].chunk.content == "Original content here"
        assert results[0].chunk.metadata == {"source": "test"}
        assert results[0].chunk.id == "my-id"

    def test_error_handling(self) -> None:
        """Errors are wrapped in RetrievalError."""

        class FailingEmbedder:
            @property
            def dimension(self) -> int:
                return 3

            def embed(self, texts: list[str]) -> list[list[float]]:
                raise RuntimeError("Embedding failed")

            async def aembed(self, texts: list[str]) -> list[list[float]]:
                raise RuntimeError("Embedding failed")

        embedder = FailingEmbedder()
        store = MemoryVectorStore()
        retriever = Retriever(embedder, store)  # type: ignore

        chunks = [Chunk(content="Test", id="c1")]

        with pytest.raises(RetrievalError, match="Failed to add"):
            retriever.add(chunks)
