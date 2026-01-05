"""Tests for the @tool decorator."""

from typing import Annotated, Literal

import pytest
from pydantic import BaseModel

from rawagents.tools import Inject, ToolDefinitionError, tool


class TestToolDecoratorBasic:
    """Tests for basic decorator functionality."""

    def test_decorator_preserves_function_behavior(self, simple_tool) -> None:
        """Decorated function can still be called normally."""
        result = simple_tool(2, 3)
        assert result == 5

    def test_decorator_with_parentheses(self) -> None:
        """Decorator works with parentheses @tool()."""

        @tool()
        def my_func(x: int) -> int:
            """Return x."""
            return x

        assert my_func(42) == 42
        assert hasattr(my_func, "__tool_name__")

    def test_decorator_without_parentheses(self) -> None:
        """Decorator works without parentheses @tool."""

        @tool
        def my_func(x: int) -> int:
            """Return x."""
            return x

        assert my_func(42) == 42
        assert hasattr(my_func, "__tool_name__")

    def test_decorator_custom_name(self) -> None:
        """Decorator accepts custom name."""

        @tool(name="custom_name")
        def my_func(x: int) -> int:
            """Return x."""
            return x

        assert my_func.__tool_name__ == "custom_name"

    def test_decorator_custom_description(self) -> None:
        """Decorator accepts custom description."""

        @tool(description="Custom description")
        def my_func(x: int) -> int:
            """Original docstring."""
            return x

        assert my_func.__tool_description__ == "Custom description"

    def test_decorator_uses_docstring_as_description(self) -> None:
        """Decorator uses docstring as description by default."""

        @tool
        def my_func(x: int) -> int:
            """This is the docstring."""
            return x

        assert my_func.__tool_description__ == "This is the docstring."


class TestToolDecoratorMetadata:
    """Tests for metadata attached by decorator."""

    def test_tool_name_attribute(self, simple_tool) -> None:
        """Decorator attaches __tool_name__."""
        assert simple_tool.__tool_name__ == "add"

    def test_tool_description_attribute(self, simple_tool) -> None:
        """Decorator attaches __tool_description__."""
        assert simple_tool.__tool_description__ == "Add two numbers."

    def test_tool_schema_attribute(self, simple_tool) -> None:
        """Decorator attaches __tool_schema__."""
        schema = simple_tool.__tool_schema__
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "add"

    def test_tool_is_async_false_for_sync(self, simple_tool) -> None:
        """Sync functions marked as not async."""
        assert simple_tool.__tool_is_async__ is False

    def test_tool_is_async_true_for_async(self, async_tool) -> None:
        """Async functions marked as async."""
        assert async_tool.__tool_is_async__ is True

    def test_injected_params_identified(self, tool_with_injection) -> None:
        """Injected parameters correctly identified."""
        assert "db" in tool_with_injection.__tool_injected_params__
        assert "sql" not in tool_with_injection.__tool_injected_params__


class TestToolDecoratorValidation:
    """Tests for signature validation at decoration time."""

    def test_missing_return_type_raises_error(self) -> None:
        """Missing return type raises ToolDefinitionError."""
        with pytest.raises(ToolDefinitionError, match="return type annotation"):

            @tool
            def bad_func(x: int):  # type: ignore[no-untyped-def]
                return x

    def test_missing_param_type_raises_error(self) -> None:
        """Missing parameter type raises ToolDefinitionError."""
        with pytest.raises(ToolDefinitionError, match="type annotation"):

            @tool
            def bad_func(x) -> int:  # type: ignore[no-untyped-def]
                return x

    def test_non_json_type_without_inject_raises_error(self) -> None:
        """Non-JSON type without Inject raises ToolDefinitionError."""

        class CustomClass:
            pass

        with pytest.raises(ToolDefinitionError, match="not JSON-serializable"):

            @tool
            def bad_func(obj: CustomClass) -> str:
                return str(obj)

    def test_json_types_are_allowed(self) -> None:
        """JSON-compatible types are allowed."""

        @tool
        def good_func(
            s: str,
            i: int,
            f: float,
            b: bool,
            lst: list[str],
            dct: dict[str, int],
        ) -> str:
            """Valid types."""
            return "ok"

        assert good_func.__tool_name__ == "good_func"

    def test_literal_type_allowed(self) -> None:
        """Literal types are allowed."""

        @tool
        def func_with_literal(mode: Literal["fast", "slow"]) -> str:
            """Has literal type."""
            return mode

        assert func_with_literal.__tool_name__ == "func_with_literal"

    def test_pydantic_model_allowed(self) -> None:
        """Pydantic models are allowed as parameters."""

        class InputModel(BaseModel):
            name: str
            count: int

        @tool
        def func_with_model(data: InputModel) -> str:
            """Has Pydantic model input."""
            return data.name

        assert func_with_model.__tool_name__ == "func_with_model"

    def test_injected_non_json_type_allowed(self) -> None:
        """Non-JSON types with Inject marker are allowed."""

        class Database:
            pass

        @tool
        def func_with_inject(
            query: str,
            db: Annotated[Database, Inject],
        ) -> str:
            """Has injected parameter."""
            return query

        assert "db" in func_with_inject.__tool_injected_params__


class TestToolDecoratorAsync:
    """Tests for async function handling."""

    def test_async_function_detected(self) -> None:
        """Async functions are correctly detected."""

        @tool
        async def async_func(x: int) -> int:
            """Async function."""
            return x

        assert async_func.__tool_is_async__ is True

    def test_sync_function_detected(self) -> None:
        """Sync functions are correctly detected."""

        @tool
        def sync_func(x: int) -> int:
            """Sync function."""
            return x

        assert sync_func.__tool_is_async__ is False

    @pytest.mark.asyncio
    async def test_async_function_can_be_awaited(self) -> None:
        """Decorated async functions can still be awaited."""

        @tool
        async def async_func(x: int) -> int:
            """Async function."""
            return x * 2

        result = await async_func.__tool_original_func__(5)
        assert result == 10
