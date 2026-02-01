# Conversation Component

A lightweight, storage-agnostic session manager for AI agents.

## Overview

The Conversation component acts as the **"operating system for short-term context"**. It manages the timeline of messages, tool calls, and state for your agents. Unlike a simple list of dictionaries, it provides:

*   **Type Safety**: Canonical Pydantic models for all message types.
*   **Branching**: Built-in `fork()` for "Tree of Thoughts" or parallel exploration.
*   **Checkpointing**: `snapshot()` and `load()` for pausing and resuming workflows.
*   **Storage Agnosticism**: Swap between In-Memory, Redis, or SQL backends without changing agent code.
*   **Context Strategies**: Pluggable logic (e.g., Sliding Window) to manage context limits.

---

## Quick Start

```python
from rawagents.state import Conversation
from rawagents.llm import LLM

# 1. Initialize
client = LLMClient()
conv = Conversation()

# 2. Add Messages
conv.add_system("You are a helpful assistant.")
conv.add_user("What is the capital of France?")

# 3. Get History (Formatted for LLM)
messages = conv.get_history()
response = client.complete(messages=messages)

# 4. Add Response
conv.add_assistant(response.content)
print(response.content)
```

---

## Core Concepts

### Message Types

The component supports all standard message roles with a unified API:

```python
# System
conv.add_system("System prompt...")

# User (Text)
conv.add_user("Hello!")

# User (Multimodal / Images)
conv.add_user("What's in this image?", images=["https://example.com/image.png"])

# Assistant
conv.add_assistant("Here is the answer...")

# Assistant (Tool Call)
conv.add_assistant(content="", tool_calls=[tool_call_object])

# Tool Result
conv.add_tool_result(tool_call_id="call_123", content='{"status": "ok"}')
```

### Context Strategies

Strategies control *which* messages are sent to the LLM (e.g., to save tokens). This does **not** delete messages from storage, only filters them for the API call.

```python
from rawagents.state import SlidingWindow

# Keep only the last 10 messages (plus system prompt)
conv = Conversation(strategy=SlidingWindow(window_size=10))

# ... add 100 messages ...

history = conv.get_history()  # Returns ~11 messages
full = conv.get_all_messages() # Returns 101 messages
```

---

## Advanced Features

### Branching (Tree of Thoughts)

Create independent copies of the conversation to explore different paths.

```python
# Fork the conversation
branch_a = conv.fork()
branch_b = conv.fork()

# Explore paths independently
branch_a.add_user("Try approach A")
branch_b.add_user("Try approach B")

# Merge the winner back
conv.merge(branch_a)
```

### Checkpointing (Pause & Resume)

Serialize the conversation state to persist it (e.g., to a database) and resume later.

```python
# Save state
state = conv.snapshot()
# state is a JSON-serializable dict

# ... store in DB ...

# Resume
new_conv = Conversation()
new_conv.load(state)
```

### Optimization Metrics

Track cost, latency, token usage, and model information per message. Fields align with `LLMResponse` for seamless integration.

```python
conv.add_assistant(
    content="Response...",
    metadata={
        "cost": 0.002,
        "latency_ms": 450,
        "model": "gpt-4o",
        "usage": {"prompt_tokens": 50, "completion_tokens": 100, "total_tokens": 150},
        "reasoning_content": "The user asked about...",  # For reasoning models
        "reasoning_blocks": [...],  # Provider-specific reasoning blocks
    }
)
```

---

## Storage Backends

The component uses a **Repository Pattern**. The default is `InMemoryStorage`, but you can swap it for production backends.

```python
from rawagents.state import InMemoryStorage

# Default (In-Memory)
conv = Conversation(storage=InMemoryStorage())

# Custom (Implement BaseStorage protocol)
# conv = Conversation(storage=RedisStorage(url="..."))
```

---

## Integration with LLM Client

This component is designed to work seamlessly with `rawagents.llm`.

*   **Shared Types**: Both use the same `ToolCall` definition.
*   **Formatted Output**: `get_history()` returns the exact list-of-dicts format required by `client.complete()`.

```python
# Seamless flow
response = client.complete(messages=conv.get_history())
conv.add_assistant(response.content)
```

## TODO
- [ ] The component doesn't reliably support images in messages at the moment, that is something which will need to be tested and added later. 

