# Product Requirements Document (PRD)
# AI Components Library - Conversation Component

**Version:** 2.0
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
7. [Project Structure](#7-project-structure)
8. [Implementation Approach](#8-implementation-approach)
9. [Risks & Mitigations](#9-risks--mitigations)
10. [Success Criteria](#10-success-criteria)
11. [Timeline](#11-timeline)
12. [Component Relationship Diagram](#12-component-relationship-diagram)

---

## 1. Executive Summary

### 1.1 What We're Building

The **Conversation Component** (`rawagents.state`) is a "smart container" for managing agent memory and state. It serves as the **operating system for context**, managing the timeline of messages, tool calls, and structured outputs between a user and an LLM.

Unlike a simple list of dictionaries, this component provides:
- **Canonical Data Model**: Strongly-typed Pydantic models for `Message` and `ToolCall` with structured metadata for optimization metrics.
- **Branching Support**: A lightweight `fork()` mechanism to support tree-of-thought reasoning without complex graph data structures.
- **State Checkpointing**: Explicit `snapshot()` and `load()` capabilities for long-running workflows and human-in-the-loop systems.
- **Context Strategies**: Pluggable logic for determining *which* messages to send to the LLM (e.g., `FullHistory`, `SlidingWindow`, `SummarizedHistory`).
- **Storage Agnosticism**: A repository pattern that allows history to be stored in-memory (default), Redis, Postgres, or file-based systems.

### 1.2 Key Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Structure** | Forking (Deep Copy) | Simpler than a linked-list Tree. Enables isolated exploration paths ("Tree of Thoughts") without complex traversal APIs. |
| **State Mgmt** | Explicit Snapshots | Enables "Undo", "Pause/Resume", and "Time Travel" debugging for agents. |
| **Data Model** | Pydantic Models | Avoids "dict soup" and schema drift. Ensures type safety for complex tool/multimodal interactions. |
| **Metrics** | Structured Metadata | Cost, latency, and model info are first-class citizens to enable future "Agent Optimization". |
| **Storage** | Repository Pattern | Decouples logic from persistence. Enables scaling from script-kiddie bots to production agents. |

### 1.3 Core Principle

**"State before Execution"**: The Conversation component manages *state* (what happened). The LLM manages *execution* (what to do next). They are distinct but interoperable.

---

## 2. Background & Motivation

### 2.1 Problem Statement

Building agents currently involves reinventing the wheel for state management:
1. **Fragile Dictionaries**: Passing `[{"role": "user", "content": "..."}]` around leads to runtime errors.
2. **Linearity Constraints**: Standard lists make it hard to implement "Tree of Thoughts" or branching logic.
3. **Loss of State**: If a script crashes, the conversation is lost. Resuming requires complex custom logic.
4. **Optimization Blindness**: Without tracking per-turn cost/latency in the history, it's impossible to programmatically optimize the agent later.

### 2.2 Solution Strategy

We will implement a **Message-Oriented Middleware** for agents. It acts as the translation layer between "What the agent remembers" (canonical history) and "What the provider sees" (formatted API payload), while adding branching and checkpointing capabilities.

---

## 3. Goals & Non-Goals

### 3.1 Goals

**G1: Canonical Message Model with Metrics**
- Unified Pydantic representation for System, User, Assistant, Tool messages.
- **Structured Metadata**: Track `cost`, `latency`, `model_name`, and `finish_reason` per message.

**G2: Branching & Merging**
- `fork()`: Create an independent copy of the conversation for exploration.
- `merge()`: Combine a branch back into the main trunk.

**G3: Checkpointing (Time Travel)**
- `snapshot()`: Export full state to a dictionary/JSON.
- `restore()`: Rebuild conversation from a snapshot.
- `truncate()`: Delete messages after a specific point (Undo).

**G4: Plug-and-Play Storage**
- Abstract `BaseStorage` interface with default `InMemoryStorage`.
- Designed for extension to Redis/SQL.

**G5: Context Strategies**
- Logic to control what context is sent to the LLM (Windowing, Filtering).

### 3.2 Non-Goals

**NG1: Active Summarization**
- The component will NOT automatically trigger LLM calls to summarize itself.
- Summarization is an *action* performed by the Agent, not a side-effect of storage.

**NG2: Complex Graph Traversal**
- We do not maintain parent/child links between messages. Branching is handled via separate Conversation objects (Forking).

**NG3: Agent Orchestration**
- The Conversation does not "run" the loop. It just holds the state.

---

## 4. Technical Architecture

### 4.1 High-Level Design

```
┌───────────────────────────────────────────────────────────────────┐
│                         Your Agent Code                           │
│                                                                   │
│  # Branching Example                                              │
│  main_conv = Conversation()                                       │
│  branch_a = main_conv.fork()                                      │
│  branch_a.add_user("Try Plan A")                                  │
│  if success: main_conv.merge(branch_a)                            │
└───────────────────────────────────────────────────────────────────┘
                │                                  │
                ▼                                  ▼
┌──────────────────────────────┐   ┌────────────────────────────────┐
│    Conversation Controller   │   │             LLM                │
│  (Manages Forks & Snaps)     │   │      (Executes Requests)       │
│                              │   │                                │
└──────────────────────────────┘   └────────────────────────────────┘
                │
                ▼
┌──────────────────────────────┐
│        Storage Layer         │
│  [In-Memory] [Redis] [SQL]   │
└──────────────────────────────┘
```

### 4.2 The Data Model (Canonical)

```python
class MessageMetadata(BaseModel):
    cost: float | None = None
    latency_ms: float | None = None
    finish_reason: str | None = None
    model: str | None = None
    usage: dict[str, int] | None = None
    reasoning_content: str | None = None
    reasoning_blocks: list[dict[str, Any]] | None = None
    custom: dict[str, Any] = {}

### MessageMetadata Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `cost` | `float \| None` | USD cost of the API call that generated this message. Populated from LiteLLM's cost tracking. |
| `latency_ms` | `float \| None` | Response time in milliseconds from request to full response. |
| `finish_reason` | `str \| None` | Why the model stopped generating. Common values: `"stop"` (natural end), `"tool_calls"` (requesting tool use), `"length"` (max tokens hit). |
| `model` | `str \| None` | The model identifier that generated the response (e.g., `"gpt-4o"`, `"claude-3-5-sonnet-latest"`). |
| `usage` | `dict[str, int] \| None` | Token usage statistics with keys: `prompt_tokens`, `completion_tokens`, `total_tokens`. |
| `reasoning_content` | `str \| None` | The model's reasoning/thinking text for reasoning models (o1, o3, Claude 3.7+). `None` if not a reasoning model or reasoning not enabled. |
| `reasoning_blocks` | `list[dict] \| None` | Provider-specific reasoning blocks (e.g., Anthropic's `thinking_blocks`). `None` if not available. |
| `custom` | `dict[str, Any]` | Arbitrary user-defined metadata. Use for application-specific tracking (e.g., trace IDs, user context). |

**Example: Tracking costs in conversation**
```python
# After an LLM response, add with full metadata
conversation.add_assistant(
    content=response.content,
    metadata={
        "cost": response.cost,
        "latency_ms": response.latency_ms,
        "model": response.model,
        "usage": response.usage,
        "finish_reason": "stop",
    }
)

# Later: Calculate total conversation cost
total_cost = sum(
    msg.metadata.cost or 0
    for msg in conversation.get_all_messages()
    if msg.metadata.cost
)
```

```python
class ContentBlock(BaseModel):
    type: Literal["text", "image_url"]
    text: str | None = None
    image_url: str | None = None

class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict

class Message(BaseModel):
    id: str = Field(default_factory=uuid4)
    role: Literal["system", "user", "assistant", "tool"]
    content: str | list[ContentBlock]
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    metadata: MessageMetadata = Field(default_factory=MessageMetadata)
    created_at: datetime = Field(default_factory=utcnow)
```

---

## 5. Detailed Requirements

### 5.1 Core Conversation Operations

- **Initialization**: `Conversation(storage=..., strategy=...)`
- **Add Messages**:
  - `add_system(content: str) -> Message`
  - `add_user(content: str, images: list[str] | None = None) -> Message`
  - `add_assistant(content: str, tool_calls: list[ToolCall] | list[dict] | None = None, metadata: dict | MessageMetadata | None = None) -> Message`
  - `add_tool_result(tool_call_id: str, content: str, metadata: dict | MessageMetadata | None = None) -> Message`
- **Retrieval**:
  - `get_history() -> list[dict]`: Apply active strategy (e.g. sliding window) and return list of dicts for LLM.
  - `get_all_messages() -> list[Message]`: Return raw `Message` objects (no filtering). Use this when you need access to metadata, timestamps, or other fields not included in the LLM-formatted output.
- **Utility**:
  - `clear() -> None`: Remove all messages from the conversation.
  - `__len__() -> int`: Return the number of messages in the conversation.

#### Multimodal Support

The `add_user()` method supports multimodal input via the optional `images` parameter:

```python
# Add a user message with image URLs for vision models
conv.add_user(
    "What's in this image?",
    images=["https://example.com/image.png"]
)
```

When images are provided, the message content is automatically converted to a list of `ContentBlock` objects containing both text and image URL blocks.

### 5.2 Branching & Time Travel

- **`fork() -> Conversation`**:
  - Returns a new Conversation instance with a deep copy of the current history.
  - The new instance is independent (changes to it do not affect parent).
- **`merge(branch: Conversation) -> None`**:
  - Appends the *new* messages from the branch to the current conversation.
  - Only messages not already in this conversation are added (identified by unique ID).
- **`truncate(message_id: str) -> None`**:
  - Removes all messages *after* the specified ID (the message with the given ID is kept).
  - Used for "Undo" or "Retry" flows.
  - Raises `ValueError` if message_id is not found.

```python
# Example: Undo the last user message
msg = conv.add_user("Wrong question")
# ... later, want to undo
conv.truncate(previous_msg.id)  # Removes "Wrong question" and everything after
```

- **`clear() -> None`**:
  - Removes all messages from the conversation.
  - Useful for resetting state without creating a new Conversation instance.

### 5.3 Checkpointing

- **`snapshot() -> dict`**:
  - Serializes the full state (history + metadata) to a dictionary.
- **`load(snapshot: dict)`**:
  - Restores state from a snapshot.

### 5.4 Storage Interface (`BaseStorage`)

- **CRUD Operations**:
  - `save_message(message)`
  - `get_messages()`
  - `delete_after(message_id)` (Support for truncation)

### 5.5 Context Strategies

- **Strategy Interface**:
  - `select_messages(all_messages: list[Message], **kwargs) -> list[Message]`
  - **Note**: Strategies must be pure functions operating only on the list of messages. They must NOT accept the `Conversation` object or `Storage` backend.
- **Standard Implementations**:
  - `FullHistory`: Returns identity.
  - `SlidingWindow`: Returns `system_prompt + last_n_messages`.
- **Planned (Not Yet Implemented)**:
  - `TokenLimitedWindow`: Returns `system_prompt + messages_fitting_token_budget`.
  - `SummarizedHistory`: Summarizes older messages to fit token budget.

---

## 6. API Design

### 6.1 Basic Usage

```python
from rawagents.state import Conversation

conv = Conversation()
conv.add_system("You are a helpful assistant.")
conv.add_user("Hello")

# Get context for LLM (returns list[dict])
messages = conv.get_history()
```

### 6.2 Branching (Tree of Thoughts)

```python
# The user asks a complex question
conv.add_user("Solve P=NP")

# Create 3 independent thinking branches
branches = [conv.fork() for _ in range(3)]

# Explore each branch
for i, branch in enumerate(branches):
    branch.add_system(f"Attempt approach #{i}")
    # ... run agent loop on branch ...

# Pick the winner (e.g. branch 1)
conv.merge(branches[1])
```

### 6.3 Checkpointing (Pause/Resume)

```python
# Save state to DB
state_blob = conv.snapshot()
db.save(session_id, state_blob)

# --- Later ---

# Resume
conv = Conversation()
conv.load(state_blob)
```

### 6.4 Optimization Metrics

```python
# When adding an assistant response, track the cost
conv.add_assistant(
    content="Hello!",
    metadata={
        "cost": 0.002,
        "latency_ms": 450,
        "model": "gpt-4o"
    }
)
```

---

## 7. Project Structure

```text
src/rawagents/state/
├── __init__.py           # Exports
├── conversation.py       # Main Logic (Controller)
├── types.py              # Pydantic Models (Message, Metadata)
├── storage/
│   ├── __init__.py
│   ├── base.py           # Abstract BaseStorage
│   └── memory.py         # InMemoryStorage
└── strategies/
    ├── __init__.py
    ├── base.py           # Abstract ContextStrategy
    └── window.py         # SlidingWindowStrategy
```

---

## 8. Implementation Approach

### Phase 1: Data Models (Day 1)
- Implement `MessageMetadata` and `Message` in `types.py`.
- Ensure Pydantic validation works for all fields.

### Phase 2: Core Logic (Day 1-2)
- Implement `InMemoryStorage`.
- Implement `Conversation` add/get methods.
- Implement `fork()` and `truncate()` logic.

### Phase 3: Strategies (Day 3)
- Implement `SlidingWindow` strategy.

### Phase 4: Testing & Examples (Day 4)
- Unit tests for forking (ensure deep copy).
- Integration test with `LLM`.

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Forking Memory Usage** | Medium | Forking duplicates message objects. For 1000+ turn conversations, this is heavy. *Mitigation:* Recommend `fork()` for reasoning steps (short-term), not long history cloning. |
| **Schema Drift** | High | Internal Pydantic models act as the source of truth. |
| **Metadata Bloat** | Low | Keep metadata optional. Only store what is needed. |

---

## 10. Success Criteria

- [ ] **Branching**: `fork()` creates a truly independent copy (modifying child doesn't affect parent).
- [ ] **Metrics**: Can retrieve cost/latency stats from the conversation history.
- [ ] **Interoperability**: Output of `get_history()` works directly with `LLM`.
- [ ] **Time Travel**: `truncate()` successfully effectively "undos" the last N turns.

---

## 11. Timeline

- **Day 1**: Models, Storage, Core Logic
- **Day 2**: Branching, Checkpointing, Strategies
- **Day 3**: Integration & Docs

---

## 12. Component Relationship Diagram

```
┌──────────────┐       ┌───────────────────┐       ┌────────────────┐
│     LLM      │◄──────┤       Agent       ├──────►│  Conversation  │
│ (Stateless)  │       │     Runtime       │       │    (State)     │
└──────────────┘       └───────────────────┘       └───────┬────────┘
                                                           │
                             ┌─────────────────────────────▼─────┐
                             │           Features                │
                             │ • Forking (Deep Copy)             │
                             │ • Snapshots (Pause/Resume)        │
                             │ • Metrics (Cost/Latency)          │
                             └───────────────────────────────────┘
```
