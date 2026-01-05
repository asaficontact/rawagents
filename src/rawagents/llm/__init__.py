"""LLM Client - Unified interface for LLM providers.

This module provides a unified client for interacting with various LLM providers
(OpenAI, Anthropic, Google, and 100+ more via LiteLLM) with support for:

- Basic text completion
- Structured output extraction (via Pydantic models)
- Function/tool calling
- Text streaming

The client is intentionally "dumb" about tools - it returns tool call requests
but does NOT execute them. Tool execution belongs in an Agent/Orchestrator layer.

Exception Handling:
    All client methods may raise LiteLLM exceptions (OpenAI-style). Import from
    litellm.exceptions::

        from litellm.exceptions import (
            RateLimitError,           # 429 - Rate limit exceeded
            AuthenticationError,       # 401 - Invalid API key
            BadRequestError,           # 400 - Invalid request
            Timeout,                   # Request timed out
            APIConnectionError,        # Network/connection issues
            ServiceUnavailableError,   # 503 - Service unavailable
            ContentPolicyViolationError,
            ContextWindowExceededError,
        )

Example:
    >>> from rawagents import LLM
    >>> from pydantic import BaseModel
    >>>
    >>> client = LLMClient()
    >>>
    >>> # Basic completion
    >>> response = client.complete(
    ...     model="openai/gpt-4o-mini",
    ...     messages=[{"role": "user", "content": "Hello!"}]
    ... )
    >>>
    >>> # Structured output
    >>> class Person(BaseModel):
    ...     name: str
    ...     age: int
    >>>
    >>> person = client.complete_structured(
    ...     model="openai/gpt-4o-mini",
    ...     messages=[{"role": "user", "content": "John is 30 years old"}],
    ...     response_model=Person
    ... )
"""

from rawagents.llm.async_client import AsyncLLM
from rawagents.llm.client import LLM

# Aliases for backward compatibility and clearer naming
AsyncLLMClient = AsyncLLM
LLMClient = LLM
from rawagents.llm.config import LLMConfig
from rawagents.llm.types import LLMResponse, ToolCall, ToolResponse


__all__ = [
    # Primary names (short form)
    "AsyncLLM",
    "LLM",
    # Aliases (backward compatible / clearer naming)
    "AsyncLLMClient",
    "LLMClient",
    # Config and types
    "LLMConfig",
    "LLMResponse",
    "ToolCall",
    "ToolResponse",
]
