"""Synchronous LLM Client."""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any, Literal, TypeVar, overload

import instructor
from litellm import completion
from pydantic import BaseModel

from rawagents.llm.config import LLMConfig
from rawagents.llm.tools import pydantic_to_tool_schema
from rawagents.llm.types import LLMResponse, ToolCall, ToolResponse


if TYPE_CHECKING:
    from collections.abc import Iterator


T = TypeVar("T", bound=BaseModel)


class LLM:
    """Synchronous LLM client.

    This client handles LLM communication only. It does NOT:
    - Execute tool calls (returns them for caller to handle)
    - Manage conversation state (caller provides full message history)
    - Run agent loops (that's a separate component)

    All methods may raise LiteLLM exceptions which map to OpenAI-style errors:
        - litellm.exceptions.RateLimitError: Rate limit exceeded (429)
        - litellm.exceptions.AuthenticationError: Invalid API key (401)
        - litellm.exceptions.BadRequestError: Invalid request (400)
        - litellm.exceptions.Timeout: Request timed out
        - litellm.exceptions.APIConnectionError: Network/connection issues
        - litellm.exceptions.ServiceUnavailableError: Service unavailable (503)
        - litellm.exceptions.ContentPolicyViolationError: Content policy violation
        - litellm.exceptions.ContextWindowExceededError: Context too long

    Example:
        >>> # Simple initialization with kwargs
        >>> client = LLM(model="openai/gpt-4o", timeout=120)
        >>>
        >>> # Or use a config object for reusable settings
        >>> config = LLMConfig(model="openai/gpt-4o", retries=5)
        >>> client = LLM(config=config)
        >>>
        >>> response = client.complete(
        ...     messages=[{"role": "user", "content": "Hello!"}]
        ... )

    Attributes:
        config: The configuration for this client.
    """

    def __init__(
        self,
        config: LLMConfig | None = None,
        *,
        model: str | None = None,
        retries: int | None = None,
        structured_validation_retries: int | None = None,
        timeout: int | None = None,
        fallbacks: list[str] | None = None,
    ) -> None:
        """Initialize the client.

        Args:
            config: Optional configuration object. If provided, kwargs override its values.
            model: Default model (e.g., "openai/gpt-4o"). Overrides config.
            retries: Number of API retries for transient errors. Overrides config.
            structured_validation_retries: Number of Pydantic validation retries. Overrides config.
            timeout: Request timeout in seconds. Overrides config.
            fallbacks: List of fallback models. Overrides config.
        """
        # Start with provided config or defaults
        base_config = config or LLMConfig()

        # Override with any provided kwargs
        self.config = LLMConfig(
            model=model if model is not None else base_config.model,
            retries=retries if retries is not None else base_config.retries,
            structured_validation_retries=(
                structured_validation_retries
                if structured_validation_retries is not None
                else base_config.structured_validation_retries
            ),
            timeout=timeout if timeout is not None else base_config.timeout,
            fallbacks=fallbacks if fallbacks is not None else base_config.fallbacks,
        )
        # Instructor client for structured output - USE from_litellm, NOT from_provider
        self._instructor = instructor.from_litellm(completion)

    def _extract_reasoning(
        self, message: Any
    ) -> tuple[str | None, list[dict[str, Any]] | None]:
        """Extract reasoning content from a response message.

        Args:
            message: The message object from the LLM response.

        Returns:
            Tuple of (reasoning_content, reasoning_blocks).
        """
        reasoning_content = getattr(message, "reasoning_content", None)
        thinking_blocks = getattr(message, "thinking_blocks", None)
        return reasoning_content, thinking_blocks

    def complete(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        reasoning_effort: Literal["low", "medium", "high"] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Basic text completion.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            model: Model identifier (e.g., "openai/gpt-4o"). Uses default if not provided.
            temperature: Sampling temperature (0.0-2.0).
            max_tokens: Maximum tokens in response.
            reasoning_effort: Reasoning depth for reasoning models ("low", "medium", "high").
                Only applicable to reasoning models (o1/o3, Claude 3.7+, Gemini 2.5+).
                LiteLLM maps this to provider-specific parameters.
            metadata: Optional metadata for logging/tracing.

        Returns:
            LLMResponse with content, usage, cost, latency, and reasoning_content if available.

        Example:
            >>> response = client.complete(
            ...     model="openai/o3-mini",
            ...     messages=[{"role": "user", "content": "Solve this math problem..."}],
            ...     reasoning_effort="high"
            ... )
            >>> print(response.reasoning_content)  # Model's reasoning process
        """
        model = model or self.config.model
        fallbacks = self.config.fallbacks or None
        metadata = metadata or {}

        # Build completion kwargs
        completion_kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "metadata": metadata,
            "num_retries": self.config.retries,
            "fallbacks": fallbacks,
            "timeout": self.config.timeout,
        }

        # Add reasoning_effort if specified
        if reasoning_effort is not None:
            completion_kwargs["reasoning_effort"] = reasoning_effort

        start = time.perf_counter()
        response = completion(**completion_kwargs)
        latency_ms = (time.perf_counter() - start) * 1000

        # Extract reasoning content if present
        message = response.choices[0].message
        reasoning_content, reasoning_blocks = self._extract_reasoning(message)

        return LLMResponse(
            content=message.content or "",
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            cost=response._hidden_params.get("response_cost"),
            latency_ms=latency_ms,
            raw_response=response,
            reasoning_content=reasoning_content,
            reasoning_blocks=reasoning_blocks,
        )

    @overload
    def complete_structured(
        self,
        messages: list[dict[str, Any]],
        response_model: type[T],
        model: str | None = None,
        *,
        temperature: float = 0.7,
        reasoning_effort: Literal["low", "medium", "high"] | None = None,
        include_metadata: Literal[False] = False,
    ) -> T: ...

    @overload
    def complete_structured(
        self,
        messages: list[dict[str, Any]],
        response_model: type[T],
        model: str | None = None,
        *,
        temperature: float = 0.7,
        reasoning_effort: Literal["low", "medium", "high"] | None = None,
        include_metadata: Literal[True],
    ) -> tuple[T, LLMResponse]: ...

    def complete_structured(
        self,
        messages: list[dict[str, Any]],
        response_model: type[T],
        model: str | None = None,
        *,
        temperature: float = 0.7,
        reasoning_effort: Literal["low", "medium", "high"] | None = None,
        include_metadata: bool = False,
    ) -> T | tuple[T, LLMResponse]:
        """Completion with Pydantic structured output.

        Uses Instructor to extract and validate structured data from the LLM response.
        Automatically retries if validation fails (configured via structured_validation_retries).

        Args:
            messages: List of message dicts.
            response_model: Pydantic model class defining the expected output structure.
            model: Model identifier. Uses default if not provided.
            temperature: Sampling temperature.
            reasoning_effort: Reasoning depth for reasoning models ("low", "medium", "high").
            include_metadata: If True, returns (model, LLMResponse) tuple for access to cost/usage.

        Returns:
            The parsed Pydantic model instance, or tuple of (model, LLMResponse) if include_metadata=True.

        Example:
            >>> class Person(BaseModel):
            ...     name: str
            ...     age: int
            >>>
            >>> person = client.complete_structured(
            ...     model="openai/gpt-4o",
            ...     messages=[{"role": "user", "content": "John is 30"}],
            ...     response_model=Person
            ... )
            >>> print(person.name, person.age)
        """
        model = model or self.config.model
        max_retries = self.config.structured_validation_retries

        # Build kwargs for instructor
        instructor_kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "response_model": response_model,
            "max_retries": max_retries,
            "temperature": temperature,
        }

        if reasoning_effort is not None:
            instructor_kwargs["reasoning_effort"] = reasoning_effort

        if include_metadata:
            start = time.perf_counter()
            parsed_result, raw = (
                self._instructor.chat.completions.create_with_completion(
                    **instructor_kwargs
                )
            )
            latency_ms = (time.perf_counter() - start) * 1000

            # Extract reasoning content if present
            message = raw.choices[0].message
            reasoning_content, reasoning_blocks = self._extract_reasoning(message)

            response_metadata = LLMResponse(
                content=message.content or "",
                model=raw.model,
                usage={
                    "prompt_tokens": raw.usage.prompt_tokens,
                    "completion_tokens": raw.usage.completion_tokens,
                    "total_tokens": raw.usage.total_tokens,
                },
                cost=raw._hidden_params.get("response_cost"),
                latency_ms=latency_ms,
                raw_response=raw,
                reasoning_content=reasoning_content,
                reasoning_blocks=reasoning_blocks,
            )
            return parsed_result, response_metadata

        # Non-metadata path
        parsed: T = self._instructor.chat.completions.create(**instructor_kwargs)
        return parsed

    def complete_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[type[BaseModel] | dict[str, Any]],
        model: str | None = None,
        *,
        tool_choice: str = "auto",
        temperature: float = 0.7,
        max_tokens: int | None = None,
        reasoning_effort: Literal["low", "medium", "high"] | None = None,
    ) -> ToolResponse:
        """Completion with tool/function calling.

        IMPORTANT: This method returns tool call REQUESTS but does NOT execute them.
        The caller is responsible for:
        1. Executing the requested tools
        2. Formatting results as tool messages
        3. Calling the client again to continue the conversation

        Args:
            messages: List of message dicts.
            tools: List of Pydantic model classes or raw JSON schemas defining available tools.
            model: Model identifier. Uses default if not provided.
            tool_choice: "auto", "required", or "none".
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in response.
            reasoning_effort: Reasoning depth for reasoning models ("low", "medium", "high").

        Returns:
            ToolResponse with tool_calls list (may be empty if model didn't call tools).

        Example:
            >>> class GetWeather(BaseModel):
            ...     '''Get weather for a location.'''
            ...     location: str
            >>>
            >>> response = client.complete_with_tools(
            ...     messages=[{"role": "user", "content": "Weather in NYC?"}],
            ...     tools=[GetWeather]
            ... )
            >>> for tool_call in response.tool_calls:
            ...     print(f"Call {tool_call.name} with {tool_call.arguments}")
        """
        model = model or self.config.model

        # Convert tools to OpenAI format (if not already dicts)
        tool_schemas: list[dict[str, Any]] = []
        for t in tools:
            if isinstance(t, dict):
                tool_schemas.append(t)
            else:
                tool_schemas.append(pydantic_to_tool_schema(t))

        # Build completion kwargs
        completion_kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "tools": tool_schemas,
            "tool_choice": tool_choice,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "num_retries": self.config.retries,
            "timeout": self.config.timeout,
        }

        if reasoning_effort is not None:
            completion_kwargs["reasoning_effort"] = reasoning_effort

        start = time.perf_counter()
        response = completion(**completion_kwargs)
        latency_ms = (time.perf_counter() - start) * 1000

        # Extract reasoning content if present
        message = response.choices[0].message
        reasoning_content, reasoning_blocks = self._extract_reasoning(message)

        # Parse tool calls from response
        tool_calls: list[ToolCall] = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=json.loads(tc.function.arguments),
                    )
                )

        return ToolResponse(
            content=message.content or "",
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            cost=response._hidden_params.get("response_cost"),
            latency_ms=latency_ms,
            raw_response=response,
            reasoning_content=reasoning_content,
            reasoning_blocks=reasoning_blocks,
            tool_calls=tool_calls,
        )

    def stream(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        """Stream text completion.

        Returns an iterator that yields text chunks as they arrive.

        NOTE: Streaming does NOT support tools or structured output in v1.0.
        Use complete_with_tools() or complete_structured() for those features.

        Args:
            messages: List of message dicts.
            model: Model identifier. Uses default if not provided.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in response.

        Yields:
            Text chunks as strings.

        Example:
            >>> for chunk in client.stream(
            ...     messages=[{"role": "user", "content": "Write a poem"}]
            ... ):
            ...     print(chunk, end="", flush=True)
        """
        model = model or self.config.model

        response = completion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            timeout=self.config.timeout,
        )

        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
