"""Type definitions for the LLM client."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from rawagents.utils.types import ToolCall

__all__ = [
    "LLMResponse",
    "ToolCall",
    "ToolResponse",
]


class LLMResponse(BaseModel):
    """Standard response from completion calls.

    Attributes:
        content: The text content of the response.
        model: The model identifier that generated the response.
        usage: Token usage statistics (prompt_tokens, completion_tokens, total_tokens).
        cost: Estimated cost in USD (from LiteLLM), None if unavailable.
        latency_ms: Request latency in milliseconds.
        raw_response: The original LiteLLM response object for advanced use cases.
        reasoning_content: The model's reasoning/thinking text (for reasoning models).
            None if reasoning was not enabled or model doesn't support it.
        reasoning_blocks: Provider-specific reasoning blocks (e.g., Anthropic's thinking_blocks).
            None if not available.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    content: str
    model: str
    usage: dict[str, int]
    cost: float | None
    latency_ms: float
    raw_response: Any = Field(repr=False)
    reasoning_content: str | None = None
    reasoning_blocks: list[dict[str, Any]] | None = None


class ToolResponse(LLMResponse):
    """Response that includes tool call requests.

    Inherits all fields from LLMResponse and adds tool_calls.

    Attributes:
        tool_calls: List of tool calls the model wants to execute.
                   Empty list if the model didn't request any tools.
    """

    tool_calls: list[ToolCall] = Field(default_factory=list)
