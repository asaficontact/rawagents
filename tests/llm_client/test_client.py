"""Tests for LLMClient."""

from typing import Any
from unittest.mock import MagicMock, patch

from pydantic import BaseModel, Field

from rawagents import LLMClient, LLMConfig, LLMResponse


class TestLLMClientInit:
    """Tests for client initialization."""

    def test_init_with_default_config(self) -> None:
        """Client initializes with default configuration."""
        client = LLMClient()
        assert client.config.model == "openai/gpt-4o-mini"
        assert client.config.structured_validation_retries == 3

    def test_init_with_custom_config(self) -> None:
        """Client initializes with custom configuration."""
        config = LLMConfig(
            model="anthropic/claude-3-5-sonnet-latest",
            structured_validation_retries=5,
            timeout=120,
        )
        client = LLMClient(config=config)
        assert client.config.model == "anthropic/claude-3-5-sonnet-latest"
        assert client.config.structured_validation_retries == 5
        assert client.config.timeout == 120

    def test_init_with_kwargs(self) -> None:
        """Client initializes with keyword arguments."""
        client = LLMClient(
            model="openai/gpt-4o",
            retries=5,
            timeout=120,
            fallbacks=["anthropic/claude-3-5-sonnet-latest"],
        )
        assert client.config.model == "openai/gpt-4o"
        assert client.config.retries == 5
        assert client.config.timeout == 120
        assert client.config.fallbacks == ["anthropic/claude-3-5-sonnet-latest"]

    def test_init_kwargs_override_config(self) -> None:
        """Kwargs override config values when both provided."""
        config = LLMConfig(
            model="openai/gpt-4o-mini",
            retries=3,
            timeout=60,
        )
        client = LLMClient(
            config=config,
            model="anthropic/claude-3-5-sonnet-latest",
            timeout=120,
        )
        # Kwargs should override
        assert client.config.model == "anthropic/claude-3-5-sonnet-latest"
        assert client.config.timeout == 120
        # Config value should be preserved when no kwarg provided
        assert client.config.retries == 3


class TestComplete:
    """Tests for the complete() method."""

    def test_complete_returns_llm_response(
        self,
        client: LLMClient,
        mock_litellm_response: MagicMock,
        sample_messages: list[dict[str, Any]],
    ) -> None:
        """complete() returns an LLMResponse with expected fields."""
        with patch("rawagents.llm.client.completion") as mock_completion:
            mock_completion.return_value = mock_litellm_response

            response = client.complete(
                model="openai/gpt-4o-mini",
                messages=sample_messages,
            )

            assert isinstance(response, LLMResponse)
            assert response.content == "Hello! How can I help you?"
            assert response.model == "gpt-4o-mini"
            assert response.usage["total_tokens"] == 18
            assert response.cost == 0.00005
            assert response.latency_ms > 0
            # Reasoning fields should be None for non-reasoning models
            assert response.reasoning_content is None
            assert response.reasoning_blocks is None

    def test_complete_uses_default_model(
        self,
        client: LLMClient,
        mock_litellm_response: MagicMock,
        sample_messages: list[dict[str, Any]],
    ) -> None:
        """complete() uses default model from config when not specified."""
        with patch("rawagents.llm.client.completion") as mock_completion:
            mock_completion.return_value = mock_litellm_response

            client.complete(messages=sample_messages)

            call_kwargs = mock_completion.call_args.kwargs
            assert call_kwargs["model"] == "openai/gpt-4o-mini"

    def test_complete_passes_parameters(
        self,
        client: LLMClient,
        mock_litellm_response: MagicMock,
        sample_messages: list[dict[str, Any]],
    ) -> None:
        """complete() passes all parameters to litellm."""
        with patch("rawagents.llm.client.completion") as mock_completion:
            mock_completion.return_value = mock_litellm_response

            client.complete(
                model="openai/gpt-4o",
                messages=sample_messages,
                temperature=0.5,
                max_tokens=100,
                metadata={"trace_id": "test-123"},
            )

            call_kwargs = mock_completion.call_args.kwargs
            assert call_kwargs["model"] == "openai/gpt-4o"
            assert call_kwargs["temperature"] == 0.5
            assert call_kwargs["max_tokens"] == 100
            assert call_kwargs["metadata"] == {"trace_id": "test-123"}

    def test_complete_passes_reasoning_effort(
        self,
        client: LLMClient,
        mock_litellm_response: MagicMock,
        sample_messages: list[dict[str, Any]],
    ) -> None:
        """complete() passes reasoning_effort parameter to litellm."""
        with patch("rawagents.llm.client.completion") as mock_completion:
            mock_completion.return_value = mock_litellm_response

            client.complete(
                model="openai/o3-mini",
                messages=sample_messages,
                reasoning_effort="high",
            )

            call_kwargs = mock_completion.call_args.kwargs
            assert call_kwargs["reasoning_effort"] == "high"

    def test_complete_excludes_reasoning_effort_when_none(
        self,
        client: LLMClient,
        mock_litellm_response: MagicMock,
        sample_messages: list[dict[str, Any]],
    ) -> None:
        """complete() does not pass reasoning_effort when not specified."""
        with patch("rawagents.llm.client.completion") as mock_completion:
            mock_completion.return_value = mock_litellm_response

            client.complete(
                model="openai/gpt-4o",
                messages=sample_messages,
            )

            call_kwargs = mock_completion.call_args.kwargs
            assert "reasoning_effort" not in call_kwargs

    def test_complete_returns_reasoning_content(
        self,
        client: LLMClient,
        mock_reasoning_response: MagicMock,
        sample_messages: list[dict[str, Any]],
    ) -> None:
        """complete() extracts reasoning content from reasoning models."""
        with patch("rawagents.llm.client.completion") as mock_completion:
            mock_completion.return_value = mock_reasoning_response

            response = client.complete(
                model="openai/o3-mini",
                messages=sample_messages,
                reasoning_effort="high",
            )

            assert response.content == "The answer is 42."
            assert response.reasoning_content == "Let me think about this step by step..."
            assert response.reasoning_blocks is not None
            assert len(response.reasoning_blocks) == 1
            assert response.reasoning_blocks[0]["type"] == "thinking"


class TestCompleteStructured:
    """Tests for the complete_structured() method."""

    def test_complete_structured_returns_model(
        self,
        client: LLMClient,
        sample_messages: list[dict[str, Any]],
    ) -> None:
        """complete_structured() returns a Pydantic model instance."""

        class Person(BaseModel):
            name: str
            age: int

        with patch.object(
            client._instructor.chat.completions,
            "create",
            return_value=Person(name="John", age=30),
        ):
            result = client.complete_structured(
                messages=sample_messages,
                response_model=Person,
            )

            assert isinstance(result, Person)
            assert result.name == "John"
            assert result.age == 30

    def test_complete_structured_with_metadata(
        self,
        client: LLMClient,
        mock_litellm_response: MagicMock,
        sample_messages: list[dict[str, Any]],
    ) -> None:
        """complete_structured() returns tuple when include_metadata=True."""

        class Person(BaseModel):
            name: str
            age: int

        person = Person(name="Jane", age=25)

        with patch.object(
            client._instructor.chat.completions,
            "create_with_completion",
            return_value=(person, mock_litellm_response),
        ):
            result, metadata = client.complete_structured(
                messages=sample_messages,
                response_model=Person,
                include_metadata=True,
            )

            assert isinstance(result, Person)
            assert result.name == "Jane"
            assert isinstance(metadata, LLMResponse)
            assert metadata.cost == 0.00005


class TestCompleteWithTools:
    """Tests for the complete_with_tools() method."""

    def test_complete_with_tools_returns_tool_calls(
        self,
        client: LLMClient,
        mock_tool_call_response: MagicMock,
        sample_messages: list[dict[str, Any]],
    ) -> None:
        """complete_with_tools() returns parsed tool calls."""

        class GetWeather(BaseModel):
            """Get weather for a location."""

            location: str = Field(description="City and state")

        with patch("rawagents.llm.client.completion") as mock_completion:
            mock_completion.return_value = mock_tool_call_response

            response = client.complete_with_tools(
                messages=sample_messages,
                tools=[GetWeather],
            )

            assert len(response.tool_calls) == 1
            assert response.tool_calls[0].name == "GetWeather"
            assert response.tool_calls[0].arguments == {"location": "New York, NY"}
            assert response.tool_calls[0].id == "call_abc123"

    def test_complete_with_tools_empty_when_no_calls(
        self,
        client: LLMClient,
        mock_litellm_response: MagicMock,
        sample_messages: list[dict[str, Any]],
    ) -> None:
        """complete_with_tools() returns empty list when model doesn't call tools."""

        class GetWeather(BaseModel):
            location: str

        with patch("rawagents.llm.client.completion") as mock_completion:
            mock_completion.return_value = mock_litellm_response

            response = client.complete_with_tools(
                messages=sample_messages,
                tools=[GetWeather],
            )

            assert response.tool_calls == []
            assert response.content == "Hello! How can I help you?"

    def test_complete_with_tools_passes_reasoning_effort(
        self,
        client: LLMClient,
        mock_tool_call_response: MagicMock,
        sample_messages: list[dict[str, Any]],
    ) -> None:
        """complete_with_tools() passes reasoning_effort parameter."""

        class GetWeather(BaseModel):
            location: str

        with patch("rawagents.llm.client.completion") as mock_completion:
            mock_completion.return_value = mock_tool_call_response

            client.complete_with_tools(
                messages=sample_messages,
                tools=[GetWeather],
                reasoning_effort="medium",
            )

            call_kwargs = mock_completion.call_args.kwargs
            assert call_kwargs["reasoning_effort"] == "medium"


class TestStream:
    """Tests for the stream() method."""

    def test_stream_yields_chunks(
        self,
        client: LLMClient,
        sample_messages: list[dict[str, Any]],
    ) -> None:
        """stream() yields text chunks."""
        chunks = [
            MagicMock(choices=[MagicMock(delta=MagicMock(content="Hello"))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content=" world"))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content="!"))]),
        ]

        with patch("rawagents.llm.client.completion") as mock_completion:
            mock_completion.return_value = iter(chunks)

            result = list(client.stream(messages=sample_messages))

            assert result == ["Hello", " world", "!"]

    def test_stream_skips_empty_chunks(
        self,
        client: LLMClient,
        sample_messages: list[dict[str, Any]],
    ) -> None:
        """stream() skips chunks with no content."""
        chunks = [
            MagicMock(choices=[MagicMock(delta=MagicMock(content="Hello"))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content=None))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content=""))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content=" world"))]),
        ]

        with patch("rawagents.llm.client.completion") as mock_completion:
            mock_completion.return_value = iter(chunks)

            result = list(client.stream(messages=sample_messages))

            assert result == ["Hello", " world"]
