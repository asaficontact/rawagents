"""ToolExecutor for safe execution of tools with dependency injection."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Annotated, Any, get_args, get_origin, get_type_hints

from pydantic import BaseModel

from rawagents.utils.types import ToolCall, ToolResult


__all__ = ["ToolExecutor"]


class ToolExecutor:
    """Execute tools safely with dependency injection.

    Features:
    - Async-first execution (sync tools run in thread pool)
    - Dependency injection via context dict (by parameter name)
    - Error boundary (exceptions → ToolResult with is_error=True)
    - Optional before/after callbacks for logging/metrics

    Example:
        from typing import Annotated
        from ai_components.tools import tool, ToolExecutor, Inject

        @tool
        def search(query: str, db: Annotated[Database, Inject]) -> str:
            '''Search the database.'''
            return db.query(query)

        executor = ToolExecutor([search])
        schemas = executor.get_schemas()  # For LLM

        result = await executor.execute(
            tool_call,
            context={'db': my_db_connection}
        )

    Attributes:
        _tools: Registry of tool name -> decorated function.
        _on_before: Optional callback invoked before execution.
        _on_after: Optional callback invoked after execution.
    """

    def __init__(
        self,
        tools: list[Callable[..., Any]] | None = None,
        on_before: Callable[[ToolCall], None] | None = None,
        on_after: Callable[[ToolCall, ToolResult], None] | None = None,
    ) -> None:
        """Initialize the executor with tools and optional callbacks.

        Args:
            tools: List of @tool decorated functions to register.
            on_before: Callback invoked before each tool execution.
            on_after: Callback invoked after each tool execution.
        """
        self._tools: dict[str, Callable[..., Any]] = {}
        self._on_before = on_before
        self._on_after = on_after

        for t in tools or []:
            self.register(t)

    def register(self, func: Callable[..., Any]) -> None:
        """Register a @tool decorated function.

        Args:
            func: A function decorated with @tool.

        Raises:
            ValueError: If the function is not decorated with @tool.
            ValueError: If a tool with the same name is already registered.
        """
        # Check for tool metadata
        if not hasattr(func, "__tool_name__"):
            raise ValueError(
                f"Function '{func.__name__}' is not decorated with @tool. "
                f"Use @tool to define tools before registering."
            )

        name: str = func.__tool_name__

        if name in self._tools:
            raise ValueError(
                f"Tool '{name}' is already registered. "
                f"Use a different name or unregister the existing tool first."
            )

        self._tools[name] = func

    def unregister(self, name: str) -> None:
        """Unregister a tool by name.

        Args:
            name: The tool name to unregister.

        Raises:
            KeyError: If the tool is not registered.
        """
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' is not registered.")
        del self._tools[name]

    def get_schemas(self) -> list[dict[str, Any]]:
        """Get OpenAI-compatible schemas for all registered tools.

        Returns:
            List of tool schema dictionaries.
        """
        return [func.__tool_schema__ for func in self._tools.values()]  # type: ignore[attr-defined]

    def get_tool_names(self) -> list[str]:
        """Get names of all registered tools.

        Returns:
            List of tool names.
        """
        return list(self._tools.keys())

    async def execute(
        self,
        tool_call: ToolCall,
        context: dict[str, Any] | None = None,
    ) -> ToolResult:
        """Execute a tool call and return the result.

        This method NEVER raises exceptions - all errors are returned as
        ToolResult with is_error=True.

        Args:
            tool_call: The tool call from the LLM.
            context: Injection context mapping parameter names to values.

        Returns:
            ToolResult with success or error information.
        """
        context = context or {}

        # Invoke before callback
        if self._on_before is not None:
            try:
                self._on_before(tool_call)
            except Exception:
                pass  # Don't let callback errors affect execution

        # Find the tool
        func = self._tools.get(tool_call.name)
        if func is None:
            result = ToolResult(
                tool_call_id=tool_call.id,
                name=tool_call.name,
                content=f"Unknown tool '{tool_call.name}'. "
                f"Available tools: {', '.join(sorted(self._tools.keys()))}",
                is_error=True,
            )
            self._invoke_after(tool_call, result)
            return result

        # Get injected parameter names
        injected_params: frozenset[str] = func.__tool_injected_params__  # type: ignore[attr-defined]

        # Validate injection context
        missing = [p for p in injected_params if p not in context]
        if missing:
            result = ToolResult(
                tool_call_id=tool_call.id,
                name=tool_call.name,
                content=f"Missing required context for tool '{tool_call.name}': "
                f"{', '.join(missing)}. Provide these in the context dict.",
                is_error=True,
            )
            self._invoke_after(tool_call, result)
            return result

        # Validate and coerce LLM arguments
        try:
            validated_args = self._validate_and_coerce_arguments(
                tool_call.arguments, func
            )
        except TypeError as e:
            result = ToolResult(
                tool_call_id=tool_call.id,
                name=tool_call.name,
                content=f"Invalid arguments for tool '{tool_call.name}': {e}",
                is_error=True,
            )
            self._invoke_after(tool_call, result)
            return result

        # Merge validated args with injected values
        kwargs = dict(validated_args)
        for param_name in injected_params:
            kwargs[param_name] = context[param_name]

        # Execute the tool
        try:
            is_async: bool = func.__tool_is_async__  # type: ignore[attr-defined]
            original_func: Callable[..., Any] = func.__tool_original_func__  # type: ignore[attr-defined]

            if is_async:
                output = await original_func(**kwargs)
            else:
                # Run sync functions in thread pool to avoid blocking
                loop = asyncio.get_running_loop()
                output = await loop.run_in_executor(
                    None,
                    lambda: original_func(**kwargs),
                )

            # Serialize result
            content = self._serialize_output(output)

            result = ToolResult(
                tool_call_id=tool_call.id,
                name=tool_call.name,
                content=content,
                is_error=False,
            )

        except Exception as e:
            result = ToolResult(
                tool_call_id=tool_call.id,
                name=tool_call.name,
                content=f"Tool '{tool_call.name}' raised {type(e).__name__}: {e}",
                is_error=True,
            )

        self._invoke_after(tool_call, result)
        return result

    async def execute_batch(
        self,
        tool_calls: list[ToolCall],
        context: dict[str, Any] | None = None,
    ) -> list[ToolResult]:
        """Execute multiple tool calls in parallel.

        Independent calls run concurrently via ``asyncio.gather()``.
        Results are returned in the same order as input ``tool_calls``.

        Each call is isolated: one failure does not cancel or affect others
        (``execute()`` never raises — it returns ``ToolResult`` with
        ``is_error=True`` on failure).

        Args:
            tool_calls: List of tool calls to execute.
            context: Shared injection context for all calls.

        Returns:
            List of ToolResults in same order as input.
        """
        if not tool_calls:
            return []

        results = await asyncio.gather(
            *(self.execute(tc, context) for tc in tool_calls),
        )
        return list(results)

    def execute_sync(
        self,
        tool_call: ToolCall,
        context: dict[str, Any] | None = None,
    ) -> ToolResult:
        """Synchronous execution wrapper.

        Creates event loop if needed. Useful for testing and simple scripts.

        Args:
            tool_call: The tool call from the LLM.
            context: Injection context mapping parameter names to values.

        Returns:
            ToolResult with success or error information.
        """
        return asyncio.run(self.execute(tool_call, context))

    def _invoke_after(self, tool_call: ToolCall, result: ToolResult) -> None:
        """Safely invoke the after callback."""
        if self._on_after is not None:
            try:
                self._on_after(tool_call, result)
            except Exception:
                pass  # Don't let callback errors affect execution

    def _coerce_value(
        self, value: Any, expected_type: Any, param_name: str
    ) -> Any:
        """Coerce a value to the expected type.

        Handles:
        - Basic types (str, int, float, bool) - no coercion needed from JSON
        - Pydantic models (dict → BaseModel)
        - Lists and dicts - pass through

        Args:
            value: The value to coerce.
            expected_type: The expected type annotation.
            param_name: Parameter name for error messages.

        Returns:
            The coerced value.

        Raises:
            TypeError: If coercion fails.
        """
        origin = get_origin(expected_type)

        # Handle Annotated types - extract the base type
        if origin is Annotated:
            expected_type = get_args(expected_type)[0]
            origin = get_origin(expected_type)

        # Pydantic model: convert dict to model instance
        if isinstance(expected_type, type) and issubclass(expected_type, BaseModel):
            if isinstance(value, dict):
                return expected_type.model_validate(value)
            elif isinstance(value, expected_type):
                return value
            else:
                raise TypeError(
                    f"Parameter '{param_name}' expected {expected_type.__name__}, "
                    f"got {type(value).__name__}"
                )

        # For other types, pass through (JSON already constrains types)
        return value

    def _validate_and_coerce_arguments(
        self,
        arguments: dict[str, Any],
        func: Callable[..., Any],
    ) -> dict[str, Any]:
        """Validate and coerce LLM arguments against function signature.

        Args:
            arguments: The arguments from ToolCall (LLM-provided).
            func: The decorated tool function.

        Returns:
            Validated and coerced arguments.

        Raises:
            TypeError: If validation/coercion fails.
        """
        # Get type hints from the original function
        try:
            hints = get_type_hints(
                func.__tool_original_func__,  # type: ignore[attr-defined]
                include_extras=True,
            )
        except Exception:
            # If we can't get type hints, pass through unchanged
            return dict(arguments)

        injected_params: frozenset[str] = func.__tool_injected_params__  # type: ignore[attr-defined]

        validated = {}
        for param_name, value in arguments.items():
            # Skip injected params - they come from context, not LLM
            if param_name in injected_params:
                continue

            # If no type hint, pass through unchanged
            if param_name not in hints:
                validated[param_name] = value
                continue

            expected_type = hints[param_name]
            validated[param_name] = self._coerce_value(value, expected_type, param_name)

        return validated

    def _serialize_output(self, output: Any) -> str:
        """Serialize tool output to string.

        Args:
            output: The raw output from the tool function.

        Returns:
            JSON string representation of the output.
        """
        if isinstance(output, str):
            return output
        if isinstance(output, BaseModel):
            return output.model_dump_json()
        if output is None:
            return "null"
        try:
            return json.dumps(output, default=str)
        except (TypeError, ValueError):
            return str(output)

    def __len__(self) -> int:
        """Return the number of registered tools."""
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        """Check if a tool is registered by name."""
        return name in self._tools
