"""Protocol definitions for RAG components.

All protocols use typing.Protocol with @runtime_checkable for duck typing.
This allows users to bring their own implementations without inheriting
from our base classes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable


if TYPE_CHECKING:
    from rawagents.rag.types import Chunk, Document, SearchResult


__all__ = [
    "Chunker",
    "Embedder",
    "VectorStore",
    "Reranker",
]


@runtime_checkable
class Chunker(Protocol):
    """Protocol for document chunking strategies.

    Chunkers split documents into smaller units for embedding and retrieval.
    Different strategies trade off between retrieval precision and context
    preservation.

    Example:
        >>> class MyChunker:
        ...     def chunk(self, documents: list[Document]) -> list[Chunk]:
        ...         # Custom chunking logic
        ...         ...
        >>>
        >>> chunker: Chunker = MyChunker()  # Works with duck typing
    """

    def chunk(self, documents: list[Document]) -> list[Chunk]:
        """Split documents into chunks.

        Args:
            documents: Source documents to chunk.

        Returns:
            List of chunks with preserved metadata and position tracking.
        """
        ...


@runtime_checkable
class Embedder(Protocol):
    """Protocol for text embedding.

    Embedders convert text into dense vector representations for semantic
    similarity search. Implementations can use any embedding provider
    (OpenAI, Cohere, local models, etc.).

    Example:
        >>> class MyEmbedder:
        ...     @property
        ...     def dimension(self) -> int:
        ...         return 384
        ...
        ...     def embed(self, texts: list[str]) -> list[list[float]]:
        ...         # Return embeddings
        ...         ...
        ...
        ...     async def aembed(self, texts: list[str]) -> list[list[float]]:
        ...         # Async version
        ...         ...
    """

    @property
    def dimension(self) -> int:
        """The dimensionality of output embeddings."""
        ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts synchronously.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors (same length as texts).
        """
        ...

    async def aembed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts asynchronously.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors (same length as texts).
        """
        ...


@runtime_checkable
class VectorStore(Protocol):
    """Protocol for vector storage and similarity search.

    This is a general-purpose vector storage primitive, NOT RAG-specific.
    It can be used for semantic search, caching, deduplication, etc.
    The VectorStore knows nothing about chunks or documents - only vectors,
    IDs, and metadata.

    The Retriever class composes an Embedder + VectorStore for RAG use cases.

    Example:
        >>> class MyVectorStore:
        ...     def add(self, ids, embeddings, metadata=None): ...
        ...     def search(self, embedding, top_k=5, filters=None, score_threshold=None): ...
        ...     def delete(self, ids): ...
    """

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        metadata: list[dict[str, Any]] | None = None,
    ) -> None:
        """Add vectors to the store.

        Args:
            ids: Unique identifiers for each vector.
            embeddings: Vector embeddings to store.
            metadata: Optional metadata for each vector.
        """
        ...

    def search(
        self,
        embedding: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
        score_threshold: float | None = None,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        """Search for similar vectors.

        Args:
            embedding: Query vector.
            top_k: Maximum number of results.
            filters: Optional metadata filters (key-value equality).
            score_threshold: Minimum score threshold.

        Returns:
            List of (id, score, metadata) tuples, sorted by score descending.
        """
        ...

    def delete(self, ids: list[str]) -> None:
        """Delete vectors by ID.

        Args:
            ids: IDs of vectors to delete.
        """
        ...


@runtime_checkable
class Reranker(Protocol):
    """Protocol for result reranking.

    Rerankers re-score search results using more expensive models for improved
    precision. Typically used in two-stage retrieval:
    1. Fast retrieval of top-N candidates (vector search)
    2. Reranking to select final top-K results (cross-encoder)

    Example:
        >>> class MyReranker:
        ...     def rerank(self, query, results, top_k=5) -> list[SearchResult]:
        ...         # Re-score using cross-encoder
        ...         ...
        ...
        ...     async def arerank(self, query, results, top_k=5) -> list[SearchResult]:
        ...         # Async version
        ...         ...
    """

    def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Rerank search results.

        Args:
            query: The original search query.
            results: Initial search results to rerank.
            top_k: Number of results to return after reranking.

        Returns:
            Reranked results, sorted by new scores.
        """
        ...

    async def arerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Async version of rerank."""
        ...
