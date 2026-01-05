"""Loops - The control logic of the agent.

The Loops component provides transparent, generator-based functions that
orchestrate the interaction between the LLM Client, Conversation, and Tools.

Core Principle: "The Loop is a Stream"
    You don't "run" an agent and wait for the result. You subscribe to
    an agent and watch it think.

Available Loops:
    simple: Standard ReAct-style loop for autonomous execution.
    interactive: Human-in-the-loop variant with approval requests.

Example:
    >>> from rawagents import loops
    >>>
    >>> async for step in loops.simple(llm, conv, tools):
    ...     if step.type == "thought":
    ...         print(f"Thinking: {step.content}")
    ...     elif step.type == "tool_call":
    ...         print(f"Calling tools: {step.tool_calls}")
    ...     elif step.type == "finish":
    ...         print(f"Done: {step.content}")
"""

from rawagents.loops.exceptions import (
    LoopCancelledError,
    LoopError,
    MaxStepsExceededError,
)
from rawagents.loops.strategies.interactive import interactive
from rawagents.loops.strategies.simple import simple
from rawagents.loops.types import (
    ApprovalDecision,
    LoopConfig,
    LoopStep,
    StepType,
)

__all__ = [
    # Loop functions
    "simple",
    "interactive",
    # Types
    "LoopStep",
    "LoopConfig",
    "ApprovalDecision",
    "StepType",
    # Exceptions
    "LoopError",
    "MaxStepsExceededError",
    "LoopCancelledError",
]
