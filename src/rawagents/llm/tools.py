"""Tool schema conversion utilities."""

from typing import Any

from pydantic import BaseModel


def pydantic_to_tool_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Convert a Pydantic model to OpenAI tool/function schema format.

    Args:
        model: A Pydantic BaseModel class representing the tool.

    Returns:
        A dictionary in OpenAI's tool format with type="function".

    Example:
        >>> from pydantic import BaseModel, Field
        >>>
        >>> class GetWeather(BaseModel):
        ...     '''Get the current weather for a location.'''
        ...     location: str = Field(description="City and state")
        ...     unit: str = Field(default="fahrenheit")
        >>>
        >>> schema = pydantic_to_tool_schema(GetWeather)
        >>> schema["type"]
        'function'
        >>> schema["function"]["name"]
        'GetWeather'
    """
    json_schema = model.model_json_schema()

    # Extract description from docstring or schema
    description = model.__doc__ or json_schema.get("description", "")

    # Build the function parameters schema
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": json_schema.get("properties", {}),
    }

    # Add required fields if present
    if "required" in json_schema:
        parameters["required"] = json_schema["required"]

    # Handle $defs for nested models
    if "$defs" in json_schema:
        parameters["$defs"] = json_schema["$defs"]

    return {
        "type": "function",
        "function": {
            "name": model.__name__,
            "description": description.strip(),
            "parameters": parameters,
        },
    }


def tools_to_schemas(tools: list[type[BaseModel]]) -> list[dict[str, Any]]:
    """Convert a list of Pydantic models to OpenAI tool schemas.

    Args:
        tools: List of Pydantic BaseModel classes.

    Returns:
        List of tool schema dictionaries.
    """
    return [pydantic_to_tool_schema(tool) for tool in tools]
