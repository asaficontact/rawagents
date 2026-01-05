"""Recursive character text splitting strategy."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Callable

from rawagents.rag.exceptions import ChunkingError
from rawagents.rag.types import Chunk, Document


if TYPE_CHECKING:
    pass


__all__ = ["RecursiveChunker"]


class RecursiveChunker:
    """Split documents by natural boundaries (paragraphs, sentences).

    Uses a recursive approach: tries to split on the largest separator first
    (e.g., double newlines for paragraphs), then falls back to smaller
    separators (single newlines, periods, spaces) if chunks are still too large.

    Best for: Documents with natural structure (articles, documentation).
    Trade-off: More complex, but preserves semantic boundaries better.

    Default separators (in order of preference):
    1. "\\n\\n" - Paragraph breaks
    2. "\\n" - Line breaks
    3. ". " - Sentence endings
    4. " " - Word boundaries

    Args:
        chunk_size: Target size per chunk (default 512 characters).
        chunk_overlap: Overlap between consecutive chunks (default 50).
        separators: List of separators to try, in order of preference.
        length_function: Function to measure text length.

    Example:
        >>> chunker = RecursiveChunker(chunk_size=500, chunk_overlap=50)
        >>> docs = [Document(content="Paragraph 1\\n\\nParagraph 2...")]
        >>> chunks = chunker.chunk(docs)
    """

    DEFAULT_SEPARATORS: list[str] = ["\n\n", "\n", ". ", " "]

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        separators: list[str] | None = None,
        length_function: Callable[[str], int] = len,
    ) -> None:
        """Initialize the chunker.

        Args:
            chunk_size: Target size per chunk.
            chunk_overlap: Overlap between consecutive chunks.
            separators: List of separators to try, in order.
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
        self.separators = separators if separators is not None else self.DEFAULT_SEPARATORS
        self.length_function = length_function

    def chunk(self, documents: list[Document]) -> list[Chunk]:
        """Split documents into chunks using recursive splitting.

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

        # Recursively split the text
        text_splits = self._split_text(content, self.separators)

        # Merge small splits into chunks with overlap
        merged_chunks = self._merge_splits(text_splits)

        # Create Chunk objects
        chunks: list[Chunk] = []
        for position, chunk_text in enumerate(merged_chunks):
            chunk = Chunk(
                content=chunk_text,
                metadata=dict(document.metadata),
                document_id=document.id,
                id=str(uuid.uuid4()),
                position=position,
            )
            chunks.append(chunk)

        return chunks

    def _split_text(self, text: str, separators: list[str]) -> list[str]:
        """Recursively split text using separators.

        Args:
            text: Text to split.
            separators: Remaining separators to try.

        Returns:
            List of text segments.
        """
        if not separators:
            # No more separators - return text as-is (will be split by character)
            return [text] if text else []

        separator = separators[0]
        remaining_separators = separators[1:]

        # Split on current separator
        if separator in text:
            splits = text.split(separator)
        else:
            # Separator not found, try next one
            return self._split_text(text, remaining_separators)

        # Process each split
        result: list[str] = []
        for i, split in enumerate(splits):
            if not split:
                continue

            # Add separator back (except for last split)
            if i < len(splits) - 1 and separator != " ":
                split = split + separator

            # If split is still too large, recurse with remaining separators
            if self.length_function(split) > self.chunk_size:
                sub_splits = self._split_text(split, remaining_separators)
                result.extend(sub_splits)
            else:
                result.append(split)

        return result

    def _merge_splits(self, splits: list[str]) -> list[str]:
        """Merge small splits into chunks with overlap.

        Args:
            splits: List of text segments.

        Returns:
            List of merged chunks.
        """
        if not splits:
            return []

        chunks: list[str] = []
        current_chunk: list[str] = []
        current_length = 0

        for split in splits:
            split_length = self.length_function(split)

            # If adding this split would exceed chunk_size
            if current_length + split_length > self.chunk_size and current_chunk:
                # Save current chunk
                chunk_text = "".join(current_chunk)
                chunks.append(chunk_text)

                # Start new chunk with overlap
                # Find splits to keep for overlap
                overlap_splits: list[str] = []
                overlap_length = 0
                for s in reversed(current_chunk):
                    s_len = self.length_function(s)
                    if overlap_length + s_len <= self.chunk_overlap:
                        overlap_splits.insert(0, s)
                        overlap_length += s_len
                    else:
                        break

                current_chunk = overlap_splits
                current_length = overlap_length

            current_chunk.append(split)
            current_length += split_length

        # Don't forget the last chunk
        if current_chunk:
            chunk_text = "".join(current_chunk)
            chunks.append(chunk_text)

        return chunks
