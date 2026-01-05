"""Tests for AsyncLLMClient."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from rawagents import AsyncLLMClient, LLMConfig, LLMResponse


@pytest.fixture
def async_client(default_config: LLMConfig) -> AsyncLLMClient:
    """Create a test async client with default configuration."""
    return AsyncLLMClient(config=default_config)


class TestAsyncLLMClientInit:
    """Tests for async client initialization."""

    def test_init_with_default_config(self) -> None:
        """Async client initializes with default configuration."""
        client = AsyncLLM()
        assert client.config.model == "openai/gpt-4o-mini"

    def test_init_with_custom_config(self) -> None:
        """Async client initializes with custom configuration."""
        config = LLMConfig(model="anthropic/claude-3-5-sonnet-latest")
        client = AsyncLLMClient(config=config)
        assert client.config.model == "anthropic/claude-3-5-sonnet-latest"

    def test_init_with_kwargs(self) -> None:
        """Async client initializes with keyword arguments."""
        client = AsyncLLMClient(
            model="openai/gpt-4o",
            retries=5,
            timeout=120,
        )
        assert client.config.model == "openai/gpt-4o"
        assert client.config.retries == 5
        assert client.config.timeout == 120

    def test_init_kwargs_override_config(self) -> None:
        """Kwargs override config values when both provided."""
        config = LLMConfig(model="openai/gpt-4o-mini", timeout=60)
        client = AsyncLLMClient(config=config, model="openai/gpt-4o", timeout=120)
        assert client.config.model == "openai/gpt-4o"
        assert client.config.timeout == 120


class TestAsyncComplete:
    """Tests for the async complete() method."""

    @pytest.mark.asyncio
    async def test_complete_returns_llm_response(
        self,
        async_client: AsyncLLMClient,
        mock_litellm_response: MagicMock,
        sample_messages: list[dict[str, Any]],
    ) -> None:
        """async complete() returns an LLMResponse with expected fields."""
        with patch(
            "rawagents.llm.async_client.acompletion"
        ) as mock_acompletion:
            mock_acompletion.return_value = mock_litellm_response

            response = await async_client.complete(
                model="openai/gpt-4o-mini",
                messages=sample_messages,
            )

            assert isinstance(response, LLMResponse)
            assert response.content == "Hello! How can I help you?"
            assert response.model == "gpt-4o-mini"
            # Reasoning fields should be None for non-reasoning models
            assert response.reasoning_content is None
            assert response.reasoning_blocks is None

    @pytest.mark.asyncio
    async def test_complete_uses_default_model(
        self,
        async_client: AsyncLLMClient,
        mock_litellm_response: MagicMock,
        sample_messages: list[dict[str, Any]],
    ) -> None:
        """async complete() uses default model from config."""
        with patch(
            "rawagents.llm.async_client.acompletion"
        ) as mock_acompletion:
            mock_acompletion.return_value = mock_litellm_response

            await async_client.complete(messages=sample_messages)

            call_kwargs = mock_acompletion.call_args.kwargs
            assert call_kwargs["model"] == "openai/gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_complete_passes_reasoning_effort(
        self,
        async_client: AsyncLLMClient,
        mock_litellm_response: MagicMock,
        sample_messages: list[dict[str, Any]],
    ) -> None:
        """async complete() passes reasoning_effort parameter."""
        with patch(
            "rawagents.llm.async_client.acompletion"
        ) as mock_acompletion:
            mock_acompletion.return_value = mock_litellm_response

            await async_client.complete(
                model="openai/o3-mini",
                messages=sample_messages,
                reasoning_effort="high",
            )

            call_kwargs = mock_acompletion.call_args.kwargs
            assert call_kwargs["reasoning_effort"] == "high"

    @pytest.mark.asyncio
    async def test_complete_returns_reasoning_content(
        self,
        async_client: AsyncLLMClient,
        mock_reasoning_response: MagicMock,
        sample_messages: list[dict[str, Any]],
    ) -> None:
        """async complete() extracts reasoning content from reasoning models."""
        with patch(
            "rawagents.llm.async_client.acompletion"
        ) as mock_acompletion:
            mock_acompletion.return_value = mock_reasoning_response

            response = await async_client.complete(
                model="openai/o3-mini",
                messages=sample_messages,
                reasoning_effort="high",
            )

            assert response.content == "The answer is 42."
            assert response.reasoning_content == "Let me think about this step by step..."
            assert response.reasoning_blocks is not None
            assert len(response.reasoning_blocks) == 1


class TestAsyncCompleteStructured:
    """Tests for the async complete_structured() method."""

    @pytest.mark.asyncio
    async def test_complete_structured_returns_model(
        self,
        async_client: AsyncLLMClient,
        sample_messages: list[dict[str, Any]],
    ) -> None:
        """async complete_structured() returns a Pydantic model instance."""

        class Person(BaseModel):
            name: str
            age: int

        with patch.object(
            async_client._instructor.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=Person(name="John", age=30),
        ):
            result = await async_client.complete_structured(
                messages=sample_messages,
                response_model=Person,
            )

            assert isinstance(result, Person)
            assert result.name == "John"


class TestAsyncCompleteWithTools:
    """Tests for the async complete_with_tools() method."""

    @pytest.mark.asyncio
    async def test_complete_with_tools_returns_tool_calls(
        self,
        async_client: AsyncLLMClient,
        mock_tool_call_response: MagicMock,
        sample_messages: list[dict[str, Any]],
    ) -> None:
        """async complete_with_tools() returns parsed tool calls."""

        class GetWeather(BaseModel):
            location: str

        with patch(
            "rawagents.llm.async_client.acompletion"
        ) as mock_acompletion:
            mock_acompletion.return_value = mock_tool_call_response

            response = await async_client.complete_with_tools(
                messages=sample_messages,
                tools=[GetWeather],
            )

            assert len(response.tool_calls) == 1
            assert response.tool_calls[0].name == "GetWeather"

    @pytest.mark.asyncio
    async def test_complete_with_tools_passes_reasoning_effort(
        self,
        async_client: AsyncLLMClient,
        mock_tool_call_response: MagicMock,
        sample_messages: list[dict[str, Any]],
    ) -> None:
        """async complete_with_tools() passes reasoning_effort parameter."""

        class GetWeather(BaseModel):
            location: str

        with patch(
            "rawagents.llm.async_client.acompletion"
        ) as mock_acompletion:
            mock_acompletion.return_value = mock_tool_call_response

            await async_client.complete_with_tools(
                messages=sample_messages,
                tools=[GetWeather],
                reasoning_effort="medium",
            )

            call_kwargs = mock_acompletion.call_args.kwargs
            assert call_kwargs["reasoning_effort"] == "medium"


class TestAsyncStream:
    """Tests for the async stream() method."""

    @pytest.mark.asyncio
    async def test_stream_yields_chunks(
        self,
        async_client: AsyncLLMClient,
        sample_messages: list[dict[str, Any]],
    ) -> None:
        """async stream() yields text chunks."""
        chunks = [
            MagicMock(choices=[MagicMock(delta=MagicMock(content="Hello"))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content=" world"))]),
        ]

        async def async_generator():
            for chunk in chunks:
                yield chunk

        with patch(
            "rawagents.llm.async_client.acompletion"
        ) as mock_acompletion:
            mock_acompletion.return_value = async_generator()

            result = [
                chunk async for chunk in async_client.stream(messages=sample_messages)
            ]

            assert result == ["Hello", " world"]
