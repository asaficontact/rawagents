"""Retriever class that composes Embedder + VectorStore for RAG retrieval."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rawagents.rag.exceptions import RetrievalError
from rawagents.rag.types import Chunk, SearchResult


if TYPE_CHECKING:
    from rawagents.rag.protocols import Embedder, Reranker, VectorStore


__all__ = ["Retriever"]


class Retriever:
    """Composes Embedder + VectorStore for RAG retrieval.

    The Retriever is the main entry point for RAG operations. It:
    1. Accepts chunks (pre-processed document segments)
    2. Embeds them using the Embedder
    3. Stores them in the VectorStore
    4. Retrieves relevant chunks for queries

    The separation of Embedder and VectorStore allows maximum flexibility -
    you can swap either component without changing the other.

    Args:
        embedder: Embedder instance for text vectorization.
        store: VectorStore instance for vector storage and search.
        reranker: Optional Reranker for two-stage retrieval.

    Example:
        >>> from rawagents.rag import LiteLLMEmbedder, MemoryVectorStore, Retriever
        >>>
        >>> embedder = LiteLLMEmbedder(model="text-embedding-3-small")
        >>> store = MemoryVectorStore()
        >>> retriever = Retriever(embedder, store)
        >>>
        >>> # Add chunks
        >>> retriever.add(chunks)
        >>>
        >>> # Retrieve
        >>> results = retriever.retrieve("What is X?", top_k=5)
    """

    def __init__(
        self,
        embedder: Embedder,
        store: VectorStore,
        reranker: Reranker | None = None,
    ) -> None:
        """Initialize the retriever.

        Args:
            embedder: Embedder instance for text vectorization.
            store: VectorStore instance for vector storage and search.
            reranker: Optional Reranker for two-stage retrieval.
        """
        self.embedder = embedder
        self.store = store
        self.reranker = reranker
        # Cache chunks by ID for retrieval (VectorStore only stores metadata)
        self._chunk_cache: dict[str, Chunk] = {}

    def add(self, chunks: list[Chunk]) -> None:
        """Add chunks to the retriever (sync).

        Embeds the chunk contents and stores them in the vector store.
        The full Chunk objects are cached locally for retrieval.

        Args:
            chunks: List of chunks to add.

        Raises:
            RetrievalError: If embedding or storage fails.
        """
        if not chunks:
            return

        try:
            texts = [c.content for c in chunks]
            embeddings = self.embedder.embed(texts)
            ids = [c.id for c in chunks]

            # Store chunk metadata + reference in VectorStore metadata
            metadata = [
                {**c.metadata, "_chunk_id": c.id}
                for c in chunks
            ]

            self.store.add(ids, embeddings, metadata)

            # Cache chunks locally
            for c in chunks:
                self._chunk_cache[c.id] = c

        except Exception as e:
            raise RetrievalError(f"Failed to add chunks: {e}") from e

    async def aadd(self, chunks: list[Chunk]) -> None:
        """Add chunks to the retriever (async).

        Embeds the chunk contents and stores them in the vector store.
        The full Chunk objects are cached locally for retrieval.

        Args:
            chunks: List of chunks to add.

        Raises:
            RetrievalError: If embedding or storage fails.
        """
        if not chunks:
            return

        try:
            texts = [c.content for c in chunks]
            embeddings = await self.embedder.aembed(texts)
            ids = [c.id for c in chunks]

            # Store chunk metadata + reference in VectorStore metadata
            metadata = [
                {**c.metadata, "_chunk_id": c.id}
                for c in chunks
            ]

            self.store.add(ids, embeddings, metadata)

            # Cache chunks locally
            for c in chunks:
                self._chunk_cache[c.id] = c

        except Exception as e:
            raise RetrievalError(f"Failed to add chunks: {e}") from e

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
        rerank: bool = True,
    ) -> list[SearchResult]:
        """Retrieve relevant chunks (sync).

        Args:
            query: The search query.
            top_k: Maximum number of results to return.
            filters: Optional metadata filters passed to VectorStore.
            rerank: Whether to use the reranker (if available).

        Returns:
            List of SearchResults with chunks and scores.

        Raises:
            RetrievalError: If retrieval fails.
        """
        try:
            # Embed query
            query_embedding = self.embedder.embed([query])[0]

            # Retrieve more candidates if reranking
            fetch_k = top_k * 3 if (rerank and self.reranker) else top_k
            raw_results = self.store.search(
                query_embedding, top_k=fetch_k, filters=filters
            )

            # Convert to SearchResults
            results = self._build_results(raw_results)

            # Rerank if available
            if rerank and self.reranker and results:
                results = self.reranker.rerank(query, results, top_k=top_k)

            return results[:top_k]

        except Exception as e:
            raise RetrievalError(f"Failed to retrieve: {e}") from e

    async def aretrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
        rerank: bool = True,
    ) -> list[SearchResult]:
        """Retrieve relevant chunks (async).

        Args:
            query: The search query.
            top_k: Maximum number of results to return.
            filters: Optional metadata filters passed to VectorStore.
            rerank: Whether to use the reranker (if available).

        Returns:
            List of SearchResults with chunks and scores.

        Raises:
            RetrievalError: If retrieval fails.
        """
        try:
            # Embed query
            query_embedding = (await self.embedder.aembed([query]))[0]

            # Retrieve more candidates if reranking
            fetch_k = top_k * 3 if (rerank and self.reranker) else top_k
            raw_results = self.store.search(
                query_embedding, top_k=fetch_k, filters=filters
            )

            # Convert to SearchResults
            results = self._build_results(raw_results)

            # Rerank if available
            if rerank and self.reranker and results:
                results = await self.reranker.arerank(query, results, top_k=top_k)

            return results[:top_k]

        except Exception as e:
            raise RetrievalError(f"Failed to retrieve: {e}") from e

    def _build_results(
        self, raw_results: list[tuple[str, float, dict[str, Any]]]
    ) -> list[SearchResult]:
        """Convert raw VectorStore results to SearchResults.

        Args:
            raw_results: List of (id, score, metadata) tuples.

        Returns:
            List of SearchResult objects.
        """
        results: list[SearchResult] = []

        for id_, score, metadata in raw_results:
            # Look up chunk from cache
            chunk = self._chunk_cache.get(id_)
            if chunk is None:
                # Chunk not found in cache - skip
                continue

            results.append(SearchResult(chunk=chunk, score=score))

        return results

    def delete(self, chunk_ids: list[str]) -> None:
        """Delete chunks by ID.

        Args:
            chunk_ids: IDs of chunks to delete.
        """
        if not chunk_ids:
            return

        self.store.delete(chunk_ids)

        # Remove from cache
        for id_ in chunk_ids:
            self._chunk_cache.pop(id_, None)

    def __len__(self) -> int:
        """Return the number of chunks in the retriever."""
        return len(self._chunk_cache)
