"""Custom exceptions for the RAG component."""

from __future__ import annotations


__all__ = [
    "RAGError",
    "ChunkingError",
    "EmbeddingError",
    "VectorStoreError",
    "RetrievalError",
]


class RAGError(Exception):
    """Base exception for all RAG-related errors."""

    pass


class ChunkingError(RAGError):
    """Raised when document chunking fails.

    Examples: empty document, invalid chunk parameters.
    """

    pass


class EmbeddingError(RAGError):
    """Raised when embedding generation fails.

    Examples: API errors, invalid input text, dimension mismatch.
    """

    pass


class VectorStoreError(RAGError):
    """Raised when vector store operations fail.

    Examples: ID not found, dimension mismatch, storage backend errors.
    """

    pass


class RetrievalError(RAGError):
    """Raised when retrieval operations fail.

    Examples: store not initialized, empty results, reranker errors.
    """

    pass
