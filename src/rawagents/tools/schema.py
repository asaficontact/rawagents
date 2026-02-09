"""JSON schema generation for tool functions."""

from __future__ import annotations

import inspect
import re
import types
from typing import (
    Annotated,
    Any,
    Callable,
    Literal,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from pydantic import BaseModel


__all__ = [
    "generate_tool_schema",
    "type_to_json_schema",
]


def type_to_json_schema(type_hint: Any) -> dict[str, Any]:
    """Convert a Python type hint to JSON Schema.

    Args:
        type_hint: A Python type annotation.

    Returns:
        JSON Schema representation of the type.

    Example:
        >>> type_to_json_schema(str)
        {'type': 'string'}
        >>> type_to_json_schema(int)
        {'type': 'integer'}
        >>> type_to_json_schema(list[str])
        {'type': 'array', 'items': {'type': 'string'}}
    """
    # Handle None type
    if type_hint is type(None):
        return {"type": "null"}

    # Handle basic types
    if type_hint is str:
        return {"type": "string"}
    if type_hint is int:
        return {"type": "integer"}
    if type_hint is float:
        return {"type": "number"}
    if type_hint is bool:
        return {"type": "boolean"}
    if type_hint is dict:
        # Generic dict -> object with any properties
        return {"type": "object", "additionalProperties": True}
    if type_hint is list:
        # Generic list -> array of anything
        return {"type": "array", "items": {}}

    origin = get_origin(type_hint)
    args = get_args(type_hint)

    # Handle Annotated - extract base type
    if origin is Annotated:
        return type_to_json_schema(args[0])

    # Handle Literal (enum)
    if origin is Literal:
        return {"type": "string", "enum": list(args)}

    # Handle list[T]
    if origin is list:
        if args:
            return {"type": "array", "items": type_to_json_schema(args[0])}
        return {"type": "array", "items": {}}

    # Handle dict[str, T]
    if origin is dict:
        schema: dict[str, Any] = {"type": "object"}
        if len(args) >= 2:
            schema["additionalProperties"] = type_to_json_schema(args[1])
        else:
            schema["additionalProperties"] = True
        return schema

    # Handle Union (including Optional which is Union[T, None]) and PEP 604 X | Y
    if origin is Union or origin is types.UnionType:
        # Filter out None for optional handling
        non_none_args = [a for a in args if a is not type(None)]
        if len(non_none_args) == 1:
            # This is Optional[T]
            return type_to_json_schema(non_none_args[0])
        # Multiple types - use anyOf
        return {"anyOf": [type_to_json_schema(a) for a in non_none_args]}

    # Handle Pydantic models
    if isinstance(type_hint, type) and issubclass(type_hint, BaseModel):
        json_schema = type_hint.model_json_schema()
        result: dict[str, Any] = {
            "type": "object",
            "properties": json_schema.get("properties", {}),
        }
        if "required" in json_schema:
            result["required"] = json_schema["required"]
        if "$defs" in json_schema:
            result["$defs"] = json_schema["$defs"]
        return result

    # Fallback to string for unknown types
    return {"type": "string"}


def _parse_docstring(docstring: str) -> tuple[str, dict[str, str]]:
    """Parse docstring to extract description and parameter descriptions.

    Supports:
    - Google Style (Args: ...)
    - Sphinx/ReST Style (:param name: ...)

    Args:
        docstring: The function docstring.

    Returns:
        Tuple of (main_description, dict of param_name -> param_description).
    """
    if not docstring:
        return "", {}

    lines = docstring.strip().split("\n")
    description_lines = []
    param_docs: dict[str, str] = {}
    current_param = None

    # Regex for Sphinx style: :param name: description
    sphinx_param_re = re.compile(r":param\s+(\w+):\s*(.*)")
    # Regex for Google style: name (type): description OR name: description
    google_param_re = re.compile(r"^\s*(\w+)(?:\s*\(.*?\))?:\s*(.*)")

    # State tracking for Google style
    in_args_section = False

    for line in lines:
        line = line.strip()

        # Skip empty lines if we haven't started args
        if not line and not in_args_section:
            if description_lines:
                description_lines.append("")  # Keep paragraph breaks
            continue

        # Check for Google Style "Args:" section header
        if line.lower() == "args:" or line.lower() == "arguments:":
            in_args_section = True
            continue

        # Sphinx Style
        sphinx_match = sphinx_param_re.match(line)
        if sphinx_match:
            name, desc = sphinx_match.groups()
            param_docs[name] = desc
            current_param = name
            continue

        # Google Style inside Args section
        if in_args_section:
            google_match = google_param_re.match(line)
            if google_match:
                name, desc = google_match.groups()
                param_docs[name] = desc
                current_param = name
                continue
            # Multiline description for previous param
            if current_param and line:
                param_docs[current_param] += " " + line
                continue

        # If not in args section and not a param tag, it's part of the description
        if not in_args_section and not line.startswith(":"):
            description_lines.append(line)

    # Join description lines
    description = "\n".join(description_lines).strip()
    return description, param_docs


def generate_tool_schema(
    name: str,
    description: str,
    func: Callable[..., Any],
    injected_params: set[str],
) -> dict[str, Any]:
    """Generate OpenAI-compatible tool schema from a function.

    Introspects the function signature to build a JSON Schema for
    the function parameters. Parameters marked as injected are excluded.

    Args:
        name: Tool name.
        description: Tool description (typically from docstring).
        func: The tool function to introspect.
        injected_params: Set of parameter names to exclude from schema.

    Returns:
        OpenAI-compatible tool schema dict.

    Example:
        >>> def get_weather(location: str, unit: str = "celsius") -> str:
        ...     '''Get weather for a location.'''
        ...     return f"Sunny in {location}"
        >>>
        >>> schema = generate_tool_schema(
        ...     "get_weather",
        ...     "Get weather for a location.",
        ...     get_weather,
        ...     set(),
        ... )
        >>> schema["type"]
        'function'
        >>> schema["function"]["name"]
        'get_weather'
    """
    # Parse docstring for parameter descriptions
    doc_description, param_docs = _parse_docstring(func.__doc__ or "")
    
    # Use provided description if available, otherwise parsed one
    final_description = description or doc_description

    # Get type hints for the function
    try:
        hints = get_type_hints(func, include_extras=True)
    except Exception:
        hints = {}

    sig = inspect.signature(func)

    properties: dict[str, Any] = {}
    required: list[str] = []

    for param_name, param in sig.parameters.items():
        # Skip self, cls, and injected parameters
        if param_name in ("self", "cls"):
            continue
        if param_name in injected_params:
            continue

        # Get type hint
        hint = hints.get(param_name, str)

        # Extract base type from Annotated if present
        if get_origin(hint) is Annotated:
            hint = get_args(hint)[0]

        # Build property schema
        prop_schema = type_to_json_schema(hint)

        # Add description from docstring if available
        if param_name in param_docs:
            prop_schema["description"] = param_docs[param_name]

        properties[param_name] = prop_schema

        # Required if no default value
        if param.default is inspect.Parameter.empty:
            required.append(param_name)

    parameters: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }

    if required:
        parameters["required"] = required

    return {
        "type": "function",
        "function": {
            "name": name,
            "description": final_description,
            "parameters": parameters,
        },
    }
