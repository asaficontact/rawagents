"""Data types for the Loops component."""

from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from rawagents.utils.types import ToolCall, ToolResult

__all__ = [
    "StepType",
    "LoopStep",
    "LoopConfig",
    "ApprovalDecision",
]

StepType = Literal[
    "thought",  # LLM response with text content
    "tool_call",  # LLM requests tool execution
    "tool_result",  # Tool execution completed
    "approval_request",  # Waiting for human approval (interactive only)
    "error",  # Non-fatal error occurred
    "finish",  # Loop completed successfully
]


class LoopStep(BaseModel):
    """Atomic unit of agent progress.

    Every significant event in the loop is yielded as a LoopStep,
    giving the caller complete visibility into the agent's execution.

    Attributes:
        step_id: Unique identifier for this step.
        type: The kind of event (thought, tool_call, etc.).
        content: Text content (for thought, error, finish types).
        tool_calls: List of tool call requests (for tool_call type).
        tool_results: List of tool execution results (for tool_result type).
        metadata: Additional info (tokens, latency, cost, step_number).
    """

    step_id: str = Field(default_factory=lambda: str(uuid4()))
    type: StepType
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_results: list[ToolResult] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LoopConfig(BaseModel):
    """Configuration for loop execution.

    Attributes:
        max_steps: Maximum loop iterations (safety limit). Default 15.
        tool_choice: LLM tool selection mode. Default "auto".
        temperature: LLM sampling temperature. Default 0.7.
        stop_on_error: Stop loop if tool execution fails. Default False.
    """

    max_steps: int = Field(default=15, ge=1, le=100)
    tool_choice: str = "auto"
    temperature: float = 0.7
    stop_on_error: bool = False


class ApprovalDecision(BaseModel):
    """Human decision for interactive approval requests.

    Attributes:
        approved: True to proceed with tool execution.
        feedback: Optional text feedback to inject if denied.
    """

    approved: bool
    feedback: str | None = None
