# Product Requirements Document (PRD)
# AI Components Library - Tool Executor Component

**Version:** 1.1
**Date:** November 2025
**Status:** Draft
**Author:** Tawab Safi

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Background & Motivation](#2-background--motivation)
3. [Goals & Non-Goals](#3-goals--non-goals)
4. [Technical Architecture](#4-technical-architecture)
5. [Detailed Requirements](#5-detailed-requirements)
6. [API Design](#6-api-design)
7. [Project Structure](#7-project-structure)
8. [Implementation Approach](#8-implementation-approach)
9. [Risks & Mitigations](#9-risks--mitigations)
10. [Success Criteria](#10-success-criteria)
11. [Timeline](#11-timeline)
12. [Component Relationship Diagram](#12-component-relationship-diagram)

---

## 1. Executive Summary

### 1.1 What We're Building

The **Tool Executor Component** (`rawagents.tools`) is the "Hands" of the agentic system. It is a stateless dispatcher that manages the **definition, registry, schema generation, and execution** of tools.

Unlike rigid frameworks that force you to inherit from a `BaseTool` class, this component adopts a **"Functions, not Frameworks"** philosophy. It wraps standard Python callables (functions, coroutines, classes) into a unified interface compatible with LLMs.

### 1.2 Key Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Definition** | Polymorphic | Support `@tool` decorators, Pydantic models, and Classes. Users shouldn't rewrite code to fit our framework. |
| **Schema Gen** | Native Pydantic | We use Pydantic to generate OpenAI-compatible JSON schemas directly. Compatible with LiteLLM. |
| **Execution** | In-Process | We do NOT implement sandboxing (Docker/WASM) inside the library. Users must handle isolation externally if needed. |
| **Injection** | Type-Hint Based | We use `Annotated[T, Inject]` to pass runtime context (e.g., UserID) to tools without exposing it to the LLM. |
| **Concurrency** | Async First | The core executor is async to allow parallel tool calls (e.g., `gather(search_a, search_b)`). |

### 1.3 Core Principle

**"The Executor is a Dispatcher"**: It does not plan. It does not reason. It simply takes a request from the LLM, finds the matching Python code, executes it safely, and returns the result.

---

## 2. Background & Motivation

### 2.1 Problem Statement

1.  **Boilerplate**: Creating tools often requires writing manual JSON schemas, which is error-prone and tedious.
2.  **Context Gap**: Tools often need runtime data (Database connection, User ID) that the LLM *doesn't know about*. Frameworks usually force you to pass these as global variables or hacky strings.
3.  **Vendor Lock-in**: Tools written for LangChain often don't work with other libraries.
4.  **Safety**: Executing code from an LLM can crash the process if exceptions aren't caught and formatted as text errors.

### 2.2 Solution Strategy

We will build a **Universal Adaptor** that:
1.  Introspects Python functions to generate Schemas automatically.
2.  Intercepts execution to inject "Context" variables based on type hints.
3.  Wraps execution in a safety layer to catch exceptions and return `ToolResult` objects.

---

## 3. Goals & Non-Goals

### 3.1 Goals

**G1: Polymorphic Tool Definition**
- Support `@tool` decorator for functions.
- Support Pydantic models as input schemas.
- Support Class-based tools for stateful services.

**G2: Dependency Injection (Context)**
- Allow passing "invisible" arguments to tools (e.g., `user_id: Annotated[str, Inject]`).
- The LLM never sees these parameters in the JSON schema.

**G3: Automatic Schema Generation**
- Generate compliant `{"name": ..., "description": ..., "parameters": ...}` schemas for LiteLLM.

**G4: Middleware Support**
- Hooks for `pre_execute` (logging, approval) and `post_execute` (metrics).

### 3.2 Non-Goals

**NG1: Sandboxing**
- We will NOT run code in Docker/VMs. That is an infrastructure concern, not a library concern.

**NG2: Planning**
- The executor does NOT decide which tool to call. The LLM does that.

**NG3: State Persistence**
- The executor is stateless. It does not remember previous tool calls.

---

## 4. Technical Architecture

### 4.1 High-Level Design

```
┌───────────────────────────────────────────────────────────────────┐
│                         Your Agent Code                           │
│                                                                   │
│  @tool                                                            │
│  def get_weather(loc: str, user: Annotated[str, Inject]): ...     │
│                                                                   │
│  registry = ToolRegistry([get_weather])                           │
│  executor = ToolExecutor(registry)                                │
└───────────────────────────────────────────────────────────────────┘
                │                                  │
                ▼                                  ▼
┌──────────────────────────────┐   ┌────────────────────────────────┐
│       Tool Registry          │   │         Tool Executor          │
│ (Maps Name -> Callable)      │   │ (Handles Injection & Run)      │
└──────────────────────────────┘   └────────────────────────────────┘
                │
                ▼
┌──────────────────────────────┐
│      Context Manager         │
│  (Injects Runtime Deps)      │
└──────────────────────────────┘
```

### 4.2 The Data Model

The component relies on shared types for compatibility with `llm` and `state`.

```python
# From rawagents._shared.types
from rawagents._shared.types import ToolCall

# New type (To be added to _shared/types.py)
class ToolResult(BaseModel):
    tool_call_id: str
    name: str
    content: str  # The output (JSON or Text)
    is_error: bool = False
    metadata: dict[str, Any] = {}  # For metrics (latency, etc)
```

---

## 5. Detailed Requirements

### 5.1 Tool Definition

- **Function-based**:
  ```python
  @tool
  def add(a: int, b: int) -> int:
      """Add two numbers."""
      return a + b
  ```
- **Pydantic-based**:
  ```python
  class AddInput(BaseModel):
      a: int
      b: int
  
  tool = Tool.from_function(add, args_schema=AddInput)
  ```

### 5.2 Tool Registry

- **Registration**: `registry.register(tool)`
- **Schema Export**: `registry.get_schemas()` -> List[dict] (OpenAI format).
- **Lookup**: `registry.get(name)` -> Tool.

### 5.3 Execution Flow

1.  **Input**: `executor.execute(tool_call: ToolCall, context=...)`
    *   Accepts the `ToolCall` object defined in `_shared`.
2.  **Validation**: Validate `tool_call.arguments` against the tool's Pydantic schema.
3.  **Injection**: Inspect tool signature. If `Annotated[T, Inject]` is found, pull `T` from `context`.
4.  **Execution**: Call the underlying python function (await if async).
5.  **Result**: Wrap return value in `ToolResult`.
6.  **Error Handling**: If exception, catch it, format trace as string, return `ToolResult(is_error=True)`.

---

## 6. API Design

### 6.1 Defining Tools

```python
from rawagents.tools import tool, ToolContext, Inject
from typing import Annotated

@tool
def search_db(query: str, db: Annotated[Database, Inject]):
    """Search the user database."""
    return db.query(query)
```

### 6.2 Executing Tools

```python
from rawagents.tools import ToolRegistry, ToolExecutor
from rawagents._shared.types import ToolCall

# Setup
registry = ToolRegistry([search_db])
executor = ToolExecutor(registry)

# Get Schemas for LLM
schemas = registry.get_schemas() 
# Note: 'db' parameter is HIDDEN from schema because it's Injected

# Runtime
# tool_call comes from LLM
context = {"db": my_db_connection}

result = await executor.execute(tool_call, context=context)
print(result.content)
```

### 6.3 Middleware (Logging example)

```python
async def log_middleware(call, next_handler):
    print(f"Calling {call.name}...")
    result = await next_handler(call)
    print(f"Result: {result.is_error}")
    return result

executor = ToolExecutor(registry, middleware=[log_middleware])
```

---

## 7. Project Structure

```text
src/rawagents/tools/
├── __init__.py           # Exports
├── executor.py           # ToolExecutor class
├── registry.py           # ToolRegistry class
├── decorators.py         # @tool decorator
├── base.py               # BaseTool protocol
├── types.py              # ToolResult (re-exported from utils if moved), Context
└── converters.py         # Pydantic -> JSON Schema logic
```

---

## 8. Implementation Approach

### Phase 1: Core Definition (Day 1)
- Implement `BaseTool` protocol.
- Implement `@tool` decorator to wrap functions.
- Implement Schema generation using Pydantic `TypeAdapter`.
- **Action**: Move `ToolResult` to `src/rawagents/utils/types.py` so it is available globally.

### Phase 2: Registry & Context (Day 2)
- Implement `ToolRegistry`.
- Implement Dependency Injection logic (inspecting `Annotated`).

### Phase 3: Execution & Middleware (Day 3)
- Implement `ToolExecutor` using `ToolCall` from `_shared`.
- Add error handling and async support.
- Add middleware chain.

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Complex Types** | Medium | LLM tries to generate complex objects (lists/dicts) and fails validation. *Mitigation:* Use Pydantic's loose validation where possible. |
| **Async/Sync Mix** | High | Mixing async and sync code is hard in Python. *Mitigation:* `ToolExecutor` will `run_in_executor` for sync tools to prevent blocking the loop. |
| **Schema Bloat** | Low | Large docstrings create massive schemas. *Mitigation:* Truncate docstrings in schema generation if needed. |

---

## 10. Success Criteria

- [ ] **Auto-Schema**: Correctly hides `Inject` parameters from the JSON schema.
- [ ] **Injection**: Successfully passes a context object to a tool at runtime.
- [ ] **Safety**: Tool exception does not crash the main script.
- [ ] **Integration**: Works with `ToolCall` objects from `_shared`.

---

## 11. Timeline

- **Day 1**: Models & Decorators
- **Day 2**: Registry & Context Logic
- **Day 3**: Executor & Middleware

---

## 12. Component Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Your Application                                 │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       Agent Runtime (Loop)                               │
│                                                                          │
│  1. Call LLM ──────────────────────────► ┌───────────────┐               │
│                                          │      LLM      │               │
│  2. Receive ToolCall ◄────────────────── └───────────────┘               │
│                                                                          │
│  3. Execute ToolCall ───────┐                                            │
│                             │                                            │
│                             ▼                                            │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                      Tool Executor                                 │  │
│  │                                                                    │  │
│  │  ┌────────────┐      ┌────────────┐      ┌──────────────────┐      │  │
│  │  │ Registry   │ ───► │ Injector   │ ───► │ Safe Execution   │      │  │
│  │  └────────────┘      └────────────┘      └──────────────────┘      │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                             │                                            │
│  4. Return ToolResult ◄─────┘                                            │
│                                                                          │
│  5. Add to History ────────────────────► ┌───────────────┐               │
│                                          │ Conversation  │               │
│                                          └───────────────┘               │
└─────────────────────────────────────────────────────────────────────────┘
```
