# Product Requirements Document (PRD)
# AI Components Library - Universal LLM Client

**Version:** 3.0
**Date:** November 2025
**Status:** Final Draft
**Author:** Tawab Safi

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Background & Motivation](#2-background--motivation)
3. [Goals & Non-Goals](#3-goals--non-goals)
4. [Technical Architecture](#4-technical-architecture)
5. [Detailed Requirements](#5-detailed-requirements)
6. [API Design](#6-api-design)
7. [Project Structure & Packaging](#7-project-structure--packaging)
8. [Implementation Approach](#8-implementation-approach)
9. [Dependencies & Integration](#9-dependencies--integration)
10. [Testing Strategy](#10-testing-strategy)
11. [Risks & Mitigations](#11-risks--mitigations)
12. [Success Criteria](#12-success-criteria)
13. [Timeline & Milestones](#13-timeline--milestones)
14. [Appendix](#14-appendix)
15. [Component Relationship Diagram](#15-component-relationship-diagram)

---

## 1. Executive Summary

### 1.1 What We're Building

A **monolithic AI components library** starting with a Universal LLM Client as the first component. The library provides reusable building blocks for AI systems with a focus on simplicity and ease of use.

**The Universal LLM Client** provides:
- **Unified API** across all providers (OpenAI, Anthropic, Google, 100+ more)
- **Structured outputs** with Pydantic validation and automatic retry
- **Function/tool calling** with typed schemas (returns tool calls, does NOT execute them)
- **Streaming** for text responses (separate from structured output/tools for simplicity)
- **Both sync and async clients** for flexible usage patterns
- **Infrastructure features**: retries, fallbacks, cost tracking, logging hooks

**Important Design Decision:** This is an LLM *client*, not an agent framework. Tool calls are returned to the caller for execution - the client does not execute tools or manage conversation loops. This separation enables custom tool execution strategies and keeps the client focused on LLM communication.

### 1.2 Key Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **API to use** | `litellm.completion()` (Chat Completions) | More reliable, works with all 100+ providers, mature Instructor integration. Responses API is OpenAI-only and still in beta. |
| **Packaging** | Monolithic library | Simpler to maintain, components share code, one install. Can split later if needed. |
| **Streaming scope** | Text-only streaming | Streaming with tools/structured output adds complexity. Keep separate for v1.0. |
| **Sync/Async** | Two separate client classes | `LLM` (sync) and `AsyncLLM` (async) for clarity. |
| **Instructor integration** | `instructor.from_litellm()` | Proven reliable pattern. Do NOT use `instructor.from_provider("litellm/...")` - it had issues until recently and should be avoided for stability. |
| **Tool execution** | Client returns tool calls only | Tool execution belongs in agent/orchestrator layer. Keeps client focused and composable. |

### 1.3 Why We're Building It

1. **Learn** the implementation details of LLM client architecture
2. **Reuse** a familiar, well-understood component across future projects

### 1.4 Core Principle

**Application-driven development**: Only build what's needed for real projects. This PRD defines the scope for v1.0 based on common agent requirements.

### 1.5 Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Provider Abstraction | LiteLLM | Unified API for 100+ providers, streaming, cost tracking, retries |
| Structured Output | Instructor | Pydantic validation, automatic retry on validation failure |
| Schema Validation | Pydantic | Type-safe response models |

---

## 2. Background & Motivation

### 2.1 Problem Statement

Building AI agents and applications requires consistent, reliable LLM interactions across different providers. Current challenges include:

1. **Provider fragmentation**: Each provider has different APIs, authentication, and response formats
2. **Structured output complexity**: Getting validated, typed responses requires significant boilerplate
3. **Reliability concerns**: Production systems need retries, fallbacks, and proper error handling
4. **Observability gaps**: Tracking costs, latency, and usage across providers is difficult
5. **Tool calling inconsistencies**: Function calling schemas differ between providers

### 2.2 Technology Evaluation

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| **Build from scratch** | Maximum control, deep learning | High maintenance, provider API changes | ❌ Too much effort |
| **LangChain** | Feature-rich | Heavy abstractions, complex | ❌ Overkill |
| **LiteLLM alone** | Provider abstraction, infra features | Basic structured output (JSON mode only) | ⚠️ Needs Instructor |
| **Instructor alone** | Excellent structured output | No rate limiting, cost tracking | ⚠️ Needs LiteLLM |
| **PydanticAI** | Type-safe agents | Opinionated, agent-focused | ❌ Wrong abstraction level |
| **LiteLLM + Instructor** | Best of both worlds | Two libraries to understand | ✅ Selected |

### 2.3 API Choice: Completions vs Responses

| Aspect | Chat Completions | Responses API |
|--------|------------------|---------------|
| Provider support | ✅ All 100+ providers | ❌ OpenAI-centric |
| Stability | ✅ Mature, industry standard | ⚠️ Beta |
| Instructor support | ✅ Full | ❌ None |
| Latency | ✅ Faster (no orchestration overhead) | ❌ Slower |
| Model quality | ✅ Same underlying models | ✅ Same underlying models |

**Decision**: Use `litellm.completion()` (Chat Completions API)

### 2.4 What LiteLLM Provides

- Unified OpenAI-format API for 100+ providers
- Built-in retry with exponential backoff for rate limits (429, 503, 500, 408)
- Cost tracking via `response._hidden_params["response_cost"]`
- Custom callback system for logging (`CustomLogger` class)
- Streaming support for tokens and tool calls
- Exception mapping to OpenAI exception types

### 2.5 What Instructor Adds

- Pydantic model-based structured output extraction
- Automatic retry when validation fails (separate from API retries)
- `instructor.from_litellm(completion)` for sync
- `instructor.from_litellm(acompletion)` for async
- `create_with_completion()` to get both parsed model and raw response (for cost)

### 2.6 Instructor + LiteLLM Reliability Notes

**Known working pattern (USE THIS):**
```python
# Sync - PROVEN RELIABLE
from litellm import completion
import instructor

client = instructor.from_litellm(completion)
result = client.chat.completions.create(model="...", response_model=Model, ...)

# Async - PROVEN RELIABLE
from litellm import acompletion
import instructor

client = instructor.from_litellm(acompletion)
result = await client.chat.completions.create(model="...", response_model=Model, ...)

# Get cost/usage with structured output
result, raw = client.chat.completions.create_with_completion(...)
cost = raw._hidden_params.get("response_cost")
```

**Known issues to avoid:**
- ❌ `instructor.from_provider("litellm/...")` - Had issues until recently (see [GitHub #1710](https://github.com/567-labs/instructor/issues/1710)). Avoid for stability.
- ⚠️ Some providers (e.g., Bedrock) may need `litellm.drop_params=True` for unsupported params
- ⚠️ Azure cost tracking can be inaccurate - set `base_model` in config (see Section 5.6)
- ✅ Keep versions pinned to avoid compatibility issues

**References:**
- [Instructor Issue #1710 - from_provider LiteLLM support](https://github.com/567-labs/instructor/issues/1710)
- [LiteLLM + Instructor Tutorial](https://docs.litellm.ai/docs/tutorials/instructor)
- [Instructor LiteLLM Integration](https://python.useinstructor.com/integrations/litellm/)

---

## 3. Goals & Non-Goals

### 3.1 Goals

**G1: Simple, Clean Interface**
- Minimal API surface that's easy to understand
- Separate sync and async clients for clarity
- Works in 30 seconds with sensible defaults

**G2: Structured Output Excellence**
- First-class Pydantic model support for response schemas
- Automatic validation with configurable retry on failure
- Access to cost/usage data even with structured output

**G3: Function/Tool Calling**
- Typed tool schemas using Pydantic models
- Consistent tool call handling across providers
- Combined with structured output OR separate (not streamed)

**G4: Text Streaming (Separate Feature)**
- Token streaming for real-time text responses
- NOT combined with tools or structured output in v1.0
- Keeps implementation simpler and more reliable

**G5: Production-Ready Infrastructure**
- Automatic retries with exponential backoff (via LiteLLM)
- Per-call cost and token accounting
- Extensible logging with metadata support
- Both sync and async support for parallel operations

**G6: Easy Distribution**
- Single `pip install` from git repository
- Works immediately with environment variables
- Comprehensive examples and documentation

### 3.2 Non-Goals

**NG1: Agent Framework**
- This is an LLM client, not an agent orchestration system
- Agent loops, memory, and planning are separate components

**NG2: Streaming + Tools/Structured Combined**
- Streaming with function calling or structured output adds significant complexity
- Will be considered for v2.0 after core is stable

**NG3: Prompt Management**
- No templating system built-in
- Separate component for future

**NG4: RAG/Embeddings**
- Embedding generation is out of scope for this component
- Separate component for future

**NG5: Multi-Modal Support (v1.0)**
- Focus on text/chat completion first
- Image/audio may be added in v2.0

**NG6: Responses API Support**
- OpenAI's new Responses API is out of scope
- Chat Completions API is the target

**NG7: Tool Execution / Agent Loops**
- The client returns tool calls but does NOT execute them
- Tool execution, agent loops, and orchestration are separate components
- This keeps the client focused on LLM communication only
- A future "Agent" component will handle tool orchestration

**NG8: Automatic Conversation Management**
- The client does not maintain conversation state
- Each call is stateless - the caller manages message history
- This enables flexible memory strategies in higher-level components

---

## 4. Technical Architecture

### 4.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Your Application                           │
│   from rawagents import LLM                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 rawagents.llm                               │
│  ┌────────────────────────┐  ┌─────────────────────────────┐   │
│  │  LLM                │  │  AsyncLLM                 │   │
│  │  (Sync)                │  │  (Async)                    │   │
│  │                        │  │                             │   │
│  │  • complete()          │  │  • complete()               │   │
│  │  • complete_structured │  │  • complete_structured()    │   │
│  │  • complete_with_tools │  │  • complete_with_tools()    │   │
│  │  • stream()            │  │  • stream()                 │   │
│  └────────────────────────┘  └─────────────────────────────┘   │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐    │
│  │  LLMConfig   │  │  LLMResponse │  │  ToolCall          │    │
│  │  (Settings)  │  │  (Results)   │  │  (Tool results)    │    │
│  └──────────────┘  └──────────────┘  └────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┴────────────────────┐
         │                                         │
         ▼                                         ▼
┌─────────────────────┐               ┌─────────────────────┐
│     Instructor      │               │      LiteLLM        │
│  from_litellm()     │───────────────│  completion()       │
│  (structured out)   │               │  acompletion()      │
└─────────────────────┘               └─────────────────────┘
                                               │
                    ┌──────────────────────────┼──────────────────────────┐
                    │                          │                          │
                    ▼                          ▼                          ▼
             ┌────────────┐             ┌────────────┐             ┌────────────┐
             │   OpenAI   │             │  Anthropic │             │   Google   │
             │    API     │             │    API     │             │    API     │
             └────────────┘             └────────────┘             └────────────┘
```

### 4.2 Design Principles

1. **Two Clients, Not One**: Separate `LLM` (sync) and `AsyncLLM` (async) rather than mixing patterns
2. **Composition Over Configuration**: Use Instructor for structured output, LiteLLM for everything else
3. **Streaming is Separate**: `stream()` only returns text chunks, no tools or structured output
4. **Explicit Over Implicit**: Methods clearly indicate what they do (`complete_structured`, `complete_with_tools`)

### 4.3 Method Routing

| Method | Uses Instructor? | Uses LiteLLM Directly? | Purpose |
|--------|------------------|------------------------|---------|
| `complete()` | No | Yes | Basic text completion |
| `complete_structured()` | Yes | Via Instructor | Pydantic model extraction |
| `complete_with_tools()` | No | Yes | Function/tool calling |
| `stream()` | No | Yes | Text streaming only |

---

## 5. Detailed Requirements

### 5.1 Provider Support

#### 5.1.1 Required Providers (v1.0)

| Provider | Model Format | Features |
|----------|--------------|----------|
| OpenAI | `openai/gpt-4o` | Chat, streaming, tools, structured output |
| Anthropic | `anthropic/claude-3-5-sonnet-latest` | Chat, streaming, tools, structured output |
| Google | `gemini/gemini-1.5-pro` | Chat, streaming, tools, structured output |

#### 5.1.2 Extensibility

Any LiteLLM-supported provider works automatically:
- Azure: `azure/deployment-name`
- Bedrock: `bedrock/anthropic.claude-3-sonnet`
- Ollama: `ollama/llama3`
- 100+ more via LiteLLM

### 5.2 Response Types

```python
from pydantic import BaseModel
from typing import Any, Optional

class LLMResponse(BaseModel):
    """Standard response from completion calls."""
    content: str
    model: str
    usage: dict  # {prompt_tokens, completion_tokens, total_tokens}
    cost: Optional[float] = None  # In USD, from LiteLLM
    latency_ms: float
    raw_response: Any = None  # Original LiteLLM response
    reasoning_content: Optional[str] = None  # Chain-of-thought for reasoning models
    reasoning_blocks: Optional[list[dict]] = None  # Provider-specific reasoning blocks

class ToolCall(BaseModel):
    """Represents a tool/function call from the model."""
    id: str
    name: str
    arguments: dict

class ToolResponse(LLMResponse):
    """Response that includes tool calls."""
    tool_calls: list[ToolCall] = []
```

#### LLMResponse Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `content` | `str` | The text content of the response. Empty string if no text. |
| `model` | `str` | Model identifier that generated the response. |
| `usage` | `dict[str, int]` | Token counts: `prompt_tokens`, `completion_tokens`, `total_tokens`. |
| `cost` | `float \| None` | Estimated USD cost from LiteLLM. `None` if unavailable. |
| `latency_ms` | `float` | Request latency in milliseconds. |
| `raw_response` | `Any` | Original LiteLLM response for advanced use cases. |
| `reasoning_content` | `str \| None` | Model's reasoning/thinking text (reasoning models only). |
| `reasoning_blocks` | `list[dict] \| None` | Provider-specific reasoning blocks (e.g., Anthropic thinking_blocks). |

#### ToolCall Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Unique identifier for this tool call. Used to match results. |
| `name` | `str` | Name of the tool/function to call. |
| `arguments` | `dict[str, Any]` | Parsed arguments as a dictionary. |

#### ToolResponse Field Reference

Inherits all fields from `LLMResponse` plus:

| Field | Type | Description |
|-------|------|-------------|
| `tool_calls` | `list[ToolCall]` | List of tool calls requested by the model. Empty if none. |

### 5.3 Tool Definition

Tools are defined as Pydantic models:

```python
from pydantic import BaseModel, Field

class GetWeather(BaseModel):
    """Get current weather for a location."""
    location: str = Field(description="City and state, e.g., San Francisco, CA")
    unit: str = Field(default="fahrenheit", description="Temperature unit")
```

The client converts Pydantic models to OpenAI tool format internally.

### 5.4 Streaming (Text Only)

Streaming is intentionally simple in v1.0:

```python
# Returns Iterator[str] or AsyncIterator[str]
for chunk in client.stream(model="openai/gpt-4o", messages=[...]):
    print(chunk, end="", flush=True)
```

**Not supported in streaming:**
- Tool calls
- Structured output
- These require non-streaming methods

### 5.5 Reasoning Models

The client supports reasoning models that expose chain-of-thought via the `reasoning_effort` parameter.

#### Supported Models

| Provider | Models | Notes |
|----------|--------|-------|
| OpenAI | `o1`, `o1-mini`, `o3-mini` | Full reasoning support |
| Anthropic | Claude 3.7+ (Sonnet/Opus) | Via `thinking_blocks` |
| Google | Gemini 2.5+ | Extended thinking |

#### reasoning_effort Parameter

| Value | Description | Use Case |
|-------|-------------|----------|
| `"low"` | Quick reasoning, minimal depth | Simple queries, fast responses |
| `"medium"` | Balanced reasoning | General problem-solving |
| `"high"` | Deep reasoning, thorough analysis | Complex math, code review |

**Example:**
```python
response = client.complete(
    model="openai/o3-mini",
    messages=[{"role": "user", "content": "Solve: 2x + 5 = 13"}],
    reasoning_effort="medium"
)

print(response.content)           # The answer
print(response.reasoning_content) # The thinking process
```

Works with all methods: `complete()`, `complete_structured()`, `complete_with_tools()`.

**Note:** LiteLLM maps `reasoning_effort` to provider-specific parameters automatically. If passed to a non-reasoning model, behavior varies by provider (may be ignored or raise an error).

### 5.6 Retry Behavior

The client has **two independent retry systems** that work together:

| Type | Library | Triggers On | Parameter | Default |
|------|---------|-------------|-----------|---------|
| **API Retries** | LiteLLM | 429, 408, 503, 500 errors | `num_retries` | 3 |
| **Validation Retries** | Instructor | Pydantic validation failures | `max_retries` | 3 |

**LiteLLM API Retries** (automatic):
- Retries on: `429 (RateLimit)`, `408 (Timeout)`, `503 (ServiceUnavailable)`, `500 (InternalError)`
- Does NOT retry on: `400 (BadRequest)`, `401 (Auth)`, `ContentPolicyViolation`
- Uses exponential backoff with jitter (via Tenacity)
- Configurable via `num_retries` parameter

**Instructor Validation Retries** (configurable):
- Retries when Pydantic validation fails
- Sends validation error back to model for correction
- Configured via `max_retries` parameter
- Each retry is a new API call (costs tokens)

**Important:** These are separate systems. A request might succeed at the API level but fail validation, triggering Instructor retries. Or it might fail at the API level (rate limit) and be retried by LiteLLM before even reaching Instructor.

### 5.7 Fallback Support

LiteLLM supports automatic fallbacks when a model fails:

```python
response = client.complete(
    model="openai/gpt-4o",
    messages=[...],
    fallbacks=["anthropic/claude-3-5-sonnet-latest", "gemini/gemini-1.5-pro"]
)
```

The client will try models in order until one succeeds. Fallbacks are triggered by:
- Rate limit errors (429)
- Service unavailable (503)
- Timeout errors

**Cooldown:** Failed models enter a 60-second cooldown before being retried.

---

## 6. API Design

### 6.1 Client Initialization

```python
from rawagents import LLM, AsyncLLM, LLMConfig

# Minimal - uses environment variables
client = LLM()

# With configuration
config = LLMConfig(
    model="openai/gpt-4o",
    retries=3,                           # LiteLLM API retries
    structured_validation_retries=3,     # Instructor validation retries
    timeout=60,
    fallbacks=["anthropic/claude-3-5-sonnet-latest"],  # Fallback models
)
client = LLM(config=config)

# Async client
async_client = AsyncLLM(config=config)
```

### 6.2 Basic Completion

```python
# Sync
response = client.complete(
    model="openai/gpt-4o",
    messages=[
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello!"}
    ],
    temperature=0.7,
    max_tokens=1000,
    metadata={"trace_id": "abc-123"}  # For logging
)

print(response.content)        # "Hello! How can I help?"
print(response.cost)           # 0.0023
print(response.usage)          # {"prompt_tokens": 10, ...}
print(response.latency_ms)     # 234.5

# Async
response = await async_client.complete(...)
```

### 6.3 Structured Output

```python
from pydantic import BaseModel

class Person(BaseModel):
    name: str
    age: int
    occupation: str

# Sync - returns Person instance directly
person = client.complete_structured(
    model="anthropic/claude-3-5-sonnet-latest",
    messages=[{"role": "user", "content": "John is a 30 year old engineer."}],
    response_model=Person,
    max_retries=3  # Retry on validation failure
)

print(person.name)       # "John"
print(person.age)        # 30
print(person.occupation) # "engineer"

# Async
person = await async_client.complete_structured(...)
```

### 6.3.1 Structured Output with Metadata

When you need access to cost/usage data alongside structured output:

```python
# Returns tuple of (parsed_model, LLMResponse)
person, metadata = client.complete_structured(
    model="anthropic/claude-3-5-sonnet-latest",
    messages=[{"role": "user", "content": "John is a 30 year old engineer."}],
    response_model=Person,
    include_metadata=True  # Request metadata
)

print(person.name)           # "John"
print(metadata.cost)         # 0.0023
print(metadata.usage)        # {"prompt_tokens": 15, ...}
print(metadata.latency_ms)   # 342.1
```

### 6.4 Tool Calling

**Important:** `complete_with_tools()` returns tool call *requests* from the model but does **NOT** execute them. The caller is responsible for:
1. Executing the requested tools
2. Formatting results as tool messages
3. Calling the client again to continue the conversation

This design enables custom tool execution strategies (async, batched, with safety checks, etc.) and keeps the client focused on LLM communication. Tool orchestration belongs in an Agent component.

```python
from pydantic import BaseModel, Field

class GetWeather(BaseModel):
    """Get current weather for a location."""
    location: str = Field(description="City, State")

class SearchWeb(BaseModel):
    """Search the web."""
    query: str

# Step 1: Call with tools - model suggests which tools to use
response = client.complete_with_tools(
    model="openai/gpt-4o",
    messages=[{"role": "user", "content": "What's the weather in NYC?"}],
    tools=[GetWeather, SearchWeb],
    tool_choice="auto"  # or "required", "none"
)

# Step 2: Check for tool calls (client does NOT execute these)
if response.tool_calls:
    for tool_call in response.tool_calls:
        print(f"Tool: {tool_call.name}")       # "GetWeather"
        print(f"Args: {tool_call.arguments}")  # {"location": "NYC"}

        # Step 3: YOU execute the tool (this is YOUR responsibility)
        result = your_tool_executor(tool_call.name, tool_call.arguments)

        # Step 4: Continue conversation with tool result
        messages.append({"role": "assistant", "tool_calls": [...]})
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": json.dumps(result)
        })

        # Step 5: Call again for final response
        final_response = client.complete(model="openai/gpt-4o", messages=messages)
```

**Why not auto-execute?** Auto-execution requires:
- Tool registry/dispatch logic
- Error handling strategy
- Permission/safety checks
- State management
- Conversation memory

These are Agent concerns, not LLM client concerns.

### 6.5 Streaming (Text Only)

```python
# Sync - returns Iterator[str]
for chunk in client.stream(
    model="openai/gpt-4o",
    messages=[{"role": "user", "content": "Write a poem."}]
):
    print(chunk, end="", flush=True)

# Async - returns AsyncIterator[str]
async for chunk in async_client.stream(...):
    print(chunk, end="", flush=True)
```

---

## 7. Project Structure & Packaging

### 7.1 Monolithic Library Structure

```
ai-components/
├── README.md                    # Quick start + links to docs
├── LICENSE
├── pyproject.toml               # Single package definition
├── docs/
│   ├── index.md                 # Overview
│   ├── quickstart.md            # 5-minute getting started
│   │── components/
│   │   └── llm-client.md        # Deep dive
│   │── examples/
│       └── llm-client/
│           ├── 01_basic_completion.py
│           ├── 02_structured_output.py
│           ├── 03_tool_calling.py
│           ├── 04_async_parallel.py
│           └── 05_streaming.py
├── src/
│   └── rawagents/
│       ├── __init__.py          # Re-export main classes
│       ├── llm_client/
│       │   ├── __init__.py      # Public API
│       │   ├── client.py        # LLMClient
│       │   ├── async_client.py  # AsyncLLMClient
│       │   ├── types.py         # LLMResponse, ToolCall, etc.
│       │   ├── config.py        # LLMConfig
│       │   ├── tools.py         # Tool schema conversion
│       │   └── exceptions.py    # Custom exceptions
│       └── _shared/             # Internal utilities (future)
│           └── __init__.py
└── tests/
    └── llm_client/
        ├── test_client.py
        ├── test_async_client.py
        ├── test_structured.py
        ├── test_tools.py
        └── conftest.py
```

### 7.2 Top-Level Exports

```python
# src/rawagents/__init__.py
"""AI Components - Reusable building blocks for AI systems."""

from rawagents.llm import (
    LLM,
    AsyncLLM,
    LLMConfig,
    LLMResponse,
    ToolCall,
    ToolResponse,
)

__version__ = "0.1.0"

__all__ = [
    "LLMClient",
    "AsyncLLMClient",
    "LLMConfig",
    "LLMResponse",
    "ToolCall",
    "ToolResponse",
]
```

This enables clean imports:
```python
from rawagents import LLM
```

### 7.3 pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "ai-components"
version = "0.1.0"
description = "Reusable components for building AI systems"
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}
authors = [
    {name = "Your Name", email = "you@example.com"}
]
keywords = ["llm", "ai", "openai", "anthropic", "agents", "pydantic"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]

dependencies = [
    "litellm>=1.50.0,<2.0.0",
    "instructor>=1.5.0,<2.0.0",
    "pydantic>=2.0.0,<3.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-mock>=3.10.0",
    "mypy>=1.0.0",
    "ruff>=0.1.0",
]

[project.urls]
Homepage = "https://github.com/yourusername/ai-components"
Documentation = "https://github.com/yourusername/ai-components#readme"
Repository = "https://github.com/yourusername/ai-components"

[tool.hatch.build.targets.wheel]
packages = ["src/rawagents"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.mypy]
python_version = "3.10"
strict = true

[tool.ruff]
line-length = 88
target-version = "py310"
```

### 7.4 Installation Methods

```bash
# Install latest from main branch
pip install git+https://github.com/yourusername/ai-components.git

# Install specific version/tag
pip install git+https://github.com/yourusername/ai-components.git@v0.1.0

# Install specific commit (for reproducibility)
pip install git+https://github.com/yourusername/ai-components.git@abc123

# For development (editable install)
git clone https://github.com/yourusername/ai-components.git
cd ai-components
pip install -e ".[dev]"
```

In requirements.txt:
```
ai-components @ git+https://github.com/yourusername/ai-components.git@v0.1.0
```

### 7.5 README Quick Start

The README should enable users to start in 30 seconds:

```markdown
# AI Components

Reusable components for building AI systems.

## Install

```bash
pip install git+https://github.com/yourusername/ai-components.git
```

## Quick Start

```python
from rawagents import LLM
from pydantic import BaseModel

# Set your API key
# export OPENAI_API_KEY=sk-...

# Simple completion
client = LLM()
response = client.complete(
    model="openai/gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.content)

# Structured output
class Person(BaseModel):
    name: str
    age: int

person = client.complete_structured(
    model="openai/gpt-4o-mini",
    messages=[{"role": "user", "content": "John is 25 years old"}],
    response_model=Person
)
print(f"{person.name} is {person.age}")
```

## Examples

See [examples/](examples/) for more usage patterns.
```

---

## 8. Implementation Approach

### 8.1 Phased Implementation

#### Phase 1: Core Foundation (Week 1)

**Goal**: Basic working client with sync/async support

**Tasks**:
1. Set up project structure with pyproject.toml
2. Implement `LLMConfig` and `LLMResponse` types
3. Implement `LLMClient.complete()`
4. Implement `AsyncLLMClient.complete()`
5. Basic error handling
6. Unit tests for core functionality

**Deliverable**: Client can make completion calls to OpenAI, Anthropic, Google

#### Phase 2: Structured Output (Week 1-2)

**Goal**: Pydantic model extraction with Instructor

**Tasks**:
1. Integrate `instructor.from_litellm()`
2. Implement `complete_structured()` for both clients
3. Handle `create_with_completion()` to get cost data
4. Validation retry logic
5. Tests for structured output

**Deliverable**: Client can extract typed Pydantic models from responses

#### Phase 3: Tool Calling (Week 2)

**Goal**: Function/tool calling support

**Tasks**:
1. Implement Pydantic model → tool schema conversion
2. Implement `complete_with_tools()` for both clients
3. Implement `complete_with_tools_structured()`
4. Parse tool call responses
5. Tests for tool calling

**Deliverable**: Client can use Pydantic models as tool definitions

#### Phase 4: Streaming (Week 2-3)

**Goal**: Text streaming support

**Tasks**:
1. Implement `stream()` returning `Iterator[str]`
2. Implement async `stream()` returning `AsyncIterator[str]`
3. Handle stream completion and errors
4. Tests for streaming

**Deliverable**: Client can stream text responses

#### Phase 5: Polish & Documentation (Week 3-4)

**Goal**: Release-ready component

**Tasks**:
1. Write comprehensive README
2. Create example files for each feature
3. Docstrings for all public methods
4. Type hints verification with mypy
5. Integration tests with real APIs
6. Performance baseline

**Deliverable**: v0.1.0 release

### 8.2 Core Implementation Pattern

```python
# src/rawagents/llm_client/client.py

from litellm import completion
import instructor
from pydantic import BaseModel
from typing import Type, TypeVar, Iterator, Optional, List, Union, Tuple, overload
import time

from .config import LLMConfig
from .types import LLMResponse, ToolCall, ToolResponse
from .tools import pydantic_to_tool_schema

T = TypeVar('T', bound=BaseModel)

class LLM:
    """Synchronous universal LLM client.

    This client handles LLM communication only. It does NOT:
    - Execute tool calls (returns them for caller to handle)
    - Manage conversation state (caller provides full message history)
    - Run agent loops (that's a separate component)
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        # Instructor client for structured output - USE from_litellm, NOT from_provider
        self._instructor = instructor.from_litellm(completion)

    def complete(
        self,
        messages: List[dict],
        model: Optional[str] = None,
        *,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        metadata: Optional[dict] = None,
        fallbacks: Optional[List[str]] = None,
    ) -> LLMResponse:
        """Basic text completion."""
        model = model or self.config.model
        fallbacks = fallbacks or self.config.fallbacks

        start = time.perf_counter()
        response = completion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            metadata=metadata,
            num_retries=self.config.retries,
            fallbacks=fallbacks,
        )
        latency_ms = (time.perf_counter() - start) * 1000

        return LLMResponse(
            content=response.choices[0].message.content or "",
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            cost=response._hidden_params.get("response_cost"),
            latency_ms=latency_ms,
            raw_response=response,
        )

    @overload
    def complete_structured(
        self,
        messages: List[dict],
        response_model: Type[T],
        model: Optional[str] = None,
        *,
        max_retries: Optional[int] = None,
        temperature: float = 0.7,
        include_metadata: Literal[False] = False,
    ) -> T: ...

    @overload
    def complete_structured(
        self,
        messages: List[dict],
        response_model: Type[T],
        model: Optional[str] = None,
        *,
        max_retries: Optional[int] = None,
        temperature: float = 0.7,
        include_metadata: Literal[True],
    ) -> Tuple[T, LLMResponse]: ...

    def complete_structured(
        self,
        messages: List[dict],
        response_model: Type[T],
        model: Optional[str] = None,
        *,
        max_retries: Optional[int] = None,
        temperature: float = 0.7,
        include_metadata: bool = False,
    ) -> Union[T, Tuple[T, LLMResponse]]:
        """Completion with Pydantic structured output.

        Args:
            include_metadata: If True, returns (model, LLMResponse) tuple
                              for access to cost/usage data.
        """
        model = model or self.config.model
        max_retries = max_retries or self.config.structured_validation_retries

        if include_metadata:
            start = time.perf_counter()
            result, raw = self._instructor.chat.completions.create_with_completion(
                model=model,
                messages=messages,
                response_model=response_model,
                max_retries=max_retries,
                temperature=temperature,
            )
            latency_ms = (time.perf_counter() - start) * 1000

            metadata = LLMResponse(
                content=raw.choices[0].message.content or "",
                model=raw.model,
                usage={
                    "prompt_tokens": raw.usage.prompt_tokens,
                    "completion_tokens": raw.usage.completion_tokens,
                    "total_tokens": raw.usage.total_tokens,
                },
                cost=raw._hidden_params.get("response_cost"),
                latency_ms=latency_ms,
                raw_response=raw,
            )
            return result, metadata
        else:
            return self._instructor.chat.completions.create(
                model=model,
                messages=messages,
                response_model=response_model,
                max_retries=max_retries,
                temperature=temperature,
            )

    def complete_with_tools(
        self,
        messages: List[dict],
        tools: List[Type[BaseModel]],
        model: Optional[str] = None,
        *,
        tool_choice: str = "auto",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> ToolResponse:
        """Completion with tool calling.

        IMPORTANT: This method returns tool call requests but does NOT execute them.
        The caller is responsible for executing tools and continuing the conversation.
        """
        model = model or self.config.model

        # Convert Pydantic models to OpenAI tool format
        tool_schemas = [pydantic_to_tool_schema(t) for t in tools]

        start = time.perf_counter()
        response = completion(
            model=model,
            messages=messages,
            tools=tool_schemas,
            tool_choice=tool_choice,
            temperature=temperature,
            max_tokens=max_tokens,
            num_retries=self.config.retries,
        )
        latency_ms = (time.perf_counter() - start) * 1000

        # Parse tool calls from response
        tool_calls = []
        if response.choices[0].message.tool_calls:
            for tc in response.choices[0].message.tool_calls:
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=json.loads(tc.function.arguments),
                ))

        return ToolResponse(
            content=response.choices[0].message.content or "",
            model=response.model,
            usage={...},
            cost=response._hidden_params.get("response_cost"),
            latency_ms=latency_ms,
            raw_response=response,
            tool_calls=tool_calls,
        )

    def stream(
        self,
        messages: List[dict],
        model: Optional[str] = None,
        *,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Iterator[str]:
        """Stream text completion. Returns Iterator[str] of text chunks.

        NOTE: Streaming does NOT support tools or structured output in v1.0.
        """
        model = model or self.config.model

        response = completion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
```

---

## 9. Dependencies & Integration

### 9.1 Required Dependencies

```toml
dependencies = [
    "litellm>=1.50.0,<2.0.0",
    "instructor>=1.5.0,<2.0.0",
    "pydantic>=2.0.0,<3.0.0",
]
```

**Version Pinning Rationale**:
- Major version pins prevent breaking changes
- Minor version floor ensures required features
- Both LiteLLM and Instructor are actively developed

### 9.2 Environment Variables

```bash
# At least one provider required
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...

# Optional
LITELLM_LOG=DEBUG  # Enable debug logging
```

---

## 10. Testing Strategy

### 10.1 Unit Tests (Mocked)

```python
# tests/llm/test_client.py
import pytest
from unittest.mock import patch, MagicMock

def test_complete_returns_response():
    with patch("litellm.completion") as mock:
        mock.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Hello!"))],
            model="gpt-4o",
            usage=MagicMock(prompt_tokens=5, completion_tokens=10, total_tokens=15),
            _hidden_params={"response_cost": 0.001}
        )
        
        client = LLM()
        response = client.complete(
            messages=[{"role": "user", "content": "Hi"}]
        )

        assert response.content == "Hello!"
        assert response.cost == 0.001
```

### 10.2 Integration Tests (Real APIs)

```python
# tests/llm/test_integration.py
import pytest
import os

@pytest.mark.integration
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="No API key")
def test_openai_real_completion():
    client = LLM(model="openai/gpt-4o-mini")
    response = client.complete(
        messages=[{"role": "user", "content": "Say 'test'"}],
        max_tokens=10
    )
    assert response.content is not None
    assert response.cost is not None
```

### 10.3 Coverage Targets

| Component | Target |
|-----------|--------|
| Client methods | 90%+ |
| Response types | 95%+ |
| Tool conversion | 95%+ |
| Error handling | 90%+ |

---

## 11. Risks & Mitigations

### 11.1 Technical Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| LiteLLM breaking changes | High | Medium | Pin versions, monitor releases, integration tests in CI |
| Instructor breaking changes | High | Medium | Pin versions, test upgrades before adopting |
| Provider API changes | Medium | High | LiteLLM handles this - that's why we use it |
| Instructor + LiteLLM incompatibility | Medium | Low | Use `from_litellm()` only, avoid `from_provider()` |
| Azure cost tracking inaccuracy | Medium | High | Document `base_model` requirement, validate in tests |
| Streaming + tools bugs | Medium | Medium | Keep streaming text-only in v1.0 (validated decision) |
| `from_provider()` instability | Medium | Medium | Use `from_litellm()` pattern exclusively |

### 11.2 Known Issues from Research

1. **`instructor.from_provider("litellm/...")`** - Had issues until recently ([GitHub #1710](https://github.com/567-labs/instructor/issues/1710)). Use `instructor.from_litellm(completion)` instead.

2. **Claude streaming + tool calls** - Had bugs in LiteLLM < v1.31.6 ([GitHub #2435](https://github.com/BerriAI/litellm/issues/2435)). Now fixed, but validates our decision to keep streaming separate from tools.

3. **Azure cost tracking** - Returns generic model names causing wrong cost calculation. Requires `base_model` configuration.

4. **Bedrock parameter issues** - May need `litellm.drop_params=True` for unsupported parameters.

### 11.3 Scope Creep

**Mitigation**:
- Strict adherence to non-goals
- Streaming limited to text-only in v1.0
- Tool execution is explicitly out of scope (agent territory)
- Feature requests go to backlog

---

## 12. Success Criteria

### 12.1 Functional Criteria

- [ ] Make completion calls to OpenAI, Anthropic, Google
- [ ] Extract structured output with Pydantic models
- [ ] Stream text responses (sync and async)
- [ ] Define tools via Pydantic models
- [ ] Handle tool calls in responses
- [ ] Retry on transient failures
- [ ] Track cost per call
- [ ] Support both sync and async usage

### 12.2 Quality Criteria

- [ ] 85%+ test coverage
- [ ] All public methods have docstrings
- [ ] Type hints on all public interfaces
- [ ] No type errors with `mypy --strict`
- [ ] README with 30-second quick start
- [ ] Working examples for each feature

### 12.3 Usability Criteria

- [ ] Install works with single pip command
- [ ] Works immediately with env vars set
- [ ] Examples are copy-paste runnable
- [ ] Error messages are helpful

---

## 13. Timeline & Milestones

| Week | Milestone | Deliverables |
|------|-----------|--------------|
| 1 | Core + Structured | Basic clients, complete(), complete_structured() |
| 2 | Tools + Streaming | complete_with_tools(), stream() |
| 3 | Polish | Documentation, examples, testing |
| 4 | Release | v0.1.0, integration tests, README |

**Total Duration**: 4 weeks

---

## 14. Appendix

### 14.1 LiteLLM Model Formats

| Provider | Format | Example |
|----------|--------|---------|
| OpenAI | `openai/<model>` | `openai/gpt-4o` |
| Anthropic | `anthropic/<model>` | `anthropic/claude-3-5-sonnet-latest` |
| Google | `gemini/<model>` | `gemini/gemini-1.5-pro` |
| Azure | `azure/<deployment>` | `azure/my-gpt4-deployment` |
| Bedrock | `bedrock/<model>` | `bedrock/anthropic.claude-3-sonnet` |
| Ollama | `ollama/<model>` | `ollama/llama3` |

### 14.2 Instructor Integration Pattern

```python
# Sync client
from litellm import completion
import instructor

client = instructor.from_litellm(completion)
result = client.chat.completions.create(
    model="openai/gpt-4o",
    messages=[...],
    response_model=MyModel,
)

# Async client
from litellm import acompletion
import instructor

client = instructor.from_litellm(acompletion)
result = await client.chat.completions.create(
    model="openai/gpt-4o",
    messages=[...],
    response_model=MyModel,
)

# Get cost with structured output
result, raw = client.chat.completions.create_with_completion(...)
cost = raw._hidden_params.get("response_cost")
```

### 14.3 Exception Handling

LiteLLM maps provider exceptions to OpenAI-style:

```python
from litellm.exceptions import (
    RateLimitError,           # 429
    AuthenticationError,       # 401
    BadRequestError,           # 400
    Timeout,                   # Timeout
    APIConnectionError,        # Network issues
    ServiceUnavailableError,   # 503
    ContentPolicyViolationError,
    ContextWindowExceededError,
)
```

### 14.4 References

- [LiteLLM Documentation](https://docs.litellm.ai/)
- [LiteLLM + Instructor Tutorial](https://docs.litellm.ai/docs/tutorials/instructor)
- [Instructor Documentation](https://python.useinstructor.com/)
- [Instructor LiteLLM Integration](https://python.useinstructor.com/integrations/litellm/)
- [Pydantic Documentation](https://docs.pydantic.dev/)

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Nov 2025 | Tawab Safi | Initial draft |
| 2.0 | Nov 2025 | Tawab Safi | Updated based on research: Chat Completions API, monolithic packaging, simplified streaming, sync/async clients |
| 3.0 | Nov 2025 | Tawab Safi | Comprehensive update: clarified tool execution design (client returns, doesn't execute), added `include_metadata` for structured output, documented `from_litellm()` vs `from_provider()` issues, added fallback support, Azure cost tracking caveats, expanded retry documentation, added known issues from research |

---

## 15. Component Relationship Diagram

This diagram shows how the Universal LLM Client fits into the larger AI components ecosystem:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Your Application                                 │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Agent / Tool Orchestrator                             │
│                    (FUTURE COMPONENT)                                    │
│                                                                          │
│  Responsibilities:                                                       │
│  • Tool registry & dispatch                                              │
│  • Agent loop (call LLM → execute tools → repeat)                        │
│  • Conversation memory                                                   │
│  • Permission/safety checks                                              │
│  • Error handling & recovery                                             │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Universal LLM Client                                  │
│                    (THIS COMPONENT)                                      │
│                                                                          │
│  Responsibilities:                                                       │
│  • Send messages to LLMs                                                 │
│  • Return responses (text, structured, tool calls)                       │
│  • Handle retries & fallbacks                                            │
│  • Track cost & usage                                                    │
│  • Stream text responses                                                 │
│                                                                          │
│  Does NOT:                                                               │
│  • Execute tool calls                                                    │
│  • Manage conversation state                                             │
│  • Run agent loops                                                       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
        ┌─────────────────────┐         ┌─────────────────────┐
        │     Instructor      │         │      LiteLLM        │
        │  (structured out)   │◄────────│  (provider API)     │
        └─────────────────────┘         └─────────────────────┘
                                                │
                        ┌───────────────────────┼───────────────────────┐
                        ▼                       ▼                       ▼
                 ┌──────────┐            ┌──────────┐            ┌──────────┐
                 │  OpenAI  │            │ Anthropic│            │  Google  │
                 └──────────┘            └──────────┘            └──────────┘
```

**Key Insight:** The Universal LLM Client is intentionally "dumb" about tools. It tells you what the model wants to call, but executing those tools is your responsibility (or the responsibility of an Agent component built on top).

---

*This PRD is a living document. Update as requirements evolve during implementation.*


