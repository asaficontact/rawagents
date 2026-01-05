"""Tests for dependency injection functionality."""

from typing import Annotated

import pytest

from rawagents.utils.types import ToolCall
from rawagents.tools import Inject, ToolExecutor, tool


class TestInjectionBasic:
    """Tests for basic injection functionality."""

    @pytest.mark.asyncio
    async def test_inject_by_param_name(self) -> None:
        """Injection resolves by parameter name."""

        @tool
        def use_db(query: str, db: Annotated[dict[str, str], Inject]) -> str:
            """Use database."""
            return db.get(query, "not found")

        executor = ToolExecutor([use_db])
        mock_db = {"key": "value"}

        result = await executor.execute(
            ToolCall(id="1", name="use_db", arguments={"query": "key"}),
            context={"db": mock_db},
        )

        assert result.is_error is False
        assert result.content == "value"

    @pytest.mark.asyncio
    async def test_inject_multiple_params(self) -> None:
        """Multiple parameters can be injected."""

        @tool
        def multi_inject(
            x: int,
            db: Annotated[dict[str, str], Inject],
            logger: Annotated[list[str], Inject],
        ) -> str:
            """Use multiple injected deps."""
            logger.append(f"called with {x}")
            return db.get("key", "none")

        executor = ToolExecutor([multi_inject])
        mock_db = {"key": "success"}
        mock_logger: list[str] = []

        result = await executor.execute(
            ToolCall(id="1", name="multi_inject", arguments={"x": 42}),
            context={"db": mock_db, "logger": mock_logger},
        )

        assert result.is_error is False
        assert result.content == "success"
        assert mock_logger == ["called with 42"]

    @pytest.mark.asyncio
    async def test_inject_with_regular_params(self) -> None:
        """Injected params work alongside regular params."""

        @tool
        def mixed_params(
            a: int,
            b: int,
            multiplier: Annotated[int, Inject],
        ) -> int:
            """Mix regular and injected params."""
            return (a + b) * multiplier

        executor = ToolExecutor([mixed_params])

        result = await executor.execute(
            ToolCall(id="1", name="mixed_params", arguments={"a": 2, "b": 3}),
            context={"multiplier": 10},
        )

        assert result.is_error is False
        assert result.content == "50"  # (2 + 3) * 10


class TestInjectionErrors:
    """Tests for injection error handling."""

    @pytest.mark.asyncio
    async def test_missing_injection_clear_error_message(self) -> None:
        """Missing injection provides clear error message."""

        @tool
        def needs_db(query: str, db: Annotated[dict[str, str], Inject]) -> str:
            """Needs database."""
            return "ok"

        executor = ToolExecutor([needs_db])

        result = await executor.execute(
            ToolCall(id="1", name="needs_db", arguments={"query": "test"}),
            context={},  # Missing 'db'
        )

        assert result.is_error is True
        assert "Missing required context" in result.content
        assert "db" in result.content

    @pytest.mark.asyncio
    async def test_missing_multiple_injections_lists_all(self) -> None:
        """Missing multiple injections are all listed."""

        @tool
        def needs_many(
            x: int,
            db: Annotated[dict[str, str], Inject],
            cache: Annotated[dict[str, str], Inject],
        ) -> str:
            """Needs multiple deps."""
            return "ok"

        executor = ToolExecutor([needs_many])

        result = await executor.execute(
            ToolCall(id="1", name="needs_many", arguments={"x": 1}),
            context={},  # Missing both
        )

        assert result.is_error is True
        assert "db" in result.content
        assert "cache" in result.content


class TestInjectionSchemaExclusion:
    """Tests verifying injected params are hidden from schema."""

    def test_single_injected_param_hidden(self) -> None:
        """Single injected param is hidden from schema."""

        @tool
        def with_inject(
            query: str,
            db: Annotated[dict[str, str], Inject],
        ) -> str:
            """Has injection."""
            return "ok"

        schema = with_inject.__tool_schema__
        props = schema["function"]["parameters"]["properties"]

        assert "query" in props
        assert "db" not in props

    def test_multiple_injected_params_hidden(self) -> None:
        """Multiple injected params are all hidden."""

        @tool
        def multi_inject(
            x: int,
            db: Annotated[dict[str, str], Inject],
            cache: Annotated[dict[str, str], Inject],
            logger: Annotated[list[str], Inject],
        ) -> str:
            """Has multiple injections."""
            return "ok"

        schema = multi_inject.__tool_schema__
        props = schema["function"]["parameters"]["properties"]

        assert "x" in props
        assert "db" not in props
        assert "cache" not in props
        assert "logger" not in props

    def test_required_list_excludes_injected(self) -> None:
        """Required list excludes injected params."""

        @tool
        def required_test(
            required_param: str,
            optional_param: str = "default",
            injected: Annotated[dict[str, str], Inject] = None,  # type: ignore[assignment]
        ) -> str:
            """Test required list."""
            return "ok"

        schema = required_test.__tool_schema__
        required = schema["function"]["parameters"].get("required", [])

        assert "required_param" in required
        assert "optional_param" not in required
        assert "injected" not in required


class TestInjectionWithAsyncTools:
    """Tests for injection with async tools."""

    @pytest.mark.asyncio
    async def test_async_tool_with_injection(self) -> None:
        """Async tools can use injection."""

        @tool
        async def async_with_inject(
            query: str,
            db: Annotated[dict[str, str], Inject],
        ) -> str:
            """Async with injection."""
            return db.get(query, "not found")

        executor = ToolExecutor([async_with_inject])
        mock_db = {"test": "async_value"}

        result = await executor.execute(
            ToolCall(id="1", name="async_with_inject", arguments={"query": "test"}),
            context={"db": mock_db},
        )

        assert result.is_error is False
        assert result.content == "async_value"


class TestInjectionMarkerVariants:
    """Tests for different ways to use Inject marker."""

    def test_inject_as_class(self) -> None:
        """Inject used as class (not instance) works."""

        @tool
        def with_class_inject(
            x: int,
            db: Annotated[dict[str, str], Inject],
        ) -> str:
            """Uses Inject class."""
            return "ok"

        assert "db" in with_class_inject.__tool_injected_params__

    def test_inject_as_instance(self) -> None:
        """Inject used as instance works."""

        @tool
        def with_instance_inject(
            x: int,
            db: Annotated[dict[str, str], Inject()],
        ) -> str:
            """Uses Inject instance."""
            return "ok"

        assert "db" in with_instance_inject.__tool_injected_params__
