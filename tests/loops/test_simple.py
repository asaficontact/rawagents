"""Tests for simple() loop."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from rawagents.utils.types import ToolCall, ToolResult
from rawagents.llm.types import ToolResponse
from rawagents.loops import LoopConfig, LoopStep, MaxStepsExceededError, simple


class TestSimpleLoop:
    """Tests for the simple() loop function."""

    @pytest.mark.asyncio
    async def test_single_turn_no_tools(
        self,
        mock_conversation: MagicMock,
        mock_llm_no_tools: AsyncMock,
        mock_tools: AsyncMock,
        tool_models: list[type],
    ) -> None:
        """LLM responds immediately without tools."""
        steps: list[LoopStep] = []
        async for step in simple(
            mock_conversation, mock_llm_no_tools, mock_tools, tool_models
        ):
            steps.append(step)

        # Should yield thought then finish
        assert len(steps) == 2
        assert steps[0].type == "thought"
        assert steps[0].content == "Hello! How can I help?"
        assert steps[1].type == "finish"
        assert steps[1].content == "Hello! How can I help?"

    @pytest.mark.asyncio
    async def test_single_tool_call_cycle(
        self,
        mock_conversation: MagicMock,
        mock_llm_with_tools: AsyncMock,
        mock_tools: AsyncMock,
        tool_models: list[type],
    ) -> None:
        """LLM requests one tool, then gives final answer."""
        steps: list[LoopStep] = []
        async for step in simple(
            mock_conversation, mock_llm_with_tools, mock_tools, tool_models
        ):
            steps.append(step)

        # Should be: thought, tool_call, tool_result, thought, finish
        assert len(steps) == 5
        assert steps[0].type == "thought"
        assert steps[1].type == "tool_call"
        assert steps[2].type == "tool_result"
        assert steps[3].type == "thought"
        assert steps[4].type == "finish"

    @pytest.mark.asyncio
    async def test_multiple_tool_calls_in_one_response(
        self,
        mock_conversation: MagicMock,
        mock_llm_multiple_tools: AsyncMock,
        mock_tools_multi: AsyncMock,
        tool_models: list[type],
    ) -> None:
        """LLM requests multiple tools in one response."""
        steps: list[LoopStep] = []
        async for step in simple(
            mock_conversation, mock_llm_multiple_tools, mock_tools_multi, tool_models
        ):
            steps.append(step)

        # Find the tool_call step
        tool_call_step = next(s for s in steps if s.type == "tool_call")
        assert tool_call_step.tool_calls is not None
        assert len(tool_call_step.tool_calls) == 2

        # Find the tool_result step
        tool_result_step = next(s for s in steps if s.type == "tool_result")
        assert tool_result_step.tool_results is not None
        assert len(tool_result_step.tool_results) == 2

    @pytest.mark.asyncio
    async def test_yields_correct_metadata(
        self,
        mock_conversation: MagicMock,
        mock_llm_no_tools: AsyncMock,
        mock_tools: AsyncMock,
        tool_models: list[type],
    ) -> None:
        """Steps include correct metadata."""
        steps: list[LoopStep] = []
        async for step in simple(
            mock_conversation, mock_llm_no_tools, mock_tools, tool_models
        ):
            steps.append(step)

        thought_step = steps[0]
        assert thought_step.metadata["step_number"] == 1
        assert thought_step.metadata["model"] == "test-model"
        assert thought_step.metadata["usage"]["total_tokens"] == 15
        assert thought_step.metadata["cost"] == 0.001
        assert thought_step.metadata["latency_ms"] == 100

    @pytest.mark.asyncio
    async def test_conversation_updated_on_finish(
        self,
        mock_conversation: MagicMock,
        mock_llm_no_tools: AsyncMock,
        mock_tools: AsyncMock,
        tool_models: list[type],
    ) -> None:
        """Conversation is updated with assistant message."""
        async for _ in simple(
            mock_conversation, mock_llm_no_tools, mock_tools, tool_models
        ):
            pass

        # Check that add_assistant was called
        mock_conversation.add_assistant.assert_called_once()
        call_args = mock_conversation.add_assistant.call_args
        assert call_args[1]["content"] == "Hello! How can I help?"

    @pytest.mark.asyncio
    async def test_conversation_updated_with_tool_calls(
        self,
        mock_conversation: MagicMock,
        mock_llm_with_tools: AsyncMock,
        mock_tools: AsyncMock,
        tool_models: list[type],
    ) -> None:
        """Conversation is updated with tool calls and results."""
        async for _ in simple(
            mock_conversation, mock_llm_with_tools, mock_tools, tool_models
        ):
            pass

        # Check add_assistant was called with tool_calls
        assert mock_conversation.add_assistant.call_count >= 1

        # Check add_tool_result was called
        mock_conversation.add_tool_result.assert_called()

    @pytest.mark.asyncio
    async def test_custom_config_applied(
        self,
        mock_conversation: MagicMock,
        mock_llm_no_tools: AsyncMock,
        mock_tools: AsyncMock,
        tool_models: list[type],
    ) -> None:
        """Custom config is passed to LLM."""
        config = LoopConfig(
            max_steps=5,
            tool_choice="required",
            temperature=0.5,
        )

        async for _ in simple(
            mock_conversation, mock_llm_no_tools, mock_tools, tool_models, config=config
        ):
            pass

        # Verify LLM was called with custom params
        call_kwargs = mock_llm_no_tools.complete_with_tools.call_args[1]
        assert call_kwargs["tool_choice"] == "required"
        assert call_kwargs["temperature"] == 0.5

    @pytest.mark.asyncio
    async def test_context_passed_to_tools(
        self,
        mock_conversation: MagicMock,
        mock_llm_with_tools: AsyncMock,
        mock_tools: AsyncMock,
        tool_models: list[type],
    ) -> None:
        """Context dict is passed to tool executor."""
        context = {"db": "mock_database"}

        async for _ in simple(
            mock_conversation,
            mock_llm_with_tools,
            mock_tools,
            tool_models,
            context=context,
        ):
            pass

        # Verify tools.execute was called with context
        mock_tools.execute.assert_called()
        call_kwargs = mock_tools.execute.call_args[1]
        assert call_kwargs["context"] == context


class TestSimpleLoopErrors:
    """Tests for error handling in simple() loop."""

    @pytest.mark.asyncio
    async def test_max_steps_exceeded_raises(
        self,
        mock_conversation: MagicMock,
        mock_llm_infinite_tools: AsyncMock,
        mock_tools: AsyncMock,
        tool_models: list[type],
    ) -> None:
        """MaxStepsExceededError raised when limit reached."""
        config = LoopConfig(max_steps=3)

        with pytest.raises(MaxStepsExceededError) as exc_info:
            async for _ in simple(
                mock_conversation,
                mock_llm_infinite_tools,
                mock_tools,
                tool_models,
                config=config,
            ):
                pass

        assert exc_info.value.max_steps == 3
        assert exc_info.value.steps_taken == 3

    @pytest.mark.asyncio
    async def test_tool_error_yields_error_step_when_stop_on_error(
        self,
        mock_conversation: MagicMock,
        mock_llm_with_tools: AsyncMock,
        mock_tools_with_error: AsyncMock,
        tool_models: list[type],
    ) -> None:
        """Tool error yields error step and stops when stop_on_error=True."""
        config = LoopConfig(stop_on_error=True)

        steps: list[LoopStep] = []
        async for step in simple(
            mock_conversation,
            mock_llm_with_tools,
            mock_tools_with_error,
            tool_models,
            config=config,
        ):
            steps.append(step)

        # Should have error step as one of the last steps
        error_steps = [s for s in steps if s.type == "error"]
        assert len(error_steps) == 1
        assert "failed" in error_steps[0].content.lower()  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_tool_error_continues_when_stop_on_error_false(
        self,
        mock_conversation: MagicMock,
        mock_tools_with_error: AsyncMock,
        tool_models: list[type],
    ) -> None:
        """Tool error does not stop loop when stop_on_error=False (default)."""
        # LLM that calls tool once then finishes
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
                content="Done despite the error.",
                model="test-model",
                usage={"prompt_tokens": 30, "completion_tokens": 15, "total_tokens": 45},
                cost=0.003,
                latency_ms=200,
                raw_response=None,
                tool_calls=[],
            ),
        ]

        config = LoopConfig(stop_on_error=False)

        steps: list[LoopStep] = []
        async for step in simple(
            mock_conversation,
            llm,
            mock_tools_with_error,
            tool_models,
            config=config,
        ):
            steps.append(step)

        # Should continue to finish despite tool error
        assert any(s.type == "finish" for s in steps)
        # Should not have error step (since stop_on_error=False)
        assert not any(s.type == "error" for s in steps)

    @pytest.mark.asyncio
    async def test_llm_error_propagates(
        self,
        mock_conversation: MagicMock,
        mock_tools: AsyncMock,
        tool_models: list[type],
    ) -> None:
        """LLM errors propagate to caller."""
        llm = AsyncMock()
        llm.complete_with_tools.side_effect = RuntimeError("LLM API failed")

        with pytest.raises(RuntimeError, match="LLM API failed"):
            async for _ in simple(mock_conversation, llm, mock_tools, tool_models):
                pass
