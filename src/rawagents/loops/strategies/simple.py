"""Simple ReAct-style agent loop."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

from rawagents.utils.types import ToolCall
from rawagents.loops.exceptions import MaxStepsExceededError
from rawagents.loops.types import LoopConfig, LoopStep

if TYPE_CHECKING:
    from pydantic import BaseModel

    from rawagents.state import Conversation
    from rawagents.llm import AsyncLLM
    from rawagents.tools import ToolExecutor

__all__ = ["simple"]


async def simple(
    llm: "AsyncLLM",
    conversation: "Conversation",
    tools: "ToolExecutor" | None = None,
    tool_schemas: list[dict[str, Any]] | list[type["BaseModel"]] | None = None,
    *,
    config: LoopConfig | None = None,
    context: dict[str, Any] | None = None,
) -> AsyncGenerator[LoopStep, None]:
    """Standard ReAct-style agent loop.

    Orchestrates the conversation between user, LLM, and tools using
    the Reasoning-Action pattern:
    1. LLM receives conversation history
    2. LLM either responds with text (finish) or requests tools
    3. Tools are executed and results added to conversation
    4. Repeat until LLM gives final answer or max_steps reached

    Args:
        llm: The LLM client for completions.
        conversation: The conversation state container.
        tools: The tool executor. Optional if no tools are used.
        tool_schemas: Optional list of tool schemas/models for the LLM.
            If None, schemas are automatically fetched from the tool executor (if provided).
        config: Optional loop configuration. Uses defaults if None.
        context: Injection context for tool execution.

    Yields:
        LoopStep for each significant event (thought, tool_call,
        tool_result, error, finish).

    Raises:
        MaxStepsExceededError: If max_steps is reached without completion.

    Example:
        >>> async for step in loops.simple(llm, conv, tools):
        ...     if step.type == "thought":
        ...         print(f"Thinking: {step.content}")
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
        # 1. Get conversation history for LLM
        messages = conversation.get_history()

        # 2. Call LLM with tools (if any)
        response = await llm.complete_with_tools(
            messages=messages,
            tools=schemas,
            tool_choice=cfg.tool_choice,
            temperature=cfg.temperature,
        )

        # 3. Build metadata from response
        step_metadata: dict[str, Any] = {
            "step_number": step_num + 1,
            "model": response.model,
            "usage": response.usage,
            "cost": response.cost,
            "latency_ms": response.latency_ms,
        }

        # 4. Yield thought step if there's content
        if response.content:
            yield LoopStep(
                type="thought",
                content=response.content,
                metadata=step_metadata,
            )

        # 5. Check for tool calls
        if not response.tool_calls:
            # No tool calls = LLM is done
            # Add assistant message to conversation
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

        # 6. Yield tool_call step
        yield LoopStep(
            type="tool_call",
            tool_calls=response.tool_calls,
            metadata=step_metadata,
        )

        # 7. Add assistant message with tool calls to conversation
        conversation.add_assistant(
            content=response.content,
            tool_calls=[_tool_call_to_dict(tc) for tc in response.tool_calls],
            metadata={
                "cost": response.cost,
                "latency_ms": response.latency_ms,
                "model": response.model,
            },
        )

        # 8. Execute tools and collect results
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

            # Add tool result to conversation
            conversation.add_tool_result(
                tool_call_id=result.tool_call_id,
                content=result.content,
            )

            # Check for errors if stop_on_error is set
            if cfg.stop_on_error and result.is_error:
                yield LoopStep(
                    type="error",
                    content=f"Tool '{result.name}' failed: {result.content}",
                    tool_results=[result],
                    metadata={"step_number": step_num + 1},
                )
                return

        # 9. Yield tool_result step
        yield LoopStep(
            type="tool_result",
            tool_results=tool_results,
            metadata={"step_number": step_num + 1},
        )

    # Max steps exceeded
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
