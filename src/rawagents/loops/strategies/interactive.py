"""Interactive agent loop with human-in-the-loop approval."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

from rawagents.utils.types import ToolCall
from rawagents.loops.exceptions import LoopCancelledError, MaxStepsExceededError
from rawagents.loops.types import ApprovalDecision, LoopConfig, LoopStep

if TYPE_CHECKING:
    from pydantic import BaseModel

    from rawagents.state import Conversation
    from rawagents.llm import AsyncLLM
    from rawagents.tools import ToolExecutor

__all__ = ["interactive"]


async def interactive(
    llm: "AsyncLLM",
    conversation: "Conversation",
    tools: "ToolExecutor" | None = None,
    tool_schemas: list[dict[str, Any]] | list[type["BaseModel"]] | None = None,
    *,
    config: LoopConfig | None = None,
    context: dict[str, Any] | None = None,
) -> AsyncGenerator[LoopStep, ApprovalDecision | None]:
    """Interactive agent loop with human approval for tool execution.

    Similar to simple(), but yields approval_request steps before
    executing tools. The caller must send an ApprovalDecision back
    via asend() to continue.

    Args:
        llm: The LLM client for completions.
        conversation: The conversation state container.
        tools: The tool executor. Optional if no tools are used.
        tool_schemas: Optional list of tool schemas/models for the LLM.
            If None, schemas are automatically fetched from the tool executor (if provided).
        config: Optional loop configuration.
        context: Injection context for tool execution.

    Yields:
        LoopStep for each event. approval_request steps require
        asend(ApprovalDecision) to continue.

    Raises:
        MaxStepsExceededError: If max_steps is reached.
        LoopCancelledError: If user denies without feedback.

    Example:
        >>> runner = loops.interactive(llm, conv, tools)
        >>> async for step in runner:
        ...     if step.type == "approval_request":
        ...         user_ok = input("Approve? (y/n): ") == "y"
        ...         decision = ApprovalDecision(approved=user_ok)
        ...         try:
        ...             await runner.asend(decision)
        ...         except StopAsyncIteration:
        ...             break
        ...     elif step.type == "finish":
        ...         print(f"Result: {step.content}")
    """
    cfg = config or LoopConfig()
    ctx = context or {}
    
    # Resolve schemas: Explicit > Executor > Empty
    if tool_schemas is not None:
        schemas = tool_schemas
    elif tools is not None:
        schemas = tools.get_schemas()
    else:
        schemas = []

    for step_num in range(cfg.max_steps):
        messages = conversation.get_history()

        response = await llm.complete_with_tools(
            messages=messages,
            tools=schemas,
            tool_choice=cfg.tool_choice,
            temperature=cfg.temperature,
        )

        step_metadata: dict[str, Any] = {
            "step_number": step_num + 1,
            "model": response.model,
            "usage": response.usage,
            "cost": response.cost,
            "latency_ms": response.latency_ms,
        }

        if response.content:
            yield LoopStep(
                type="thought",
                content=response.content,
                metadata=step_metadata,
            )

        if not response.tool_calls:
            conversation.add_assistant(
                content=response.content,
                metadata={
                    "cost": response.cost,
                    "latency_ms": response.latency_ms,
                    "model": response.model,
                },
            )
            yield LoopStep(
                type="finish",
                content=response.content,
                metadata=step_metadata,
            )
            return

        # Yield approval request and wait for decision
        decision: ApprovalDecision | None = yield LoopStep(
            type="approval_request",
            tool_calls=response.tool_calls,
            metadata=step_metadata,
        )

        if decision is None or not decision.approved:
            # User denied - inject feedback or cancel
            feedback = decision.feedback if decision else "User denied execution."

            # 1. Add the Assistant Message (The Request)
            # We must add this first so the history is valid (Assistant -> Tool)
            conversation.add_assistant(
                content=response.content,
                tool_calls=[_tool_call_to_dict(tc) for tc in response.tool_calls],
                metadata={
                    "cost": response.cost,
                    "latency_ms": response.latency_ms,
                    "model": response.model,
                },
            )

            # 2. Resolve tool calls with denial message
            for tc in response.tool_calls:
                conversation.add_tool_result(
                    tool_call_id=tc.id,
                    content=f"UserDenied: {feedback}",
                )

            # Yield the denial as a result step so caller knows what happened
            yield LoopStep(
                type="tool_result",
                content=f"UserDenied: {feedback}",
                tool_results=[],  # No actual results, just denial
                metadata={"step_number": step_num + 1},
            )
            continue  # Let LLM try again with the denial feedback

        # User approved - proceed with tool execution
        yield LoopStep(
            type="tool_call",
            tool_calls=response.tool_calls,
            metadata=step_metadata,
        )

        conversation.add_assistant(
            content=response.content,
            tool_calls=[_tool_call_to_dict(tc) for tc in response.tool_calls],
            metadata={
                "cost": response.cost,
                "latency_ms": response.latency_ms,
                "model": response.model,
            },
        )

        tool_results = []
        
        # Safety check: If LLM calls tools but no executor provided, it's an error state
        if response.tool_calls and tools is None:
             # This shouldn't happen if schemas=[] but LLMs can hallucinate tool calls
             yield LoopStep(
                type="error",
                content="LLM attempted to call tools but no ToolExecutor was provided.",
                metadata={"step_number": step_num + 1}
             )
             return

        for tool_call in response.tool_calls:
            # We know tools is not None here due to check above
            assert tools is not None 
            result = await tools.execute(tool_call, context=ctx)
            tool_results.append(result)
            conversation.add_tool_result(
                tool_call_id=result.tool_call_id,
                content=result.content,
            )

            if cfg.stop_on_error and result.is_error:
                yield LoopStep(
                    type="error",
                    content=f"Tool '{result.name}' failed: {result.content}",
                    tool_results=[result],
                    metadata={"step_number": step_num + 1},
                )
                return

        yield LoopStep(
            type="tool_result",
            tool_results=tool_results,
            metadata={"step_number": step_num + 1},
        )

    raise MaxStepsExceededError(
        max_steps=cfg.max_steps,
        steps_taken=cfg.max_steps,
    )


def _tool_call_to_dict(tc: ToolCall) -> dict[str, Any]:
    """Convert ToolCall to dict for conversation storage."""
    return {
        "id": tc.id,
        "name": tc.name,
        "arguments": tc.arguments,
    }
