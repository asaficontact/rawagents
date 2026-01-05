"""Custom Jinja2 filters for prompt rendering."""

from __future__ import annotations

import json
from typing import Any, Callable

from pydantic import BaseModel

__all__ = ["to_json", "get_default_filters"]


def to_json(value: Any, indent: int | None = None) -> str:
    """Serialize value to JSON string.

    Handles:
    - Pydantic BaseModel instances (uses model_dump_json)
    - Dicts, lists, primitives (uses json.dumps)
    - Other objects (uses default=str fallback)

    Args:
        value: Value to serialize.
        indent: JSON indentation level.

    Returns:
        JSON string.

    Example in template:
        {{ tools | to_json(indent=2) }}
        {{ user.preferences | to_json }}
    """
    if isinstance(value, BaseModel):
        return value.model_dump_json(indent=indent)
    return json.dumps(value, indent=indent, default=str)


def get_default_filters() -> dict[str, Callable[..., Any]]:
    """Get dictionary of default filters for Jinja2 environment.

    Returns:
        Dict mapping filter names to filter functions.
    """
    return {
        "to_json": to_json,
    }
