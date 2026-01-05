"""Tests for LLMConfig."""

import pytest
from pydantic import ValidationError

from rawagents import LLMConfig


class TestLLMConfig:
    """Tests for LLMConfig Pydantic model."""

    def test_default_values(self) -> None:
        """Config has sensible defaults."""
        config = LLMConfig()

        assert config.model == "openai/gpt-4o-mini"
        assert config.retries == 3
        assert config.structured_validation_retries == 3
        assert config.timeout == 60
        assert config.fallbacks == []

    def test_custom_values(self) -> None:
        """Config accepts custom values."""
        config = LLMConfig(
            model="anthropic/claude-3-5-sonnet-latest",
            retries=2,
            structured_validation_retries=5,
            timeout=120,
            fallbacks=["openai/gpt-4o-mini"],
        )

        assert config.model == "anthropic/claude-3-5-sonnet-latest"
        assert config.retries == 2
        assert config.structured_validation_retries == 5
        assert config.timeout == 120
        assert config.fallbacks == ["openai/gpt-4o-mini"]

    def test_invalid_structured_validation_retries_raises(self) -> None:
        """Negative structured_validation_retries raises ValidationError."""
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            LLMConfig(structured_validation_retries=-1)

    def test_invalid_retries_raises(self) -> None:
        """Negative retries raises ValidationError."""
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            LLMConfig(retries=-1)

    def test_invalid_timeout_raises(self) -> None:
        """Non-positive timeout raises ValidationError."""
        with pytest.raises(ValidationError, match="greater than 0"):
            LLMConfig(timeout=0)

        with pytest.raises(ValidationError, match="greater than 0"):
            LLMConfig(timeout=-10)

    def test_zero_retries_valid(self) -> None:
        """Zero retries is valid (disable retries)."""
        config = LLMConfig(retries=0, structured_validation_retries=0)
        assert config.retries == 0
        assert config.structured_validation_retries == 0
