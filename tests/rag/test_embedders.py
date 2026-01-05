"""Tests for embedder implementations."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rawagents.rag import LiteLLMEmbedder
from rawagents.rag.exceptions import EmbeddingError


class TestLiteLLMEmbedder:
    """Tests for LiteLLMEmbedder."""

    def test_init_default_model(self) -> None:
        """Default model is set correctly."""
        embedder = LiteLLMEmbedder()
        assert embedder.model == "text-embedding-3-small"
        assert embedder.batch_size == 100

    def test_init_custom_model(self) -> None:
        """Custom model and batch size work."""
        embedder = LiteLLMEmbedder(
            model="cohere/embed-english-v3.0",
            batch_size=50,
        )
        assert embedder.model == "cohere/embed-english-v3.0"
        assert embedder.batch_size == 50

    @patch("rawagents.rag.embedders.litellm.embedding")
    def test_embed_sync(self, mock_embedding: MagicMock) -> None:
        """Synchronous embedding works."""
        # Mock response
        mock_embedding.return_value = MagicMock(
            data=[
                {"embedding": [0.1, 0.2, 0.3]},
                {"embedding": [0.4, 0.5, 0.6]},
            ]
        )

        embedder = LiteLLMEmbedder(model="test-model")
        result = embedder.embed(["hello", "world"])

        assert len(result) == 2
        assert result[0] == [0.1, 0.2, 0.3]
        assert result[1] == [0.4, 0.5, 0.6]

        mock_embedding.assert_called_once_with(
            model="test-model",
            input=["hello", "world"],
            dimensions=None,
        )

    @patch("rawagents.rag.embedders.litellm.embedding")
    def test_embed_empty_list(self, mock_embedding: MagicMock) -> None:
        """Empty list returns empty result."""
        embedder = LiteLLMEmbedder()
        result = embedder.embed([])
        assert result == []
        mock_embedding.assert_not_called()

    @patch("rawagents.rag.embedders.litellm.embedding")
    def test_embed_batching(self, mock_embedding: MagicMock) -> None:
        """Large inputs are batched."""
        # Return correct number of embeddings based on input
        def mock_embed(model: str, input: list[str], dimensions: int | None = None) -> MagicMock:
            return MagicMock(
                data=[{"embedding": [0.1, 0.2]} for _ in input]
            )

        mock_embedding.side_effect = mock_embed

        embedder = LiteLLMEmbedder(batch_size=3)
        texts = [f"text{i}" for i in range(7)]
        result = embedder.embed(texts)

        # Should be called 3 times: batch of 3, 3, 1
        assert mock_embedding.call_count == 3
        assert len(result) == 7

    @patch("rawagents.rag.embedders.litellm.embedding")
    def test_embed_error_handling(self, mock_embedding: MagicMock) -> None:
        """API errors are wrapped in EmbeddingError."""
        mock_embedding.side_effect = Exception("API error")

        embedder = LiteLLMEmbedder()
        with pytest.raises(EmbeddingError, match="Failed to embed"):
            embedder.embed(["test"])

    @patch("rawagents.rag.embedders.litellm.aembedding")
    @pytest.mark.asyncio
    async def test_aembed_async(self, mock_aembedding: MagicMock) -> None:
        """Asynchronous embedding works."""
        mock_aembedding.return_value = MagicMock(
            data=[
                {"embedding": [0.1, 0.2, 0.3]},
            ]
        )

        embedder = LiteLLMEmbedder(model="test-model")
        result = await embedder.aembed(["hello"])

        assert len(result) == 1
        assert result[0] == [0.1, 0.2, 0.3]

    @patch("rawagents.rag.embedders.litellm.aembedding")
    @pytest.mark.asyncio
    async def test_aembed_empty_list(self, mock_aembedding: MagicMock) -> None:
        """Empty list returns empty result (async)."""
        embedder = LiteLLMEmbedder()
        result = await embedder.aembed([])
        assert result == []
        mock_aembedding.assert_not_called()

    @patch("rawagents.rag.embedders.litellm.aembedding")
    @pytest.mark.asyncio
    async def test_aembed_error_handling(self, mock_aembedding: MagicMock) -> None:
        """Async API errors are wrapped in EmbeddingError."""
        mock_aembedding.side_effect = Exception("API error")

        embedder = LiteLLMEmbedder()
        with pytest.raises(EmbeddingError, match="Failed to embed"):
            await embedder.aembed(["test"])

    @patch("rawagents.rag.embedders.litellm.embedding")
    def test_dimension_property(self, mock_embedding: MagicMock) -> None:
        """Dimension property works by making a test embedding."""
        mock_embedding.return_value = MagicMock(
            data=[{"embedding": [0.1] * 1536}]  # OpenAI-like dimension
        )

        embedder = LiteLLMEmbedder()
        dim = embedder.dimension

        assert dim == 1536
        mock_embedding.assert_called_once()

        # Second call should use cached value
        dim2 = embedder.dimension
        assert dim2 == 1536
        assert mock_embedding.call_count == 1  # Still just 1 call

    @patch("rawagents.rag.embedders.litellm.embedding")
    def test_dimension_error(self, mock_embedding: MagicMock) -> None:
        """Dimension property error is wrapped."""
        mock_embedding.side_effect = Exception("API error")

        embedder = LiteLLMEmbedder()
        with pytest.raises(EmbeddingError, match="Failed to determine"):
            _ = embedder.dimension

    @patch("rawagents.rag.embedders.litellm.embedding")
    def test_dimensions_parameter(self, mock_embedding: MagicMock) -> None:
        """Dimensions parameter is passed to API."""
        mock_embedding.return_value = MagicMock(
            data=[{"embedding": [0.1] * 256}]
        )

        embedder = LiteLLMEmbedder(dimensions=256)
        embedder.embed(["test"])

        mock_embedding.assert_called_with(
            model="text-embedding-3-small",
            input=["test"],
            dimensions=256,
        )
