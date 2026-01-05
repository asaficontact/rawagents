"""Core type definitions for the RAG component."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


__all__ = [
    "Document",
    "Chunk",
    "SearchResult",
]


class Document(BaseModel):
    """A source document before chunking.

    Represents a complete document that will be split into smaller chunks
    for embedding and retrieval. Documents can carry arbitrary metadata
    that will be inherited by their chunks.

    Attributes:
        content: The full text content of the document.
        metadata: Arbitrary metadata (source, author, date, etc.).
        id: Unique identifier. Auto-generated if not provided.

    Example:
        >>> doc = Document(
        ...     content="This is a long document...",
        ...     metadata={"source": "wiki", "author": "Alice"},
        ... )
    """

    content: str = Field(description="The full text content of the document")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary metadata (source, author, date, etc.)",
    )
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier. Auto-generated if not provided.",
    )


class Chunk(BaseModel):
    """A chunk of a document, ready for embedding.

    Represents a segment of a document that has been split by a Chunker.
    Chunks are the atomic units of retrieval - they get embedded and stored
    in a VectorStore.

    Attributes:
        content: The text content of the chunk.
        metadata: Inherited from document + chunk-specific metadata.
        document_id: Reference to the source document.
        id: Unique identifier for this chunk.
        position: Position within the document (0-indexed).
            Used for context expansion and parent-document retrieval.

    Example:
        >>> chunk = Chunk(
        ...     content="First paragraph of the document...",
        ...     metadata={"source": "wiki"},
        ...     document_id="doc-123",
        ...     position=0,
        ... )
    """

    content: str = Field(description="The text content of the chunk")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Inherited from document + chunk-specific metadata",
    )
    document_id: str | None = Field(
        default=None,
        description="Reference to the source document",
    )
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this chunk",
    )
    position: int | None = Field(
        default=None,
        description="Position within the document (0-indexed)",
    )


class SearchResult(BaseModel):
    """A retrieved chunk with relevance score.

    Returned by retrieval operations, containing both the matched chunk
    and a relevance score indicating how well it matches the query.

    Attributes:
        chunk: The retrieved chunk.
        score: Relevance score (higher = more relevant).
            Score semantics depend on the vector store and similarity metric
            (cosine similarity, L2 distance, dot product, etc.).

    Example:
        >>> result = SearchResult(chunk=my_chunk, score=0.95)
        >>> print(f"Found: {result.chunk.content[:50]}... (score: {result.score:.3f})")
    """

    chunk: Chunk = Field(description="The retrieved chunk")
    score: float = Field(
        description="Relevance score (higher = more relevant)",
    )
