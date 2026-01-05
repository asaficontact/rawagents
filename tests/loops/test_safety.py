"""Safety and edge case tests for loops."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from rawagents.utils.types import ToolCall
from rawagents.llm.types import ToolResponse
from rawagents.loops import (
    LoopConfig,
    LoopError,
    MaxStepsExceededError,
    simple,
)


class TestLoopSafety:
    """Safety-focused tests."""

    @pytest.mark.asyncio
    async def test_max_steps_enforced(
        self,
        mock_conversation: MagicMock,
        mock_llm_infinite_tools: AsyncMock,
        mock_tools: AsyncMock,
        tool_models: list[type],
    ) -> None:
        """max_steps is enforced even when LLM keeps requesting tools."""
        config = LoopConfig(max_steps=5)

        step_count = 0
        with pytest.raises(MaxStepsExceededError):
            async for _ in simple(
                mock_conversation,
                mock_llm_infinite_tools,
                mock_tools,
                tool_models,
                config=config,
            ):
                step_count += 1

        # Should have yielded steps for all 5 iterations
        # Each iteration: thought, tool_call, tool_result = 3 steps per iteration
        # So 5 iterations = at least 15 steps (some may be less if content is empty)
        assert step_count > 0

    @pytest.mark.asyncio
    async def test_default_max_steps_is_15(
        self,
        mock_conversation: MagicMock,
        mock_llm_infinite_tools: AsyncMock,
        mock_tools: AsyncMock,
        tool_models: list[type],
    ) -> None:
        """Default max_steps is 15."""
        config = LoopConfig()
        assert config.max_steps == 15

        with pytest.raises(MaxStepsExceededError) as exc_info:
            async for _ in simple(
                mock_conversation,
                mock_llm_infinite_tools,
                mock_tools,
                tool_models,
            ):
                pass

        assert exc_info.value.max_steps == 15

    def test_max_steps_bounds_enforced_at_config(self) -> None:
        """max_steps bounds are enforced at config creation."""
        from pydantic import ValidationError

        # Too low
        with pytest.raises(ValidationError):
            LoopConfig(max_steps=0)

        # Too high
        with pytest.raises(ValidationError):
            LoopConfig(max_steps=101)

        # At bounds should work
        config_1 = LoopConfig(max_steps=1)
        config_100 = LoopConfig(max_steps=100)
        assert config_1.max_steps == 1
        assert config_100.max_steps == 100

    @pytest.mark.asyncio
    async def test_tool_execution_error_captured(
        self,
        mock_conversation: MagicMock,
        mock_tools_with_error: AsyncMock,
        tool_models: list[type],
    ) -> None:
        """Tool execution errors are captured in ToolResult, not raised."""
        # LLM requests tool then finishes
        llm = AsyncMock()
        llm.complete_with_tools.side_effect = [
            ToolResponse(
                content="Let me search.",
                model="test-model",
                usage={"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
                cost=0.002,
                latency_ms=150,
                raw_response=None,
                tool_calls=[
                    ToolCall(id="call_1", name="search", arguments={"query": "test"})
                ],
            ),
            ToolResponse(
                content="Done.",
                model="test-model",
                usage={"prompt_tokens": 30, "completion_tokens": 15, "total_tokens": 45},
                cost=0.003,
                latency_ms=200,
                raw_response=None,
                tool_calls=[],
            ),
        ]

        # With stop_on_error=False, errors are captured but loop continues
        config = LoopConfig(stop_on_error=False)

        steps = []
        async for step in simple(
            mock_conversation,
            llm,
            mock_tools_with_error,
            tool_models,
            config=config,
        ):
            steps.append(step)

        # Loop should complete without raising
        assert any(s.type == "finish" for s in steps)
        # Tool result should be in the steps
        tool_result_step = next(s for s in steps if s.type == "tool_result")
        assert tool_result_step.tool_results is not None
        assert tool_result_step.tool_results[0].is_error is True

    @pytest.mark.asyncio
    async def test_llm_error_propagates(
        self,
        mock_conversation: MagicMock,
        mock_tools: AsyncMock,
        tool_models: list[type],
    ) -> None:
        """LLM API errors propagate to caller."""
        llm = AsyncMock()
        llm.complete_with_tools.side_effect = RuntimeError("API unavailable")

        with pytest.raises(RuntimeError, match="API unavailable"):
            async for _ in simple(mock_conversation, llm, mock_tools, tool_models):
                pass


class TestExceptionHierarchy:
    """Tests for exception hierarchy."""

    def test_max_steps_exceeded_is_loop_error(self) -> None:
        """MaxStepsExceededError inherits from LoopError."""
        error = MaxStepsExceededError(max_steps=15, steps_taken=15)
        assert isinstance(error, LoopError)

    def test_max_steps_exceeded_has_attributes(self) -> None:
        """MaxStepsExceededError has max_steps and steps_taken."""
        error = MaxStepsExceededError(max_steps=10, steps_taken=10)
        assert error.max_steps == 10
        assert error.steps_taken == 10

    def test_max_steps_exceeded_message(self) -> None:
        """MaxStepsExceededError has informative message."""
        error = MaxStepsExceededError(max_steps=10, steps_taken=10)
        message = str(error)
        assert "10" in message
        assert "max" in message.lower()


class TestEmptyToolModels:
    """Tests with empty tool_models list."""

    @pytest.mark.asyncio
    async def test_works_with_empty_tool_models(
        self,
        mock_conversation: MagicMock,
        mock_llm_no_tools: AsyncMock,
        mock_tools: AsyncMock,
    ) -> None:
        """Loop works with empty tool_models list."""
        steps = []
        async for step in simple(
            mock_conversation, mock_llm_no_tools, mock_tools, []
        ):
            steps.append(step)

        assert len(steps) > 0
        assert any(s.type == "finish" for s in steps)
