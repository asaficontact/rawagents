"""Tests for interactive() loop."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from rawagents.utils.types import ToolCall
from rawagents.llm.types import ToolResponse
from rawagents.loops import (
    ApprovalDecision,
    LoopConfig,
    LoopStep,
    MaxStepsExceededError,
    interactive,
)


class TestInteractiveLoop:
    """Tests for the interactive() loop function."""

    @pytest.mark.asyncio
    async def test_single_turn_no_tools_no_approval_needed(
        self,
        mock_conversation: MagicMock,
        mock_llm_no_tools: AsyncMock,
        mock_tools: AsyncMock,
        tool_models: list[type],
    ) -> None:
        """LLM responds without tools - no approval needed."""
        steps: list[LoopStep] = []
        async for step in interactive(
            mock_conversation, mock_llm_no_tools, mock_tools, tool_models
        ):
            steps.append(step)

        # Should yield thought then finish, no approval_request
        assert len(steps) == 2
        assert steps[0].type == "thought"
        assert steps[1].type == "finish"
        assert not any(s.type == "approval_request" for s in steps)

    @pytest.mark.asyncio
    async def test_approval_request_yielded_before_tool_execution(
        self,
        mock_conversation: MagicMock,
        mock_llm_with_tools: AsyncMock,
        mock_tools: AsyncMock,
        tool_models: list[type],
    ) -> None:
        """approval_request is yielded before tools execute."""
        runner = interactive(
            mock_conversation, mock_llm_with_tools, mock_tools, tool_models
        )

        steps: list[LoopStep] = []

        # First step should be thought
        step = await runner.__anext__()
        steps.append(step)
        assert step.type == "thought"

        # Second step should be approval_request
        step = await runner.__anext__()
        steps.append(step)
        assert step.type == "approval_request"
        assert step.tool_calls is not None
        assert len(step.tool_calls) == 1

        # At this point, tools should NOT have been executed yet
        mock_tools.execute.assert_not_called()

        # Now approve and continue
        await runner.asend(ApprovalDecision(approved=True))

        # Continue iteration
        async for step in runner:
            steps.append(step)

        # Now tools should have been executed
        mock_tools.execute.assert_called()

    @pytest.mark.asyncio
    async def test_approved_executes_tools(
        self,
        mock_conversation: MagicMock,
        mock_llm_with_tools: AsyncMock,
        mock_tools: AsyncMock,
        tool_models: list[type],
    ) -> None:
        """Approved decision executes tools."""
        runner = interactive(
            mock_conversation, mock_llm_with_tools, mock_tools, tool_models
        )

        steps: list[LoopStep] = []
        approval_sent = False

        async for step in runner:
            steps.append(step)

            if step.type == "approval_request" and not approval_sent:
                # Approve the tool execution
                try:
                    step = await runner.asend(ApprovalDecision(approved=True))
                    steps.append(step)
                except StopAsyncIteration:
                    break
                approval_sent = True

        # Should have tool_call and tool_result after approval
        assert any(s.type == "tool_call" for s in steps)
        assert any(s.type == "tool_result" for s in steps)
        assert any(s.type == "finish" for s in steps)

    @pytest.mark.asyncio
    async def test_denied_with_feedback_continues_loop(
        self,
        mock_conversation: MagicMock,
        mock_tools: AsyncMock,
        tool_models: list[type],
    ) -> None:
        """Denied with feedback adds feedback to conversation and continues."""
        # LLM: first wants tool, after feedback gives final answer
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
            # After denial with feedback, LLM gives final answer
            ToolResponse(
                content="OK, I'll answer without searching.",
                model="test-model",
                usage={"prompt_tokens": 30, "completion_tokens": 15, "total_tokens": 45},
                cost=0.003,
                latency_ms=200,
                raw_response=None,
                tool_calls=[],
            ),
        ]

        runner = interactive(mock_conversation, llm, mock_tools, tool_models)

        steps: list[LoopStep] = []
        denial_sent = False

        async for step in runner:
            steps.append(step)

            if step.type == "approval_request" and not denial_sent:
                # Deny with feedback
                decision = ApprovalDecision(
                    approved=False,
                    feedback="Don't use search, just answer directly.",
                )
                try:
                    step = await runner.asend(decision)
                    steps.append(step)
                except StopAsyncIteration:
                    break
                denial_sent = True

        # Should have a tool_result step with the denial message
        denial_results = [
            s for s in steps
            if s.type == "tool_result" and s.content and "UserDenied" in s.content
        ]
        assert len(denial_results) >= 1

        # Should eventually finish
        assert any(s.type == "finish" for s in steps)

        # Tools should NOT have been executed
        mock_tools.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_denied_without_feedback_continues_with_default_message(
        self,
        mock_conversation: MagicMock,
        mock_llm_with_tools: AsyncMock,
        mock_tools: AsyncMock,
        tool_models: list[type],
    ) -> None:
        """Denied without feedback continues loop with default denial message."""
        runner = interactive(
            mock_conversation, mock_llm_with_tools, mock_tools, tool_models
        )

        steps: list[LoopStep] = []
        denial_sent = False

        async for step in runner:
            steps.append(step)

            if step.type == "approval_request" and not denial_sent:
                # Deny without feedback
                try:
                    step = await runner.asend(ApprovalDecision(approved=False))
                    steps.append(step)
                except StopAsyncIteration:
                    break
                denial_sent = True

        # Should have a tool_result step with UserDenied message
        denial_results = [
            s for s in steps
            if s.type == "tool_result" and s.content and "UserDenied" in s.content
        ]
        assert len(denial_results) >= 1

        # Should eventually finish
        assert any(s.type == "finish" for s in steps)

        # Tools should NOT have been executed
        mock_tools.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_none_decision_continues_with_default_denial(
        self,
        mock_conversation: MagicMock,
        mock_llm_with_tools: AsyncMock,
        mock_tools: AsyncMock,
        tool_models: list[type],
    ) -> None:
        """None decision (no asend) continues loop with default denial message."""
        runner = interactive(
            mock_conversation, mock_llm_with_tools, mock_tools, tool_models
        )

        steps: list[LoopStep] = []

        async for step in runner:
            steps.append(step)
            # Don't send any decision on approval_request - just continue
            # This means decision will be None on the next yield

        # Should have a tool_result step with UserDenied message
        denial_results = [
            s for s in steps
            if s.type == "tool_result" and s.content and "UserDenied" in s.content
        ]
        assert len(denial_results) >= 1

        # Should eventually finish
        assert any(s.type == "finish" for s in steps)

        # Tools should NOT have been executed
        mock_tools.execute.assert_not_called()


class TestInteractiveLoopEdgeCases:
    """Edge case tests for interactive() loop."""

    @pytest.mark.asyncio
    async def test_multiple_approvals_in_sequence(
        self,
        mock_conversation: MagicMock,
        mock_tools_multi: AsyncMock,
        tool_models: list[type],
    ) -> None:
        """Multiple tool calls each need approval."""
        # LLM that wants tools twice before finishing
        llm = AsyncMock()
        llm.complete_with_tools.side_effect = [
            ToolResponse(
                content="First search.",
                model="test-model",
                usage={"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
                cost=0.002,
                latency_ms=150,
                raw_response=None,
                tool_calls=[
                    ToolCall(id="call_1", name="search", arguments={"query": "first"})
                ],
            ),
            ToolResponse(
                content="Second search.",
                model="test-model",
                usage={"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
                cost=0.002,
                latency_ms=150,
                raw_response=None,
                tool_calls=[
                    ToolCall(id="call_2", name="search", arguments={"query": "second"})
                ],
            ),
            ToolResponse(
                content="All done.",
                model="test-model",
                usage={"prompt_tokens": 30, "completion_tokens": 15, "total_tokens": 45},
                cost=0.003,
                latency_ms=200,
                raw_response=None,
                tool_calls=[],
            ),
        ]

        runner = interactive(mock_conversation, llm, mock_tools_multi, tool_models)

        steps: list[LoopStep] = []
        approval_count = 0

        async for step in runner:
            steps.append(step)

            if step.type == "approval_request":
                approval_count += 1
                try:
                    step = await runner.asend(ApprovalDecision(approved=True))
                    steps.append(step)
                except StopAsyncIteration:
                    break

        # Should have had 2 approval requests
        assert approval_count == 2
        # Should have finished
        assert any(s.type == "finish" for s in steps)

    @pytest.mark.asyncio
    async def test_max_steps_exceeded_in_interactive(
        self,
        mock_conversation: MagicMock,
        mock_llm_infinite_tools: AsyncMock,
        mock_tools: AsyncMock,
        tool_models: list[type],
    ) -> None:
        """MaxStepsExceededError raised in interactive mode."""
        config = LoopConfig(max_steps=2)

        runner = interactive(
            mock_conversation,
            mock_llm_infinite_tools,
            mock_tools,
            tool_models,
            config=config,
        )

        with pytest.raises(MaxStepsExceededError) as exc_info:
            async for step in runner:
                if step.type == "approval_request":
                    try:
                        await runner.asend(ApprovalDecision(approved=True))
                    except StopAsyncIteration:
                        break

        assert exc_info.value.max_steps == 2

    @pytest.mark.asyncio
    async def test_stop_on_error_in_interactive(
        self,
        mock_conversation: MagicMock,
        mock_llm_with_tools: AsyncMock,
        mock_tools_with_error: AsyncMock,
        tool_models: list[type],
    ) -> None:
        """stop_on_error works in interactive mode."""
        config = LoopConfig(stop_on_error=True)

        runner = interactive(
            mock_conversation,
            mock_llm_with_tools,
            mock_tools_with_error,
            tool_models,
            config=config,
        )

        steps: list[LoopStep] = []
        async for step in runner:
            steps.append(step)
            if step.type == "approval_request":
                try:
                    step = await runner.asend(ApprovalDecision(approved=True))
                    steps.append(step)
                except StopAsyncIteration:
                    break

        # Should have error step
        error_steps = [s for s in steps if s.type == "error"]
        assert len(error_steps) == 1
