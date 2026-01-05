"""In-memory vector store using NumPy."""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.linalg import norm

from rawagents.rag.exceptions import VectorStoreError


__all__ = ["MemoryVectorStore"]


class MemoryVectorStore:
    """In-memory vector store using NumPy.

    A simple but efficient vector store for development and testing.
    Uses NumPy for cosine similarity calculations.

    Features:
    - Zero external dependencies (just NumPy)
    - Fast for small to medium datasets (<100k vectors)
    - Metadata filtering support
    - Score threshold filtering

    Limitations:
    - Not persistent (data lost on restart)
    - Not suitable for very large datasets
    - Single-threaded (no concurrent writes)

    Example:
        >>> store = MemoryVectorStore()
        >>> store.add(
        ...     ids=["doc1", "doc2"],
        ...     embeddings=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
        ...     metadata=[{"source": "wiki"}, {"source": "news"}],
        ... )
        >>> results = store.search([0.1, 0.2, 0.3], top_k=1)
        >>> print(results[0])  # ("doc1", 1.0, {"source": "wiki"})
    """

    def __init__(self) -> None:
        """Initialize an empty vector store."""
        self._ids: list[str] = []
        self._embeddings: np.ndarray | None = None  # shape: (n, dim)
        self._metadata: list[dict[str, Any]] = []

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

        Raises:
            VectorStoreError: If inputs are mismatched or invalid.
        """
        if not ids:
            return

        if len(ids) != len(embeddings):
            raise VectorStoreError(
                f"Number of ids ({len(ids)}) must match embeddings ({len(embeddings)})"
            )

        if metadata is not None and len(metadata) != len(ids):
            raise VectorStoreError(
                f"Number of metadata ({len(metadata)}) must match ids ({len(ids)})"
            )

        # Check for duplicate IDs
        existing_ids = set(self._ids)
        duplicates = [id_ for id_ in ids if id_ in existing_ids]
        if duplicates:
            raise VectorStoreError(f"Duplicate IDs: {duplicates}")

        # Convert to numpy array
        new_embeddings = np.array(embeddings, dtype=np.float32)

        # Check dimension consistency
        if self._embeddings is not None:
            if new_embeddings.shape[1] != self._embeddings.shape[1]:
                raise VectorStoreError(
                    f"Embedding dimension mismatch: expected {self._embeddings.shape[1]}, "
                    f"got {new_embeddings.shape[1]}"
                )

        # Add to store
        if self._embeddings is None:
            self._embeddings = new_embeddings
        else:
            self._embeddings = np.vstack([self._embeddings, new_embeddings])

        self._ids.extend(ids)
        self._metadata.extend(metadata or [{} for _ in ids])

    def search(
        self,
        embedding: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
        score_threshold: float | None = None,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        """Search for similar vectors using cosine similarity.

        Args:
            embedding: Query vector.
            top_k: Maximum number of results.
            filters: Optional metadata filters (key-value equality).
            score_threshold: Minimum cosine similarity threshold.

        Returns:
            List of (id, score, metadata) tuples, sorted by score descending.
        """
        if self._embeddings is None or len(self._ids) == 0:
            return []

        query = np.array(embedding, dtype=np.float32)

        # Cosine similarity: dot(A, B) / (norm(A) * norm(B))
        query_norm = norm(query)
        if query_norm == 0:
            return []

        embeddings_norm = norm(self._embeddings, axis=1)

        # Avoid division by zero
        valid_mask = embeddings_norm > 0
        similarities = np.zeros(len(self._ids), dtype=np.float32)
        similarities[valid_mask] = (
            np.dot(self._embeddings[valid_mask], query)
            / (embeddings_norm[valid_mask] * query_norm)
        )

        # Apply metadata filters
        mask = np.ones(len(self._ids), dtype=bool)
        if filters:
            for key, value in filters.items():
                for i, meta in enumerate(self._metadata):
                    if meta.get(key) != value:
                        mask[i] = False

        # Apply score threshold
        if score_threshold is not None:
            mask &= similarities >= score_threshold

        # Get valid indices and scores
        valid_indices = np.where(mask)[0]
        if len(valid_indices) == 0:
            return []

        valid_scores = similarities[valid_indices]

        # Get top-k indices (sorted by score descending)
        if len(valid_indices) <= top_k:
            sorted_order = np.argsort(valid_scores)[::-1]
        else:
            # Use argpartition for efficiency with large arrays
            partition_idx = np.argpartition(valid_scores, -top_k)[-top_k:]
            sorted_order = partition_idx[np.argsort(valid_scores[partition_idx])[::-1]]

        top_indices = valid_indices[sorted_order]

        return [
            (self._ids[i], float(similarities[i]), self._metadata[i])
            for i in top_indices
        ]

    def delete(self, ids: list[str]) -> None:
        """Delete vectors by ID.

        Args:
            ids: IDs of vectors to delete.
        """
        if not ids:
            return

        ids_to_delete = set(ids)
        indices_to_keep = [
            i for i, id_ in enumerate(self._ids) if id_ not in ids_to_delete
        ]

        if len(indices_to_keep) == len(self._ids):
            # Nothing to delete
            return

        self._ids = [self._ids[i] for i in indices_to_keep]
        self._metadata = [self._metadata[i] for i in indices_to_keep]

        if self._embeddings is not None:
            if len(indices_to_keep) == 0:
                self._embeddings = None
            else:
                self._embeddings = self._embeddings[indices_to_keep]

    def __len__(self) -> int:
        """Return the number of vectors in the store."""
        return len(self._ids)

    def clear(self) -> None:
        """Remove all vectors from the store."""
        self._ids = []
        self._embeddings = None
        self._metadata = []
