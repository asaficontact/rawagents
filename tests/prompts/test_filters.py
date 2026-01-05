"""Tests for custom Jinja2 filters."""

import json

import pytest

from rawagents.prompts.filters import get_default_filters, to_json


class TestToJsonFilter:
    """Tests for the to_json filter."""

    def test_dict_to_json(self) -> None:
        """Dictionary serializes to JSON."""
        result = to_json({"key": "value"})
        assert json.loads(result) == {"key": "value"}

    def test_list_to_json(self) -> None:
        """List serializes to JSON."""
        result = to_json([1, 2, 3])
        assert json.loads(result) == [1, 2, 3]

    def test_nested_dict_to_json(self) -> None:
        """Nested dictionary serializes correctly."""
        data = {"outer": {"inner": "value"}}
        result = to_json(data)
        assert json.loads(result) == data

    def test_primitives_to_json(self) -> None:
        """Primitive values serialize correctly."""
        assert to_json("hello") == '"hello"'
        assert to_json(42) == "42"
        assert to_json(3.14) == "3.14"
        assert to_json(True) == "true"
        assert to_json(None) == "null"

    def test_pydantic_model_to_json(self, sample_user: "SampleUser") -> None:
        """Pydantic model serializes to JSON."""
        result = to_json(sample_user)
        parsed = json.loads(result)
        assert parsed["id"] == 1
        assert parsed["name"] == "Alice"

    def test_nested_pydantic_model(self, sample_config: "SampleConfig") -> None:
        """Nested Pydantic model serializes correctly."""
        result = to_json(sample_config)
        parsed = json.loads(result)
        assert parsed["user"]["name"] == "Alice"
        assert parsed["settings"]["theme"] == "dark"

    def test_with_indent_parameter(self) -> None:
        """Indent parameter produces formatted JSON."""
        result = to_json({"key": "value"}, indent=2)
        assert "\n" in result
        assert "  " in result

    def test_pydantic_with_indent(self, sample_user: "SampleUser") -> None:
        """Pydantic model with indent produces formatted JSON."""
        result = to_json(sample_user, indent=2)
        assert "\n" in result

    def test_non_serializable_uses_str_fallback(self) -> None:
        """Non-serializable objects use str() fallback."""

        class CustomObj:
            def __str__(self) -> str:
                return "CustomObj"

        result = to_json({"obj": CustomObj()})
        assert "CustomObj" in result

    def test_datetime_uses_str_fallback(self) -> None:
        """Datetime objects use str() fallback."""
        from datetime import datetime

        dt = datetime(2024, 1, 15, 12, 30, 0)
        result = to_json({"date": dt})
        assert "2024" in result


class TestDefaultFilters:
    """Tests for get_default_filters."""

    def test_returns_dict_with_to_json(self) -> None:
        """get_default_filters returns dict with to_json."""
        filters = get_default_filters()
        assert isinstance(filters, dict)
        assert "to_json" in filters
        assert filters["to_json"] is to_json

    def test_to_json_filter_works(self) -> None:
        """to_json filter from defaults works correctly."""
        filters = get_default_filters()
        result = filters["to_json"]({"key": "value"})
        assert json.loads(result) == {"key": "value"}


# Import fixtures for type hints
from tests.prompts.conftest import SampleConfig, SampleUser
