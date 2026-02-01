# Product Requirements Document (PRD)
# Unchained - Loops Component

**Version:** 1.0
**Date:** November 2025
**Status:** Final Draft
**Package:** `rawagents.loops`

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Background & Motivation](#2-background--motivation)
3. [Goals & Non-Goals](#3-goals--non-goals)
4. [Technical Architecture](#4-technical-architecture)
5. [Detailed Requirements](#5-detailed-requirements)
6. [API Design](#6-api-design)
7. [Project Structure](#7-project-structure)
8. [Component Interactions](#8-component-interactions)
9. [Risks & Mitigations](#9-risks--mitigations)
10. [Success Criteria](#10-success-criteria)

---

## 1. Executive Summary

### 1.1 What We're Building

The **Loops Component** (`rawagents.loops`) is the control logic of the agent. It is a collection of **transparent, generator-based functions** that orchestrate the interaction between the Brain (`llm`), Memory (`state`), and Hands (`tools`).

Unlike `AgentExecutor` (LangChain) or `Task` (CrewAI), which are heavy classes that hide the execution flow, `loops` are simple Python functions that **yield** their status at every step. This gives the developer complete visibility into the agent's thought process and allows for real-time UI updates, logging, and intervention.

### 1.2 Key Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Architecture** | Generators (`yield`) | Allows the caller to "stream" the agent's thinking process. Enables easy pausing, logging, and UI integration without complex callbacks. |
| **State** | Stateless Functions | The loop function does not store history. It modifies the passed `state` object. This ensures the agent can be paused/resumed just by serializing the `state`. |
| **Concurrency** | Async Native | All loops are `async` by default to support parallel tool execution and non-blocking I/O. |
| **Intervention** | `generator.send()` | For Human-in-the-Loop, we use the native Python generator `send()` method to inject user approval or feedback mid-loop. |
| **Dependency** | Loose Coupling | Loops take interfaces (Protocols), not concrete implementations, allowing users to swap out the LLM or Tool Executor easily. |

### 1.3 Core Principle

**"The Loop is a Stream"**: You don't "run" an agent and wait for the result. You **subscribe** to an agent and watch it think.

---

## 2. Background & Motivation

### 2.1 Problem Statement

1.  **Black Box Execution**: In existing frameworks, `agent.run("input")` is a black box. If the agent loops infinitely or calls the wrong tool, you can't see why until it crashes.
2.  **Callback Hell**: To get real-time logs in LangChain, you have to implement `BaseCallbackHandler` and override 10 different methods (`on_tool_start`, `on_llm_end`, etc.).
3.  **Rigid Control Flow**: Implementing "Human Approval before Tool Execution" is notoriously difficult in standard frameworks because the loop doesn't natively pause.

### 2.2 Solution Strategy

We replace the "Engine" concept with a **Generator Protocol**.
*   The loop **yields** a `LoopStep` object for every significant event (Thought, Tool Call, Result).
*   The developer iterates over the generator: `for step in loop.run(...)`.
*   This puts the developer in control. They can `print(step)`, `log(step)`, or `break` whenever they want.

---

## 3. Goals & Non-Goals

### 3.1 Goals

**G1: Total Transparency**
*   Every interaction with the LLM and every tool execution must be yielded to the caller.

**G2: Human-in-the-Loop First**
*   Native support for pausing execution to ask for user confirmation (`interactive_loop`).

**G3: Simplistic API**
*   No class inheritance required. Just import a function `run_simple` and use it.

**G4: Safety Limits**
*   Hard limits on `max_steps` to prevent infinite loops and cost overruns.

### 3.2 Non-Goals

**NG1: Complex Graph Orchestration**
*   We are not building a DAG runner (like LangGraph) in v1. This is for sequential loops. Complex graphs should be built by composing multiple loops.

**NG2: Task Queues**
*   We do not handle background job queues or persistence of the loop state itself (only the conversation state).

---

## 4. Technical Architecture

### 4.1 High-Level Design

```
┌─────────────────────────┐
│       Developer         │
│  (Iterates Generator)   │
└───────────┬─────────────┘
            │ 1. Start Loop
            ▼
┌─────────────────────────┐       2. Read History  ┌──────────────┐
│      loops.simple       │ ◄──────────────────── │     State    │
│   (Generator Function)  │ ────────────────────► │ (Conversation)│
└───────────┬─────────────┘       7. Write Result  └──────────────┘
            │
            │ 3. Consult         ┌──────────────┐
            ├──────────────────► │      LLM     │
            │ ◄───────────────── │              │
            │                    └──────────────┘
            │
            │ 4. Yield Step (Thought)
            ▼
┌─────────────────────────┐       5. Execute       ┌──────────────┐
│      Developer          │ ────────────────────► │ ToolExecutor │
│  (Handles/Prints Step)  │ ◄──────────────────── │              │
└───────────┬─────────────┘       6. Result        └──────────────┘
            │
            │ 8. Yield Step (Result)
            ▼
         (Repeat)
```

### 4.2 The Data Model

We introduce a unified `LoopStep` model to represent any event in the loop.

```python
class LoopStep(BaseModel):
    """Atomic unit of agent progress."""
    step_id: str = Field(default_factory=uuid4)
    type: Literal["thought", "tool_call", "tool_result", "approval_request", "error", "finish"]

    # Payloads (Union-like)
    content: str | None = None              # Text thought
    tool_calls: list[ToolCall] | None = None # Request to execute
    tool_results: list[ToolResult] | None = None # Result of execution

    metadata: dict[str, Any] = {}           # Tokens, latency, cost

### LoopStep.metadata Structure

The `metadata` dict contains optimization and observability data populated by the loop strategies.
Fields available depend on the step type:

| Field | Type | Description | Available On |
|-------|------|-------------|--------------|
| `step_number` | `int` | The current iteration (1-indexed) | All step types |
| `model` | `str` | Model identifier that generated the response | `thought`, `tool_call`, `finish` |
| `usage` | `dict[str, int]` | Token usage statistics | `thought`, `tool_call`, `finish` |
| `cost` | `float \| None` | Estimated USD cost of the LLM call | `thought`, `tool_call`, `finish` |
| `latency_ms` | `float` | Response latency in milliseconds | `thought`, `tool_call`, `finish` |

**`usage` dict structure:**
```python
{
    "prompt_tokens": int,      # Tokens in the input
    "completion_tokens": int,  # Tokens in the response
    "total_tokens": int,       # Sum of prompt + completion
}
```

**Example: Accessing metadata**
```python
async for step in loops.simple(llm, conversation, tools):
    if step.type == "thought":
        print(f"Step {step.metadata['step_number']}")
        print(f"Model: {step.metadata['model']}")
        print(f"Cost: ${step.metadata.get('cost', 0):.4f}")
        print(f"Latency: {step.metadata['latency_ms']:.0f}ms")
        print(f"Tokens: {step.metadata['usage']['total_tokens']}")
```

---

## 5. Detailed Requirements

### 5.1 `loops.simple()` (The Workhorse)

The standard ReAct-style loop.

```python
async def simple(
    llm: AsyncLLM,
    conversation: Conversation,
    tools: ToolExecutor | None = None,
    tool_schemas: list[dict[str, Any]] | list[type[BaseModel]] | None = None,
    *,
    config: LoopConfig | None = None,
    context: dict[str, Any] | None = None,
) -> AsyncGenerator[LoopStep, None]:
```

*   **Parameters**:
    *   `llm`: The LLM client for completions.
    *   `conversation`: The conversation state container.
    *   `tools`: The tool executor. Optional if no tools are used.
    *   `tool_schemas`: Optional list of tool schemas or Pydantic models for the LLM. If `None`, schemas are automatically fetched from the tool executor (if provided). Use this to explicitly override which tools the LLM sees, or to provide schemas without a ToolExecutor.
    *   `config`: Optional `LoopConfig` for customizing behavior. Uses defaults if `None`.
    *   `context`: Injection context dict for tool execution. Keys should match parameter names decorated with `Annotated[T, Inject]` in your tools.

*   **Logic**:
    1.  Fetch history from `conversation`.
    2.  Call `llm.complete_with_tools()`.
    3.  **Yield** `LoopStep(type="thought", content=response)`.
    4.  If no tool calls: **Yield** `LoopStep(type="finish")` and return.
    5.  If tool calls:
        *   **Yield** `LoopStep(type="tool_call", tool_calls=...)`.
        *   Execute tools via `tools.execute(context=context)`.
        *   **Yield** `LoopStep(type="tool_result", tool_results=...)`.
        *   Update `conversation` with results.
    6.  Repeat until `max_steps`.

*   **Raises**: `MaxStepsExceededError` if `max_steps` is reached without completion.

**Example with explicit tool_schemas:**
```python
# Provide schemas explicitly (useful for testing or custom tool formats)
custom_schemas = [
    {"type": "function", "function": {"name": "search", "parameters": {...}}}
]

async for step in loops.simple(llm, conv, tools, tool_schemas=custom_schemas):
    ...
```

**Example with context injection:**
```python
@tool
def query_db(sql: str, db: Annotated[Database, Inject]) -> str:
    """Execute a database query."""
    return db.execute(sql)

# Pass the database connection via context
async for step in loops.simple(llm, conv, tools, context={"db": my_database}):
    ...
```

### 5.2 `loops.interactive()` (Human-in-the-Loop)

Identical to `loops.simple()`, but pauses before execution to request human approval.

```python
async def interactive(
    llm: AsyncLLM,
    conversation: Conversation,
    tools: ToolExecutor | None = None,
    tool_schemas: list[dict[str, Any]] | list[type[BaseModel]] | None = None,
    *,
    config: LoopConfig | None = None,
    context: dict[str, Any] | None = None,
) -> AsyncGenerator[LoopStep, ApprovalDecision | None]:
```

*   **Parameters**: Same as `loops.simple()`.
*   **Returns**: An async generator that yields `LoopStep` and can receive `ApprovalDecision` via `asend()`.

*   **Logic Change**:
    *   Instead of executing tools immediately:
    *   **Yield** `LoopStep(type="approval_request", tool_calls=...)`.
    *   Wait for input via `asend(ApprovalDecision)`.
    *   If `approved=True`: Execute tools.
    *   If `approved=False`: Inject "UserDenied: {feedback}" into `conversation` and let LLM try again.

*   **Raises**: `MaxStepsExceededError` if `max_steps` is reached.

### 5.3 `ApprovalDecision` Type

The type used to send approval decisions back to the `interactive` loop.

```python
class ApprovalDecision(BaseModel):
    """Human decision for interactive approval requests."""
    approved: bool       # True to proceed with tool execution
    feedback: str | None = None  # Optional text feedback if denied
```

**Usage:**
```python
from rawagents import loops, ApprovalDecision

runner = loops.interactive(llm, conv, tools)

async for step in runner:
    if step.type == "approval_request":
        print(f"Agent wants to run: {step.tool_calls}")
        user_ok = input("Approve? (y/n) ") == "y"

        if user_ok:
            decision = ApprovalDecision(approved=True)
        else:
            decision = ApprovalDecision(
                approved=False,
                feedback="Please use a different approach"
            )

        try:
            await runner.asend(decision)
        except StopAsyncIteration:
            break
    elif step.type == "finish":
        print(f"Result: {step.content}")
```

When the user denies with feedback, the feedback is injected into the conversation as a tool result with the format `"UserDenied: {feedback}"`, allowing the LLM to understand why the action was rejected and adjust its approach.

### 5.4 `swarm_loop` (Parallel Execution) - **Planned**

**Status:** Not yet implemented. This section describes planned functionality.

Executes a list of sub-agents in parallel.

*   **Inputs**:
    *   `agents`: A list of initialized `(state, llm, tools)` tuples.
*   **Logic**:
    *   Uses `asyncio.gather` to advance all agents one step.
    *   Yields a `Step` containing a map of agent_id -> step.

---

## 6. API Design

### 6.1 Standard Usage

```python
from rawagents import AsyncLLM, Conversation, ToolExecutor, tool, loops


@tool
def search(query: str) -> str:
    """Search for nearby coffee shops."""
    ...


async def run_agent() -> None:
    llm = AsyncLLM(model="openai/gpt-4o")
    conv = Conversation()
    tools = ToolExecutor([search])

    conv.add_user("Find me a coffee shop.")

    async for step in loops.simple(llm=llm, conversation=conv, tools=tools, context={}):
        if step.type == "thought":
            print(f"Thinking: {step.content}")
        elif step.type == "tool_call":
            print(f"Calling: {step.tool_calls}")
        elif step.type == "tool_result":
            print(f"Result: {step.tool_results}")
```

### 6.2 Human Approval Usage

```python
from rawagents import ApprovalDecision

runner = loops.interactive(llm, conv, tools)

async for step in runner:
    if step.type == "approval_request":
        print(f"Agent wants to run: {step.tool_calls}")
        user_ok = input("Approve? (y/n) ") == "y"
        decision = ApprovalDecision(approved=user_ok)
        try:
            await runner.asend(decision)
        except StopAsyncIteration:
            break
```

---

## 7. Project Structure

```text
src/rawagents/loops/
├── __init__.py         # Exports: simple, interactive, swarm
├── types.py            # LoopStep, StepType
├── strategies/
│   ├── __init__.py
│   ├── simple.py       # run_simple logic
│   ├── interactive.py  # run_interactive logic
│   └── swarm.py        # run_swarm logic
└── utils.py            # Safety checks, formatting
```

---

## 8. Component Interactions

*   **State (Conversation)**: The loop has a **Read/Write** relationship with State.
    *   *Read:* At the start of every iteration, it calls `state.get_history()` to build the context for the LLM.
    *   *Write:* After the LLM responds or tools execute, it calls `state.add_assistant()` and `state.add_tool_result()` to persist the new events.
*   **LLM**: The loop calls `llm.complete_with_tools()`. It relies on the LLM to handle retries and provider abstraction.
*   **Tools**: The loop delegates actual execution to `tools.execute()`. The loop is responsible for deciding *when* to call it, but `tools` handles the *how*.
*   **Prompts**: The loop does **not** interact with prompts directly.
    *   *Why?* Prompt rendering is a "pre-loop" activity. You use `prompts.render()` to generate the system message, add it to `state`, and *then* start the loop. This keeps the loop logic pure and agnostic to your templating engine.

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Infinite Loops** | High | Enforce `max_steps` default (e.g., 15). User must explicitly override to disable. |
| **Context Overflow** | Medium | The loop monitors `llm` errors. If `ContextWindowExceeded`, it triggers `state.strategy.truncate()` (future feature). |
| **Async Complexity** | Medium | Loops are async-first; use `asyncio.run()` if synchronous execution is needed. |
| **Error Propagation** | Medium | Wrap tool execution in try/catch blocks *inside the loop* so one tool failure doesn't crash the agent. |

---

## 10. Success Criteria

1.  [ ] **Streaming**: Can print thoughts character-by-character (if LLM supports it) or step-by-step to console.
2.  [ ] **Intervention**: Can successfully deny a tool call in `interactive_loop` and see the agent recover/respond to the denial.
3.  [ ] **Stability**: Agent gracefully handles tool errors without crashing the Python process.
4.  [ ] **Observability**: A `Step` object contains sufficient metadata (latency, tokens) to build a dashboard.

