"""Tests for RAG Jinja2 filters."""

import pytest

from rawagents.rag import (
    Chunk,
    SearchResult,
    format_chunk,
    format_context,
    get_rag_filters,
)


class TestFormatChunk:
    """Tests for format_chunk filter."""

    def test_basic_formatting(self) -> None:
        """Basic chunk formatting returns content."""
        chunk = Chunk(content="Hello world")
        result = format_chunk(chunk)
        assert result == "Hello world"

    def test_with_metadata_disabled(self) -> None:
        """Metadata not included by default."""
        chunk = Chunk(content="Hello", metadata={"source": "wiki"})
        result = format_chunk(chunk)
        assert result == "Hello"
        assert "source" not in result

    def test_with_metadata_enabled(self) -> None:
        """Metadata included when requested."""
        chunk = Chunk(content="Hello", metadata={"source": "wiki", "page": 5})
        result = format_chunk(chunk, include_metadata=True)

        assert "Hello" in result
        assert "source: wiki" in result
        assert "page: 5" in result

    def test_empty_metadata(self) -> None:
        """Empty metadata doesn't add brackets."""
        chunk = Chunk(content="Hello", metadata={})
        result = format_chunk(chunk, include_metadata=True)
        assert result == "Hello"

    def test_internal_metadata_hidden(self) -> None:
        """Metadata keys starting with _ are hidden."""
        chunk = Chunk(
            content="Hello",
            metadata={"_chunk_id": "internal", "source": "visible"},
        )
        result = format_chunk(chunk, include_metadata=True)

        assert "source: visible" in result
        assert "_chunk_id" not in result
        assert "internal" not in result


class TestFormatContext:
    """Tests for format_context filter."""

    def test_basic_formatting(self) -> None:
        """Basic context formatting."""
        results = [
            SearchResult(chunk=Chunk(content="First chunk"), score=0.9),
            SearchResult(chunk=Chunk(content="Second chunk"), score=0.8),
        ]
        result = format_context(results)

        assert "[1]" in result
        assert "First chunk" in result
        assert "[2]" in result
        assert "Second chunk" in result

    def test_empty_results(self) -> None:
        """Empty results return empty string."""
        result = format_context([])
        assert result == ""

    def test_custom_separator(self) -> None:
        """Custom separator is used."""
        results = [
            SearchResult(chunk=Chunk(content="A"), score=0.9),
            SearchResult(chunk=Chunk(content="B"), score=0.8),
        ]
        result = format_context(results, separator="\n\n")

        assert "---" not in result
        # Should have double newline between chunks
        assert "\n\n" in result

    def test_with_scores(self) -> None:
        """Scores included when requested."""
        results = [
            SearchResult(chunk=Chunk(content="Test"), score=0.95),
        ]
        result = format_context(results, include_scores=True)

        assert "score: 0.950" in result

    def test_without_scores(self) -> None:
        """Scores not included by default."""
        results = [
            SearchResult(chunk=Chunk(content="Test"), score=0.95),
        ]
        result = format_context(results)

        assert "score" not in result

    def test_with_metadata(self) -> None:
        """Metadata passed through to format_chunk."""
        results = [
            SearchResult(
                chunk=Chunk(content="Test", metadata={"source": "wiki"}),
                score=0.9,
            ),
        ]
        result = format_context(results, include_metadata=True)

        assert "source: wiki" in result

    def test_max_results(self) -> None:
        """Max results limits output."""
        results = [
            SearchResult(chunk=Chunk(content=f"Chunk {i}"), score=0.9 - i * 0.1)
            for i in range(5)
        ]
        result = format_context(results, max_results=2)

        assert "[1]" in result
        assert "[2]" in result
        assert "[3]" not in result

    def test_numbering(self) -> None:
        """Chunks are numbered starting from 1."""
        results = [
            SearchResult(chunk=Chunk(content="A"), score=0.9),
            SearchResult(chunk=Chunk(content="B"), score=0.8),
            SearchResult(chunk=Chunk(content="C"), score=0.7),
        ]
        result = format_context(results)

        lines = result.split("\n")
        # First line should start with [1]
        assert lines[0].startswith("[1]")


class TestGetRagFilters:
    """Tests for get_rag_filters."""

    def test_returns_dict(self) -> None:
        """Returns dictionary of filters."""
        filters = get_rag_filters()
        assert isinstance(filters, dict)

    def test_contains_expected_filters(self) -> None:
        """Contains expected filter functions."""
        filters = get_rag_filters()

        assert "format_chunk" in filters
        assert "format_context" in filters

    def test_filters_are_callable(self) -> None:
        """Filters are callable."""
        filters = get_rag_filters()

        for name, fn in filters.items():
            assert callable(fn), f"Filter {name} is not callable"

    def test_filters_work(self) -> None:
        """Filters work when called."""
        filters = get_rag_filters()

        chunk = Chunk(content="Test")
        result = filters["format_chunk"](chunk)
        assert result == "Test"

        results = [SearchResult(chunk=chunk, score=0.9)]
        context = filters["format_context"](results)
        assert "Test" in context
