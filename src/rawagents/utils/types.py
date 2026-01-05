"""Shared data models for AI components.

These types are used across multiple components (LLM Client, Conversation, etc.)
to ensure compatibility and avoid circular dependencies.
"""

from typing import Any

from pydantic import BaseModel

__all__ = [
    "ToolCall",
    "ToolResult",
]


class ToolCall(BaseModel):
    """Represents a tool/function call request from the model.

    This class is used by both the LLM Client (to return requests)
    and the Conversation component (to store history).

    Attributes:
        id: Unique identifier for this tool call.
        name: The name of the tool/function to call.
        arguments: The parsed arguments as a dictionary.
    """

    id: str
    name: str
    arguments: dict[str, Any]


class ToolResult(BaseModel):
    """Result of executing a tool.

    This class is used by the Tool Executor to return results and
    integrates with the Conversation component for history storage.

    Attributes:
        tool_call_id: ID matching the original ToolCall this responds to.
        name: Name of the tool that was executed.
        content: Output as string (JSON-serialized if structured).
        is_error: True if execution failed.
    """

    tool_call_id: str
    name: str
    content: str
    is_error: bool = False
