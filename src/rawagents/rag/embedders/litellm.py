"""LiteLLM-based embedder supporting 100+ embedding providers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from litellm import aembedding, embedding

from rawagents.rag.exceptions import EmbeddingError


if TYPE_CHECKING:
    pass


__all__ = ["LiteLLMEmbedder"]


class LiteLLMEmbedder:
    """Embedder using LiteLLM (100+ providers).

    Supports any embedding model available through LiteLLM, including:
    - OpenAI (text-embedding-3-small, text-embedding-3-large, text-embedding-ada-002)
    - Cohere (embed-english-v3.0, embed-multilingual-v3.0)
    - Voyage AI (voyage-2, voyage-code-2)
    - Azure OpenAI, AWS Bedrock, and many more

    Args:
        model: LiteLLM model identifier (default "text-embedding-3-small").
            Use provider prefix for non-OpenAI models (e.g., "cohere/embed-english-v3.0").
        batch_size: Maximum texts per API call (default 100).
            Large batches are more efficient but may hit API limits.
        dimensions: Optional dimension override for models that support it.
            Only supported by some models (e.g., text-embedding-3-*).

    Example:
        >>> embedder = LiteLLMEmbedder(model="text-embedding-3-small")
        >>> vectors = embedder.embed(["Hello world", "Goodbye world"])
        >>> print(len(vectors[0]))  # 1536
        >>>
        >>> # Async usage
        >>> vectors = await embedder.aembed(["Hello world"])
    """

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        batch_size: int = 100,
        dimensions: int | None = None,
    ) -> None:
        """Initialize the embedder.

        Args:
            model: LiteLLM model identifier.
            batch_size: Maximum texts per API call.
            dimensions: Optional dimension override.
        """
        self.model = model
        self.batch_size = batch_size
        self.dimensions = dimensions
        self._dimension: int | None = None

    @property
    def dimension(self) -> int:
        """Get the embedding dimension.

        Lazily determined by embedding a test string on first access.

        Returns:
            The dimensionality of output embeddings.
        """
        if self._dimension is None:
            # Embed a test string to get dimension
            try:
                result = embedding(
                    model=self.model,
                    input=["test"],
                    dimensions=self.dimensions,
                )
                self._dimension = len(result.data[0]["embedding"])
            except Exception as e:
                raise EmbeddingError(f"Failed to determine embedding dimension: {e}") from e
        return self._dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts synchronously.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors (same length as texts).

        Raises:
            EmbeddingError: If embedding fails.
        """
        if not texts:
            return []

        try:
            all_embeddings: list[list[float]] = []

            # Process in batches
            for i in range(0, len(texts), self.batch_size):
                batch = texts[i : i + self.batch_size]
                response = embedding(
                    model=self.model,
                    input=batch,
                    dimensions=self.dimensions,
                )
                batch_embeddings = [item["embedding"] for item in response.data]
                all_embeddings.extend(batch_embeddings)

            return all_embeddings

        except Exception as e:
            raise EmbeddingError(f"Failed to embed texts: {e}") from e

    async def aembed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts asynchronously.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors (same length as texts).

        Raises:
            EmbeddingError: If embedding fails.
        """
        if not texts:
            return []

        try:
            all_embeddings: list[list[float]] = []

            # Process in batches
            for i in range(0, len(texts), self.batch_size):
                batch = texts[i : i + self.batch_size]
                response = await aembedding(
                    model=self.model,
                    input=batch,
                    dimensions=self.dimensions,
                )
                batch_embeddings = [item["embedding"] for item in response.data]
                all_embeddings.extend(batch_embeddings)

            return all_embeddings

        except Exception as e:
            raise EmbeddingError(f"Failed to embed texts: {e}") from e
