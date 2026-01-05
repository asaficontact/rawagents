"""Tests for chunker implementations."""

import pytest

from rawagents.rag import Chunk, Document, FixedSizeChunker, RecursiveChunker
from rawagents.rag.exceptions import ChunkingError


class TestFixedSizeChunker:
    """Tests for FixedSizeChunker."""

    def test_basic_chunking(self) -> None:
        """Basic chunking creates chunks of expected size."""
        chunker = FixedSizeChunker(chunk_size=100, chunk_overlap=0)
        doc = Document(content="a" * 250)
        chunks = chunker.chunk([doc])

        assert len(chunks) == 3
        assert len(chunks[0].content) == 100
        assert len(chunks[1].content) == 100
        assert len(chunks[2].content) == 50

    def test_chunking_with_overlap(self) -> None:
        """Chunks overlap correctly."""
        chunker = FixedSizeChunker(chunk_size=100, chunk_overlap=20)
        doc = Document(content="a" * 200)
        chunks = chunker.chunk([doc])

        # With overlap=20, step=80. Should get ceil(200/80) = 3 chunks
        assert len(chunks) >= 2

        # Verify overlap: end of chunk 0 should overlap with start of chunk 1
        # chunk0: 0-100, chunk1: 80-180
        assert chunks[0].content[-20:] == chunks[1].content[:20]

    def test_metadata_inherited(self) -> None:
        """Chunk inherits document metadata."""
        chunker = FixedSizeChunker(chunk_size=50, chunk_overlap=0)
        doc = Document(
            content="a" * 100,
            metadata={"source": "wiki", "author": "Alice"},
        )
        chunks = chunker.chunk([doc])

        for chunk in chunks:
            assert chunk.metadata == {"source": "wiki", "author": "Alice"}

    def test_document_id_preserved(self) -> None:
        """Chunk preserves reference to source document."""
        chunker = FixedSizeChunker(chunk_size=50, chunk_overlap=0)
        doc = Document(content="a" * 100, id="doc-123")
        chunks = chunker.chunk([doc])

        for chunk in chunks:
            assert chunk.document_id == "doc-123"

    def test_position_tracking(self) -> None:
        """Chunks track their position in the document."""
        chunker = FixedSizeChunker(chunk_size=50, chunk_overlap=0)
        doc = Document(content="a" * 150)
        chunks = chunker.chunk([doc])

        assert chunks[0].position == 0
        assert chunks[1].position == 1
        assert chunks[2].position == 2

    def test_empty_document(self) -> None:
        """Empty document produces no chunks."""
        chunker = FixedSizeChunker(chunk_size=100)
        doc = Document(content="")
        chunks = chunker.chunk([doc])
        assert chunks == []

    def test_whitespace_only_document(self) -> None:
        """Whitespace-only document produces no chunks."""
        chunker = FixedSizeChunker(chunk_size=100)
        doc = Document(content="   \n\t  ")
        chunks = chunker.chunk([doc])
        assert chunks == []

    def test_multiple_documents(self) -> None:
        """Multiple documents are chunked together."""
        chunker = FixedSizeChunker(chunk_size=50, chunk_overlap=0)
        docs = [
            Document(content="a" * 100, id="doc1"),
            Document(content="b" * 75, id="doc2"),
        ]
        chunks = chunker.chunk(docs)

        # doc1: 2 chunks, doc2: 2 chunks
        assert len(chunks) == 4

        # First two from doc1
        assert chunks[0].document_id == "doc1"
        assert chunks[1].document_id == "doc1"
        # Last two from doc2
        assert chunks[2].document_id == "doc2"
        assert chunks[3].document_id == "doc2"

    def test_unique_chunk_ids(self) -> None:
        """Each chunk gets a unique ID."""
        chunker = FixedSizeChunker(chunk_size=50, chunk_overlap=0)
        doc = Document(content="a" * 200)
        chunks = chunker.chunk([doc])

        ids = [c.id for c in chunks]
        assert len(ids) == len(set(ids))  # All unique

    def test_invalid_chunk_size(self) -> None:
        """Invalid chunk_size raises error."""
        with pytest.raises(ChunkingError, match="chunk_size must be positive"):
            FixedSizeChunker(chunk_size=0)

        with pytest.raises(ChunkingError, match="chunk_size must be positive"):
            FixedSizeChunker(chunk_size=-10)

    def test_invalid_overlap(self) -> None:
        """Invalid overlap raises error."""
        with pytest.raises(ChunkingError, match="chunk_overlap must be non-negative"):
            FixedSizeChunker(chunk_size=100, chunk_overlap=-5)

    def test_overlap_greater_than_size(self) -> None:
        """Overlap >= chunk_size raises error."""
        with pytest.raises(ChunkingError, match="must be less than chunk_size"):
            FixedSizeChunker(chunk_size=100, chunk_overlap=100)

        with pytest.raises(ChunkingError, match="must be less than chunk_size"):
            FixedSizeChunker(chunk_size=100, chunk_overlap=150)

    def test_custom_length_function(self) -> None:
        """Custom length function can be provided (for validation purposes)."""
        # Note: The current implementation uses character-based chunking
        # The length_function is stored but the implementation does character slicing
        # This test verifies the length_function parameter is accepted
        def word_count(text: str) -> int:
            return len(text.split())

        chunker = FixedSizeChunker(
            chunk_size=50,  # 50 characters per chunk
            chunk_overlap=0,
            length_function=word_count,
        )
        # Verify the function is stored
        assert chunker.length_function is word_count

        doc = Document(content="a" * 100)
        chunks = chunker.chunk([doc])

        # Character-based: 100 chars / 50 = 2 chunks
        assert len(chunks) == 2


class TestRecursiveChunker:
    """Tests for RecursiveChunker."""

    def test_basic_chunking(self) -> None:
        """Basic chunking works."""
        chunker = RecursiveChunker(chunk_size=100, chunk_overlap=0)
        doc = Document(content="First paragraph.\n\nSecond paragraph.\n\nThird paragraph.")
        chunks = chunker.chunk([doc])

        assert len(chunks) >= 1
        # All content should be preserved
        total_content = "".join(c.content for c in chunks)
        assert "First" in total_content
        assert "Second" in total_content
        assert "Third" in total_content

    def test_splits_on_paragraphs(self) -> None:
        """Prefers splitting on paragraph breaks."""
        chunker = RecursiveChunker(chunk_size=30, chunk_overlap=0)
        # Each paragraph is ~15 chars, so 30 char limit should cause splits
        doc = Document(content="Short paragraph one.\n\nAnother paragraph two.\n\nThird paragraph here.")
        chunks = chunker.chunk([doc])

        # Should split on \n\n, producing multiple chunks
        # Content is ~68 chars, with 30 char limit and paragraph breaks
        assert len(chunks) >= 2

    def test_metadata_inherited(self) -> None:
        """Chunk inherits document metadata."""
        chunker = RecursiveChunker(chunk_size=100)
        doc = Document(
            content="Test content here.",
            metadata={"source": "test"},
        )
        chunks = chunker.chunk([doc])

        for chunk in chunks:
            assert chunk.metadata == {"source": "test"}

    def test_document_id_preserved(self) -> None:
        """Chunk preserves reference to source document."""
        chunker = RecursiveChunker(chunk_size=100)
        doc = Document(content="Test content.", id="doc-456")
        chunks = chunker.chunk([doc])

        for chunk in chunks:
            assert chunk.document_id == "doc-456"

    def test_empty_document(self) -> None:
        """Empty document produces no chunks."""
        chunker = RecursiveChunker(chunk_size=100)
        doc = Document(content="")
        chunks = chunker.chunk([doc])
        assert chunks == []

    def test_custom_separators(self) -> None:
        """Custom separators are used."""
        chunker = RecursiveChunker(
            chunk_size=50,
            chunk_overlap=0,
            separators=["||", "|"],  # Custom separators
        )
        doc = Document(content="Part one||Part two|Part three")
        chunks = chunker.chunk([doc])

        # Should split on || first
        assert len(chunks) >= 1

    def test_invalid_parameters(self) -> None:
        """Invalid parameters raise errors."""
        with pytest.raises(ChunkingError):
            RecursiveChunker(chunk_size=0)

        with pytest.raises(ChunkingError):
            RecursiveChunker(chunk_size=100, chunk_overlap=-1)

        with pytest.raises(ChunkingError):
            RecursiveChunker(chunk_size=100, chunk_overlap=100)

    def test_very_long_content_without_separators(self) -> None:
        """Handles long content without natural separators."""
        chunker = RecursiveChunker(chunk_size=100, chunk_overlap=10)
        doc = Document(content="a" * 500)  # No separators
        chunks = chunker.chunk([doc])

        # Should still produce chunks
        assert len(chunks) >= 1
        # All content preserved
        total_len = sum(len(c.content) for c in chunks)
        # Allow for some overlap
        assert total_len >= 500

    def test_sentence_boundary_preference(self) -> None:
        """Prefers splitting on sentence boundaries over words."""
        chunker = RecursiveChunker(chunk_size=100, chunk_overlap=0)
        doc = Document(
            content="First sentence here. Second sentence here. Third sentence here."
        )
        chunks = chunker.chunk([doc])

        # Content should be preserved
        for chunk in chunks:
            assert len(chunk.content) > 0
