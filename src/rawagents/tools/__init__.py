"""Tool Executor - Define and execute tools for LLM agents.

The Tool Executor component is the "Hands" of the agentic system. It provides
a stateless dispatcher that manages tool definition, schema generation, and
execution with dependency injection.

Features:
    - @tool decorator to define tools from Python functions
    - Automatic JSON schema generation for LLM consumption
    - Dependency injection via Annotated[T, Inject]
    - Async-first execution with sync tool support
    - Error boundary (exceptions → ToolResult with is_error=True)
    - Before/after callbacks for logging and metrics

Example:
    >>> from typing import Annotated
    >>> from rawagents.tools import tool, ToolExecutor, Inject
    >>>
    >>> @tool
    ... def get_weather(location: str) -> str:
    ...     '''Get weather for a location.'''
    ...     return f"Sunny in {location}"
    >>>
    >>> @tool
    ... def search_db(query: str, db: Annotated[Database, Inject]) -> str:
    ...     '''Search the database.'''
    ...     return db.query(query)
    >>>
    >>> executor = ToolExecutor([get_weather, search_db])
    >>> schemas = executor.get_schemas()  # Pass to LLM
    >>>
    >>> # Execute a tool call from the LLM
    >>> result = await executor.execute(
    ...     tool_call,
    ...     context={'db': my_db_connection}
    ... )
"""

from rawagents.tools.decorator import tool
from rawagents.tools.exceptions import (
    InjectionError,
    ToolDefinitionError,
    ToolError,
    ToolExecutionError,
)
from rawagents.tools.executor import ToolExecutor
from rawagents.tools.types import Inject, ToolResult

__all__ = [
    # Core
    "tool",
    "ToolExecutor",
    "ToolResult",
    "Inject",
    # Exceptions
    "ToolError",
    "ToolDefinitionError",
    "ToolExecutionError",
    "InjectionError",
]
