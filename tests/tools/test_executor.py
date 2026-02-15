"""Tests for ToolExecutor."""

from typing import Any
from unittest.mock import MagicMock

import pytest

from rawagents.tools import ToolExecutor, ToolResult, tool
from rawagents.utils.types import ToolCall


class TestToolExecutorRegistration:
    """Tests for tool registration."""

    def test_register_tool(self, simple_tool) -> None:
        """Tool can be registered."""
        executor = ToolExecutor()
        executor.register(simple_tool)
        assert "add" in executor

    def test_register_via_constructor(self, simple_tool) -> None:
        """Tools can be registered via constructor."""
        executor = ToolExecutor([simple_tool])
        assert "add" in executor

    def test_register_duplicate_raises_error(self, simple_tool) -> None:
        """Registering duplicate tool raises ValueError."""
        executor = ToolExecutor([simple_tool])
        with pytest.raises(ValueError, match="already registered"):
            executor.register(simple_tool)

    def test_register_non_tool_raises_error(self) -> None:
        """Registering non-tool function raises ValueError."""

        def not_a_tool(x: int) -> int:
            return x

        executor = ToolExecutor()
        with pytest.raises(ValueError, match="not decorated with @tool"):
            executor.register(not_a_tool)

    def test_unregister_tool(self, simple_tool) -> None:
        """Tool can be unregistered."""
        executor = ToolExecutor([simple_tool])
        executor.unregister("add")
        assert "add" not in executor

    def test_unregister_unknown_raises_error(self) -> None:
        """Unregistering unknown tool raises KeyError."""
        executor = ToolExecutor()
        with pytest.raises(KeyError, match="not registered"):
            executor.unregister("unknown")


class TestToolExecutorSchemas:
    """Tests for schema retrieval."""

    def test_get_schemas(self, executor) -> None:
        """get_schemas returns list of schemas."""
        schemas = executor.get_schemas()
        assert isinstance(schemas, list)
        assert len(schemas) == 5  # 5 tools in fixture

    def test_get_schemas_format(self, simple_tool) -> None:
        """Schemas have correct format."""
        executor = ToolExecutor([simple_tool])
        schemas = executor.get_schemas()
        assert len(schemas) == 1
        assert schemas[0]["type"] == "function"
        assert schemas[0]["function"]["name"] == "add"

    def test_get_tool_names(self, executor) -> None:
        """get_tool_names returns list of names."""
        names = executor.get_tool_names()
        assert "add" in names
        assert "greet" in names


class TestToolExecutorExecution:
    """Tests for tool execution."""

    @pytest.mark.asyncio
    async def test_execute_simple_sync_tool(self, executor) -> None:
        """Sync tool executes correctly."""
        tool_call = ToolCall(id="1", name="add", arguments={"a": 2, "b": 3})
        result = await executor.execute(tool_call)

        assert isinstance(result, ToolResult)
        assert result.tool_call_id == "1"
        assert result.name == "add"
        assert result.content == "5"
        assert result.is_error is False

    @pytest.mark.asyncio
    async def test_execute_async_tool(self, executor) -> None:
        """Async tool executes correctly."""
        tool_call = ToolCall(id="2", name="fetch", arguments={"url": "http://example.com"})
        result = await executor.execute(tool_call)

        assert result.is_error is False
        assert "Content from http://example.com" in result.content

    @pytest.mark.asyncio
    async def test_execute_unknown_tool_returns_error(self, executor) -> None:
        """Unknown tool returns error result."""
        tool_call = ToolCall(id="3", name="unknown", arguments={})
        result = await executor.execute(tool_call)

        assert result.is_error is True
        assert "Unknown tool" in result.content
        assert "unknown" in result.content

    @pytest.mark.asyncio
    async def test_execute_with_defaults(self, executor) -> None:
        """Tool with defaults works without providing all args."""
        tool_call = ToolCall(id="4", name="greet", arguments={"name": "Alice"})
        result = await executor.execute(tool_call)

        assert result.is_error is False
        assert "Hello, Alice!" in result.content

    @pytest.mark.asyncio
    async def test_execute_overriding_defaults(self, executor) -> None:
        """Default values can be overridden."""
        tool_call = ToolCall(
            id="5", name="greet", arguments={"name": "Bob", "greeting": "Hi"}
        )
        result = await executor.execute(tool_call)

        assert result.is_error is False
        assert "Hi, Bob!" in result.content


class TestToolExecutorInjection:
    """Tests for dependency injection."""

    @pytest.mark.asyncio
    async def test_execute_with_injection(self, executor, mock_db) -> None:
        """Tool with injection executes with context."""
        tool_call = ToolCall(
            id="6", name="query", arguments={"sql": "SELECT * FROM users"}
        )
        result = await executor.execute(tool_call, context={"db": mock_db})

        assert result.is_error is False
        assert "users" in result.content

    @pytest.mark.asyncio
    async def test_execute_missing_injection_returns_error(self, executor) -> None:
        """Missing injection context returns error."""
        tool_call = ToolCall(id="7", name="query", arguments={"sql": "SELECT 1"})
        result = await executor.execute(tool_call)  # No context provided

        assert result.is_error is True
        assert "Missing required context" in result.content
        assert "db" in result.content


class TestToolExecutorErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_tool_exception_returns_error_result(self, executor) -> None:
        """Tool exception is caught and returned as error."""
        tool_call = ToolCall(id="8", name="divide", arguments={"a": 1, "b": 0})
        result = await executor.execute(tool_call)

        assert result.is_error is True
        assert "ZeroDivisionError" in result.content

    @pytest.mark.asyncio
    async def test_error_result_has_correct_metadata(self, executor) -> None:
        """Error result has correct tool_call_id and name."""
        tool_call = ToolCall(id="error-test", name="divide", arguments={"a": 1, "b": 0})
        result = await executor.execute(tool_call)

        assert result.tool_call_id == "error-test"
        assert result.name == "divide"


class TestToolExecutorCallbacks:
    """Tests for before/after callbacks."""

    @pytest.mark.asyncio
    async def test_before_callback_invoked(self, simple_tool) -> None:
        """Before callback is invoked."""
        callback = MagicMock()
        executor = ToolExecutor([simple_tool], on_before=callback)

        tool_call = ToolCall(id="1", name="add", arguments={"a": 1, "b": 2})
        await executor.execute(tool_call)

        callback.assert_called_once()
        assert callback.call_args[0][0] == tool_call

    @pytest.mark.asyncio
    async def test_after_callback_invoked(self, simple_tool) -> None:
        """After callback is invoked."""
        callback = MagicMock()
        executor = ToolExecutor([simple_tool], on_after=callback)

        tool_call = ToolCall(id="1", name="add", arguments={"a": 1, "b": 2})
        await executor.execute(tool_call)

        callback.assert_called_once()
        args = callback.call_args[0]
        assert args[0] == tool_call
        assert isinstance(args[1], ToolResult)

    @pytest.mark.asyncio
    async def test_callback_exception_does_not_affect_execution(
        self, simple_tool
    ) -> None:
        """Callback exceptions don't affect tool execution."""

        def bad_callback(tc: ToolCall) -> None:
            raise RuntimeError("Callback failed")

        executor = ToolExecutor([simple_tool], on_before=bad_callback)

        tool_call = ToolCall(id="1", name="add", arguments={"a": 1, "b": 2})
        result = await executor.execute(tool_call)

        # Execution still succeeds despite callback failure
        assert result.is_error is False
        assert result.content == "3"


class TestToolExecutorBatch:
    """Tests for batch/parallel execution."""

    @pytest.mark.asyncio
    async def test_batch_multiple_tools(self, executor) -> None:
        """Batch should return results for all calls."""
        calls = [
            ToolCall(id="1", name="add", arguments={"a": 1, "b": 2}),
            ToolCall(id="2", name="add", arguments={"a": 3, "b": 4}),
            ToolCall(id="3", name="greet", arguments={"name": "Alice"}),
        ]
        results = await executor.execute_batch(calls)

        assert len(results) == 3
        assert results[0].content == "3"
        assert results[1].content == "7"
        assert "Alice" in results[2].content

    @pytest.mark.asyncio
    async def test_batch_empty_list(self, executor) -> None:
        """Empty batch should return empty list."""
        results = await executor.execute_batch([])
        assert results == []

    @pytest.mark.asyncio
    async def test_batch_preserves_order(self, executor) -> None:
        """Results should be in the same order as input calls."""
        calls = [
            ToolCall(id="a", name="add", arguments={"a": 10, "b": 20}),
            ToolCall(id="b", name="add", arguments={"a": 30, "b": 40}),
        ]
        results = await executor.execute_batch(calls)

        assert results[0].tool_call_id == "a"
        assert results[0].content == "30"
        assert results[1].tool_call_id == "b"
        assert results[1].content == "70"

    @pytest.mark.asyncio
    async def test_batch_error_isolation(self, executor) -> None:
        """One failure should not affect other calls."""
        calls = [
            ToolCall(id="ok", name="add", arguments={"a": 1, "b": 2}),
            ToolCall(id="err", name="divide", arguments={"a": 1, "b": 0}),
            ToolCall(id="ok2", name="add", arguments={"a": 5, "b": 5}),
        ]
        results = await executor.execute_batch(calls)

        assert len(results) == 3
        assert results[0].is_error is False
        assert results[0].content == "3"
        assert results[1].is_error is True
        assert "ZeroDivisionError" in results[1].content
        assert results[2].is_error is False
        assert results[2].content == "10"

    @pytest.mark.asyncio
    async def test_batch_with_context(self, executor, mock_db) -> None:
        """Injection context should be shared across all calls."""
        calls = [
            ToolCall(id="1", name="query", arguments={"sql": "SELECT * FROM users"}),
            ToolCall(id="2", name="query", arguments={"sql": "SELECT 1"}),
        ]
        results = await executor.execute_batch(calls, context={"db": mock_db})

        assert len(results) == 2
        assert results[0].is_error is False
        assert results[1].is_error is False

    @pytest.mark.asyncio
    async def test_batch_callbacks_invoked(self, simple_tool) -> None:
        """Before/after callbacks should be invoked for each call."""
        before_calls: list[ToolCall] = []
        after_calls: list[tuple[ToolCall, Any]] = []

        executor = ToolExecutor(
            [simple_tool],
            on_before=lambda tc: before_calls.append(tc),
            on_after=lambda tc, tr: after_calls.append((tc, tr)),
        )

        calls = [
            ToolCall(id="1", name="add", arguments={"a": 1, "b": 2}),
            ToolCall(id="2", name="add", arguments={"a": 3, "b": 4}),
        ]
        await executor.execute_batch(calls)

        assert len(before_calls) == 2
        assert len(after_calls) == 2


class TestToolExecutorSyncExecution:
    """Tests for synchronous execution."""

    def test_execute_sync(self, simple_tool) -> None:
        """execute_sync works for sync tools."""
        executor = ToolExecutor([simple_tool])
        tool_call = ToolCall(id="1", name="add", arguments={"a": 5, "b": 7})
        result = executor.execute_sync(tool_call)

        assert result.is_error is False
        assert result.content == "12"


class TestToolExecutorSerialization:
    """Tests for output serialization."""

    @pytest.mark.asyncio
    async def test_serialize_string_output(self) -> None:
        """String output is returned as-is."""

        @tool
        def string_tool(x: str) -> str:
            """Return string."""
            return x

        executor = ToolExecutor([string_tool])
        result = await executor.execute(
            ToolCall(id="1", name="string_tool", arguments={"x": "hello"})
        )

        assert result.content == "hello"

    @pytest.mark.asyncio
    async def test_serialize_dict_output(self) -> None:
        """Dict output is JSON serialized."""

        @tool
        def dict_tool(x: str) -> dict[str, str]:
            """Return dict."""
            return {"key": x}

        executor = ToolExecutor([dict_tool])
        result = await executor.execute(
            ToolCall(id="1", name="dict_tool", arguments={"x": "value"})
        )

        assert result.content == '{"key": "value"}'

    @pytest.mark.asyncio
    async def test_serialize_list_output(self) -> None:
        """List output is JSON serialized."""

        @tool
        def list_tool(n: int) -> list[int]:
            """Return list."""
            return list(range(n))

        executor = ToolExecutor([list_tool])
        result = await executor.execute(
            ToolCall(id="1", name="list_tool", arguments={"n": 3})
        )

        assert result.content == "[0, 1, 2]"

    @pytest.mark.asyncio
    async def test_serialize_none_output(self) -> None:
        """None output is serialized as 'null'."""

        @tool
        def none_tool() -> None:
            """Return None."""
            return None

        executor = ToolExecutor([none_tool])
        result = await executor.execute(
            ToolCall(id="1", name="none_tool", arguments={})
        )

        assert result.content == "null"


class TestToolExecutorUtility:
    """Tests for utility methods."""

    def test_len(self, executor) -> None:
        """__len__ returns number of tools."""
        assert len(executor) == 5

    def test_contains(self, executor) -> None:
        """__contains__ checks tool presence."""
        assert "add" in executor
        assert "unknown" not in executor
