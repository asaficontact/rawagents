"""Custom exceptions for the Tool Executor component."""

from __future__ import annotations

__all__ = [
    "ToolError",
    "ToolDefinitionError",
    "ToolExecutionError",
    "InjectionError",
]


class ToolError(Exception):
    """Base exception for all tool-related errors."""

    pass


class ToolDefinitionError(ToolError):
    """Raised when a tool is incorrectly defined.

    This is a developer error caught at decoration time (fail fast).
    Examples: missing type annotations, unsupported types.
    """

    pass


class ToolExecutionError(ToolError):
    """Raised when tool execution fails.

    Caught by the executor and converted to ToolResult(is_error=True).

    Attributes:
        tool_name: Name of the tool that failed.
        original_error: The original exception if available.
    """

    def __init__(
        self,
        message: str,
        tool_name: str,
        original_error: Exception | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            message: Error message.
            tool_name: Name of the tool that failed.
            original_error: The original exception if available.
        """
        super().__init__(message)
        self.tool_name = tool_name
        self.original_error = original_error


class InjectionError(ToolError):
    """Raised when dependency injection fails.

    Examples: required context parameter not provided.
    """

    pass
