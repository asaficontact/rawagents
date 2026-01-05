"""Tests for RAG type definitions."""

import uuid

import pytest

from rawagents.rag import Chunk, Document, SearchResult


class TestDocument:
    """Tests for Document dataclass."""

    def test_create_with_content_only(self) -> None:
        """Document can be created with just content."""
        doc = Document(content="Hello world")
        assert doc.content == "Hello world"
        assert doc.metadata == {}
        assert doc.id is not None
        # ID should be a valid UUID
        uuid.UUID(doc.id)

    def test_create_with_metadata(self) -> None:
        """Document can be created with metadata."""
        doc = Document(
            content="Test content",
            metadata={"source": "wiki", "author": "Alice"},
        )
        assert doc.content == "Test content"
        assert doc.metadata == {"source": "wiki", "author": "Alice"}

    def test_create_with_custom_id(self) -> None:
        """Document can be created with a custom ID."""
        doc = Document(content="Test", id="custom-id-123")
        assert doc.id == "custom-id-123"

    def test_unique_ids_by_default(self) -> None:
        """Each document gets a unique ID by default."""
        doc1 = Document(content="A")
        doc2 = Document(content="B")
        assert doc1.id != doc2.id


class TestChunk:
    """Tests for Chunk dataclass."""

    def test_create_with_content_only(self) -> None:
        """Chunk can be created with just content."""
        chunk = Chunk(content="Chunk text")
        assert chunk.content == "Chunk text"
        assert chunk.metadata == {}
        assert chunk.document_id is None
        assert chunk.position is None
        assert chunk.id is not None

    def test_create_with_all_fields(self) -> None:
        """Chunk can be created with all fields."""
        chunk = Chunk(
            content="Chunk text",
            metadata={"source": "wiki"},
            document_id="doc-123",
            id="chunk-456",
            position=3,
        )
        assert chunk.content == "Chunk text"
        assert chunk.metadata == {"source": "wiki"}
        assert chunk.document_id == "doc-123"
        assert chunk.id == "chunk-456"
        assert chunk.position == 3

    def test_unique_ids_by_default(self) -> None:
        """Each chunk gets a unique ID by default."""
        chunk1 = Chunk(content="A")
        chunk2 = Chunk(content="B")
        assert chunk1.id != chunk2.id


class TestSearchResult:
    """Tests for SearchResult dataclass."""

    def test_create_search_result(self) -> None:
        """SearchResult can be created with chunk and score."""
        chunk = Chunk(content="Found this")
        result = SearchResult(chunk=chunk, score=0.95)
        assert result.chunk is chunk
        assert result.score == 0.95

    def test_search_result_with_zero_score(self) -> None:
        """SearchResult can have zero score."""
        chunk = Chunk(content="Low relevance")
        result = SearchResult(chunk=chunk, score=0.0)
        assert result.score == 0.0

    def test_search_result_with_negative_score(self) -> None:
        """SearchResult can have negative score (for some distance metrics)."""
        chunk = Chunk(content="L2 distance")
        result = SearchResult(chunk=chunk, score=-1.5)
        assert result.score == -1.5
