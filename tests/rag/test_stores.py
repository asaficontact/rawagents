"""Tests for vector store implementations."""

import numpy as np
import pytest

from rawagents.rag import MemoryVectorStore
from rawagents.rag.exceptions import VectorStoreError


class TestMemoryVectorStore:
    """Tests for MemoryVectorStore."""

    def test_add_and_search_basic(self) -> None:
        """Basic add and search works."""
        store = MemoryVectorStore()
        store.add(
            ids=["doc1", "doc2"],
            embeddings=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            metadata=[{"source": "a"}, {"source": "b"}],
        )

        # Search for doc1's embedding
        results = store.search([1.0, 0.0, 0.0], top_k=1)

        assert len(results) == 1
        assert results[0][0] == "doc1"  # ID
        assert results[0][1] == pytest.approx(1.0)  # Score (cosine similarity)
        assert results[0][2] == {"source": "a"}  # Metadata

    def test_cosine_similarity(self) -> None:
        """Cosine similarity is calculated correctly."""
        store = MemoryVectorStore()
        store.add(
            ids=["a", "b", "c"],
            embeddings=[
                [1.0, 0.0],  # Unit vector along x
                [0.0, 1.0],  # Unit vector along y
                [0.707, 0.707],  # ~45 degrees
            ],
        )

        # Query with x-axis vector
        results = store.search([1.0, 0.0], top_k=3)

        # Should rank: a (cos=1.0), c (cos≈0.707), b (cos=0.0)
        assert results[0][0] == "a"
        assert results[0][1] == pytest.approx(1.0, abs=0.01)

        assert results[1][0] == "c"
        assert results[1][1] == pytest.approx(0.707, abs=0.01)

        assert results[2][0] == "b"
        assert results[2][1] == pytest.approx(0.0, abs=0.01)

    def test_top_k_limiting(self) -> None:
        """Top-k limits results."""
        store = MemoryVectorStore()
        store.add(
            ids=["a", "b", "c", "d", "e"],
            embeddings=[[i, 0.0] for i in range(5)],
        )

        results = store.search([4.0, 0.0], top_k=2)
        assert len(results) == 2

    def test_metadata_filtering(self) -> None:
        """Metadata filters work."""
        store = MemoryVectorStore()
        store.add(
            ids=["a", "b", "c"],
            embeddings=[[1.0, 0.0], [1.0, 0.0], [1.0, 0.0]],
            metadata=[
                {"type": "article"},
                {"type": "video"},
                {"type": "article"},
            ],
        )

        # Filter for articles only
        results = store.search([1.0, 0.0], top_k=10, filters={"type": "article"})

        assert len(results) == 2
        assert all(r[2]["type"] == "article" for r in results)

    def test_score_threshold(self) -> None:
        """Score threshold filters results."""
        store = MemoryVectorStore()
        store.add(
            ids=["similar", "different"],
            embeddings=[[1.0, 0.0], [0.0, 1.0]],
        )

        # Only return results with similarity >= 0.5
        results = store.search([1.0, 0.0], top_k=10, score_threshold=0.5)

        assert len(results) == 1
        assert results[0][0] == "similar"

    def test_delete(self) -> None:
        """Delete removes vectors."""
        store = MemoryVectorStore()
        store.add(
            ids=["a", "b", "c"],
            embeddings=[[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]],
        )

        assert len(store) == 3

        store.delete(["b"])

        assert len(store) == 2

        # Searching should not return deleted item
        results = store.search([0.0, 1.0], top_k=10)
        ids = [r[0] for r in results]
        assert "b" not in ids

    def test_delete_nonexistent(self) -> None:
        """Deleting nonexistent IDs is a no-op."""
        store = MemoryVectorStore()
        store.add(ids=["a"], embeddings=[[1.0, 0.0]])

        # Should not raise
        store.delete(["nonexistent"])

        assert len(store) == 1

    def test_empty_store_search(self) -> None:
        """Searching empty store returns empty results."""
        store = MemoryVectorStore()
        results = store.search([1.0, 0.0], top_k=10)
        assert results == []

    def test_add_empty_list(self) -> None:
        """Adding empty list is a no-op."""
        store = MemoryVectorStore()
        store.add(ids=[], embeddings=[], metadata=[])
        assert len(store) == 0

    def test_mismatched_lengths_error(self) -> None:
        """Mismatched input lengths raise error."""
        store = MemoryVectorStore()

        with pytest.raises(VectorStoreError, match="must match"):
            store.add(
                ids=["a", "b"],
                embeddings=[[1.0, 0.0]],  # Only 1 embedding
            )

    def test_duplicate_ids_error(self) -> None:
        """Duplicate IDs raise error."""
        store = MemoryVectorStore()
        store.add(ids=["a"], embeddings=[[1.0, 0.0]])

        with pytest.raises(VectorStoreError, match="Duplicate"):
            store.add(ids=["a"], embeddings=[[0.0, 1.0]])

    def test_dimension_mismatch_error(self) -> None:
        """Different dimensions raise error."""
        store = MemoryVectorStore()
        store.add(ids=["a"], embeddings=[[1.0, 0.0, 0.0]])  # 3D

        with pytest.raises(VectorStoreError, match="dimension mismatch"):
            store.add(ids=["b"], embeddings=[[1.0, 0.0]])  # 2D

    def test_clear(self) -> None:
        """Clear removes all vectors."""
        store = MemoryVectorStore()
        store.add(
            ids=["a", "b"],
            embeddings=[[1.0, 0.0], [0.0, 1.0]],
        )

        assert len(store) == 2
        store.clear()
        assert len(store) == 0

    def test_multiple_adds(self) -> None:
        """Multiple add calls accumulate vectors."""
        store = MemoryVectorStore()
        store.add(ids=["a"], embeddings=[[1.0, 0.0]])
        store.add(ids=["b"], embeddings=[[0.0, 1.0]])

        assert len(store) == 2

        results = store.search([1.0, 0.0], top_k=10)
        assert len(results) == 2

    def test_no_metadata(self) -> None:
        """Adding without metadata uses empty dicts."""
        store = MemoryVectorStore()
        store.add(ids=["a"], embeddings=[[1.0, 0.0]])

        results = store.search([1.0, 0.0], top_k=1)
        assert results[0][2] == {}

    def test_zero_vector_query(self) -> None:
        """Zero vector query returns empty (avoid division by zero)."""
        store = MemoryVectorStore()
        store.add(ids=["a"], embeddings=[[1.0, 0.0]])

        results = store.search([0.0, 0.0], top_k=10)
        assert results == []

    def test_large_batch(self) -> None:
        """Can handle larger batches."""
        store = MemoryVectorStore()

        n = 1000
        ids = [f"doc{i}" for i in range(n)]
        # Random embeddings
        rng = np.random.default_rng(42)
        embeddings = rng.random((n, 128)).tolist()

        store.add(ids=ids, embeddings=embeddings)

        assert len(store) == n

        # Search should work
        results = store.search(embeddings[0], top_k=5)
        assert len(results) == 5
        # First result should be exact match
        assert results[0][0] == "doc0"
