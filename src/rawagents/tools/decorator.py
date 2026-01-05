"""The @tool decorator for defining tools from Python functions."""

from __future__ import annotations

import asyncio
import inspect
from functools import wraps
from typing import (
    Annotated,
    Any,
    Callable,
    Literal,
    TypeVar,
    Union,
    cast,
    get_args,
    get_origin,
    get_type_hints,
    overload,
)

from pydantic import BaseModel

from rawagents.tools.exceptions import ToolDefinitionError
from rawagents.tools.schema import generate_tool_schema
from rawagents.tools.types import Inject

__all__ = ["tool"]

F = TypeVar("F", bound=Callable[..., Any])


# Types that can be represented in JSON Schema
_JSON_COMPATIBLE_TYPES: frozenset[type[Any]] = frozenset(
    {
        str,
        int,
        float,
        bool,
        type(None),
    }
)


def _is_json_compatible(type_hint: Any) -> bool:
    """Check if a type can be represented in JSON Schema.

    Args:
        type_hint: A Python type annotation.

    Returns:
        True if the type is JSON-serializable.
    """
    # Basic types
    if type_hint in _JSON_COMPATIBLE_TYPES:
        return True

    origin = get_origin(type_hint)
    args = get_args(type_hint)

    # Handle Annotated - check base type
    if origin is Annotated:
        return _is_json_compatible(args[0])

    # Handle Literal
    if origin is Literal:
        return True

    # Handle list[T]
    if origin is list:
        if args:
            return _is_json_compatible(args[0])
        return True

    # Handle dict[str, T]
    if origin is dict:
        if len(args) >= 2:
            return args[0] is str and _is_json_compatible(args[1])
        return True

    # Handle Union (including Optional)
    if origin is Union:
        return all(_is_json_compatible(a) for a in args)

    # Handle Pydantic models
    if isinstance(type_hint, type) and issubclass(type_hint, BaseModel):
        return True

    return False


def _is_injected(annotation: Any) -> bool:
    """Check if an annotation is marked with Inject.

    Args:
        annotation: A type annotation.

    Returns:
        True if Annotated[T, Inject] pattern is detected.
    """
    if get_origin(annotation) is not Annotated:
        return False

    args = get_args(annotation)
    for meta in args[1:]:
        if isinstance(meta, type) and issubclass(meta, Inject):
            return True
        if isinstance(meta, Inject):
            return True
    return False


def _validate_signature(func: Callable[..., Any], name: str) -> set[str]:
    """Validate the function signature for tool usage.

    Args:
        func: The function to validate.
        name: Tool name for error messages.

    Returns:
        Set of injected parameter names.

    Raises:
        ToolDefinitionError: If the signature is invalid.
    """
    sig = inspect.signature(func)

    try:
        hints = get_type_hints(func, include_extras=True)
    except Exception as e:
        raise ToolDefinitionError(
            f"Tool '{name}' has invalid type annotations: {e}"
        ) from e

    # Check return type
    if "return" not in hints:
        raise ToolDefinitionError(
            f"Tool '{name}' must have a return type annotation. "
            f"Add '-> ReturnType' to the function signature."
        )

    injected_params: set[str] = set()

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue

        # Check parameter has type annotation
        if param_name not in hints:
            raise ToolDefinitionError(
                f"Parameter '{param_name}' in tool '{name}' must have a type annotation."
            )

        annotation = hints[param_name]

        # Check if injected
        if _is_injected(annotation):
            injected_params.add(param_name)
            continue

        # Non-injected parameters must be JSON-compatible
        if not _is_json_compatible(annotation):
            type_name = getattr(annotation, "__name__", str(annotation))
            raise ToolDefinitionError(
                f"Parameter '{param_name}' in tool '{name}' has type '{type_name}' "
                f"which is not JSON-serializable. Use Annotated[{type_name}, Inject] "
                f"for dependency injection, or use a JSON-compatible type "
                f"(str, int, float, bool, list, dict, Literal, or Pydantic model)."
            )

    return injected_params


@overload
def tool(func: F) -> F: ...


@overload
def tool(
    *,
    name: str | None = None,
    description: str | None = None,
) -> Callable[[F], F]: ...


def tool(
    func: F | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
) -> F | Callable[[F], F]:
    """Decorator to define a tool from a Python function.

    Validates the function signature at decoration time (fail fast) and
    attaches metadata for schema generation and execution.

    The decorated function can still be called normally as a Python function.

    Args:
        func: The function to decorate (when used without parentheses).
        name: Override the tool name (defaults to function name).
        description: Override the description (defaults to docstring).

    Returns:
        The decorated function with tool metadata attached.

    Raises:
        ToolDefinitionError: If the function signature is invalid.

    Example:
        @tool
        def get_weather(location: str) -> str:
            '''Get weather for a location.'''
            return f"Sunny in {location}"

        @tool(name="search", description="Search the web")
        async def web_search(query: str, limit: int = 10) -> list[str]:
            '''Search the web for results.'''
            ...

        # With dependency injection
        @tool
        def query_db(
            sql: str,
            db: Annotated[Database, Inject],
        ) -> str:
            '''Execute a SQL query.'''
            return db.execute(sql)
    """

    def decorator(fn: F) -> F:
        tool_name = name or fn.__name__
        tool_description = (description or fn.__doc__ or "").strip()

        # Validate signature and get injected parameters (fail fast)
        injected_params = _validate_signature(fn, tool_name)

        # Check if async
        is_async = asyncio.iscoroutinefunction(fn)

        # Generate schema (excluding injected parameters)
        schema = generate_tool_schema(
            tool_name,
            tool_description,
            fn,
            injected_params,
        )

        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return fn(*args, **kwargs)

        # Attach metadata
        wrapper.__tool_name__ = tool_name  # type: ignore[attr-defined]
        wrapper.__tool_description__ = tool_description  # type: ignore[attr-defined]
        wrapper.__tool_schema__ = schema  # type: ignore[attr-defined]
        wrapper.__tool_is_async__ = is_async  # type: ignore[attr-defined]
        wrapper.__tool_injected_params__ = frozenset(injected_params)  # type: ignore[attr-defined]
        wrapper.__tool_original_func__ = fn  # type: ignore[attr-defined]

        return cast(F, wrapper)

    # Handle @tool vs @tool()
    if func is not None:
        return decorator(func)
    return decorator
