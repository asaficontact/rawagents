# State Component (`rawagents.state`)

The state component is a **conversation and message manager** for agents -- the "operating system for context". It tracks the ordered timeline of messages, tool calls, and metadata exchanged between a user and an LLM, providing the structured history that drives agent loops.

It focuses on:

- canonical Pydantic models for all message types (`Message`, `ContentBlock`, `ToolCall`, `MessageMetadata`)
- a `Conversation` container with branching (`fork`/`merge`) and checkpointing (`snapshot`/`load`)
- pluggable context strategies (e.g., `SlidingWindow`) that filter what the LLM sees without deleting history
- storage-agnostic backends via the `BaseStorage` protocol

It deliberately does **not** call the LLM or execute tools -- those are handled by the `llm` and `tools` components respectively.

---

## Quick start

```python
from rawagents import Conversation

conv = Conversation()

conv.add_system("You are a helpful assistant.")
conv.add_user("What is the capital of France?")

messages = conv.get_history()  # OpenAI-compatible list[dict]
# Pass directly to client.complete(messages=messages)
```

See the full README in `src/rawagents/state/README.md` for advanced examples.

---

## Message Types

All messages use the `Message` Pydantic model with a `role` field (`"system"`, `"user"`, `"assistant"`, or `"tool"`). Each message gets an auto-generated UUID and UTC timestamp.

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Unique identifier (auto-generated UUID). |
| `role` | `Literal["system", "user", "assistant", "tool"]` | Message role. |
| `content` | `str \| list[ContentBlock]` | Text or multimodal content blocks. |
| `tool_calls` | `list[ToolCall] \| None` | Tool calls requested by the assistant. |
| `tool_call_id` | `str \| None` | ID of the tool call this result responds to (tool messages). |
| `metadata` | `MessageMetadata` | Cost, latency, model, token usage, and reasoning data. |
| `created_at` | `datetime` | UTC timestamp of creation. |

`MessageMetadata` tracks optimization metrics: `cost`, `latency_ms`, `finish_reason`, `model`, `usage`, `reasoning_content`, `reasoning_blocks`, and a `custom` dict for arbitrary data.

---

## `Conversation`

The `Conversation` class is the primary interface. It wraps a storage backend and a context strategy.

```python
from rawagents.state import Conversation, SlidingWindow, InMemoryStorage

conv = Conversation(
    storage=InMemoryStorage(),       # default
    strategy=SlidingWindow(window_size=10),  # default is FullHistory
)
```

### Adding messages

```python
conv.add_system("You are a helpful assistant.")
conv.add_user("Hello!")
conv.add_user("Describe this.", images=["https://example.com/img.png"])
conv.add_assistant("Sure!", metadata={"cost": 0.002, "model": "gpt-4o"})
conv.add_tool_result(tool_call_id="call_abc", content='{"temp": 72}')
```

### Retrieving history

| Method | Returns | Description |
|--------|---------|-------------|
| `get_history()` | `list[dict[str, Any]]` | Strategy-filtered messages as OpenAI-compatible dicts. |
| `get_all_messages()` | `list[Message]` | All raw `Message` objects, unfiltered. |

---

## Context Strategies

Strategies control which messages are sent to the LLM without deleting anything from storage.

| Strategy | Behaviour |
|----------|-----------|
| `FullHistory` (default) | Returns all messages unchanged. |
| `SlidingWindow(window_size=N)` | Keeps all system messages plus the last *N* non-system messages. |

Implement the `BaseStrategy` protocol (a single `select_messages` method) to create custom strategies such as token-budget or summarisation-based approaches.

---

## Branching and Checkpointing

```python
# Fork: create an independent copy for exploration
branch = conv.fork()
branch.add_user("Try approach A")
# Original conv is unchanged

# Merge: append new messages from a branch
conv.merge(branch)

# Truncate: undo messages after a given ID
conv.truncate(some_message.id)

# Snapshot / Load: serialise state to a dict (JSON-safe)
state = conv.snapshot()
new_conv = Conversation()
new_conv.load(state)
```

---

## Storage Backends

Storage follows the `BaseStorage` protocol with five methods: `save_message`, `get_messages`, `delete_after`, `clear`, and `fork`. The built-in `InMemoryStorage` keeps messages in a Python list and is suitable for single-process scripts and testing. For production persistence, implement the protocol over Redis, PostgreSQL, or any other backend.

---

## Integration with Other Components

The state component connects to the rest of RawAgents through shared types:

- `get_history()` returns the exact `list[dict]` format expected by `llm.LLM.complete()`.
- `ToolCall` is the same Pydantic model used by `tools.ToolExecutor`, so tool results flow directly into `add_tool_result()`.
- `MessageMetadata` fields (`cost`, `latency_ms`, `usage`, `reasoning_content`) mirror `llm.LLMResponse` for seamless metric capture.
