"""Fixed-size chunking strategy."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Callable

from rawagents.rag.exceptions import ChunkingError
from rawagents.rag.types import Chunk, Document


if TYPE_CHECKING:
    pass


__all__ = ["FixedSizeChunker"]


class FixedSizeChunker:
    """Split documents into fixed-size chunks with overlap.

    Uses a sliding window approach to create chunks of a target size,
    with configurable overlap between consecutive chunks. Simple and
    predictable, but may split mid-sentence.

    Best for: Homogeneous content (news articles, blog posts).
    Trade-off: May split mid-sentence, but predictable behavior.

    Args:
        chunk_size: Target size per chunk (default 512 characters).
        chunk_overlap: Overlap between consecutive chunks (default 50).
        length_function: Function to measure text length.
            Default is len() for characters. Use tiktoken for tokens.

    Example:
        >>> chunker = FixedSizeChunker(chunk_size=500, chunk_overlap=50)
        >>> docs = [Document(content="Long text...")]
        >>> chunks = chunker.chunk(docs)
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        length_function: Callable[[str], int] = len,
    ) -> None:
        """Initialize the chunker.

        Args:
            chunk_size: Target size per chunk.
            chunk_overlap: Overlap between consecutive chunks.
            length_function: Function to measure text length.

        Raises:
            ChunkingError: If parameters are invalid.
        """
        if chunk_size <= 0:
            raise ChunkingError(f"chunk_size must be positive, got {chunk_size}")
        if chunk_overlap < 0:
            raise ChunkingError(f"chunk_overlap must be non-negative, got {chunk_overlap}")
        if chunk_overlap >= chunk_size:
            raise ChunkingError(
                f"chunk_overlap ({chunk_overlap}) must be less than chunk_size ({chunk_size})"
            )

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.length_function = length_function

    def chunk(self, documents: list[Document]) -> list[Chunk]:
        """Split documents into fixed-size chunks.

        Args:
            documents: Source documents to chunk.

        Returns:
            List of chunks with preserved metadata and position tracking.
        """
        all_chunks: list[Chunk] = []

        for doc in documents:
            doc_chunks = self._chunk_document(doc)
            all_chunks.extend(doc_chunks)

        return all_chunks

    def _chunk_document(self, document: Document) -> list[Chunk]:
        """Chunk a single document.

        Args:
            document: Document to chunk.

        Returns:
            List of chunks from this document.
        """
        content = document.content
        if not content or not content.strip():
            return []

        chunks: list[Chunk] = []
        step = self.chunk_size - self.chunk_overlap
        position = 0
        start = 0

        while start < len(content):
            # Get the chunk text
            end = start + self.chunk_size
            chunk_text = content[start:end]

            # Skip if chunk is empty (shouldn't happen, but be safe)
            if not chunk_text.strip():
                start += step
                continue

            # Create chunk with inherited metadata
            chunk = Chunk(
                content=chunk_text,
                metadata=dict(document.metadata),  # Copy metadata
                document_id=document.id,
                id=str(uuid.uuid4()),
                position=position,
            )
            chunks.append(chunk)

            position += 1
            start += step

        return chunks
