# RawAgents: Build What You Actually Need

**Status:** Pre-Alpha
**Philosophy:** Primitives, not prescriptions.

---

## The Idea

```python
async for step in loops.simple(llm, conv, tools):
    print(step)  # Your entire agent. Visible. Controllable.
```

Four building blocks. Infinite possibilities.

| Component | Import | What It Does |
|-----------|--------|--------------|
| **LLM** | `rawagents.llm` | Any provider, one interface |
| **Conversation** | `rawagents.state` | Memory that forks, merges, checkpoints |
| **Tools** | `rawagents.tools` | Python functions with auto-generated schemas |
| **Loops** | `rawagents.loops` | Orchestration as readable, testable Python |

Every step visible. Every decision traceable. Type-safe by default.

---

## Why RawAgents?

**Simple enough** to learn in an afternoon.
**Powerful enough** for production.
**Flexible enough** for research.

We build the bricks. You build the system.

---

## Quick Start

```python
from rawagents import AsyncLLM, Conversation, ToolExecutor, tool, loops


@tool
def search(query: str) -> str:
    """Search the web for the given query."""
    return f"Results for: {query}"


async def main():
    llm = AsyncLLM(model="openai/gpt-4o")
    conv = Conversation()
    tools = ToolExecutor([search])

    conv.add_system("You are a helpful assistant.")
    conv.add_user("Find resources about building AI agents.")

    async for step in loops.simple(llm=llm, conversation=conv, tools=tools):
        if step.type == "thought":
            print(f"Thinking: {step.content}")
        elif step.type == "tool_call":
            print(f"Calling: {[c.name for c in step.tool_calls]}")
        elif step.type == "finish":
            print(f"Answer: {step.content}")
```

No hidden engines. No invisible executors. Just Python you can read, test, and trust.

---

## Installation

```bash
pip install git+https://github.com/tawab-safi/rawagents.git
```

Set your API key:

```bash
export OPENAI_API_KEY=sk-...
```

---

## The Four Primitives

### 1. LLM (`rawagents.llm`)

Stateless client for any provider. Sync and async. Structured output with Pydantic.

```python
from rawagents import AsyncLLM, LLM

client = AsyncLLM(model="openai/gpt-4o")
response = await client.complete([{"role": "user", "content": "Hello"}])
```

### 2. Conversation (`rawagents.state`)

Message history with branching, checkpointing, and context strategies.

```python
from rawagents import Conversation

conv = Conversation()
conv.add_system("You are helpful.")
conv.add_user("Hello!")

# Fork for parallel exploration
branch = conv.fork()

# Snapshot for checkpointing
snapshot = conv.snapshot()
```

### 3. Tools (`rawagents.tools`)

Python functions become LLM tools. Dependency injection included.

```python
from rawagents import tool, ToolExecutor, Inject
from typing import Annotated


@tool
def get_user(user_id: str, db: Annotated[Database, Inject]) -> dict:
    """Fetch user from database."""
    return db.get(user_id)


executor = ToolExecutor([get_user], context={"db": my_database})
```

### 4. Loops (`rawagents.loops`)

Async generators that yield every step. You see everything.

```python
from rawagents import loops

async for step in loops.simple(llm, conv, tools, max_steps=10):
    print(step.type, step.content)
```

For human-in-the-loop:

```python
async for step in loops.interactive(llm, conv, tools, approval_fn=my_approver):
    print(step)
```

---

## Recipes

See the [docs/recipes](docs/recipes/) folder for complete examples:

- [Basic Chatbot](docs/recipes/basic_chat_bot.md)
- [Tool-Using Assistant](docs/recipes/tool_using_assistant.md)
- [Human-in-the-Loop](docs/recipes/human_in_the_loop.md)
- [Stateful Researcher](docs/recipes/stateful_researcher.md)
- [Streaming API Server](docs/recipes/streaming_api_server.md)

---

## Roadmap

- **v0.1** ✅ Core primitives (LLM, Conversation, Tools, Loops)
- **v0.2** ✅ Human-in-the-loop, observability (latency, tokens, cost)
- **v0.3** 🔄 Multi-agent coordination (`loops.swarm`)
- **Future** 📋 RAG integration, persistence backends

---

## Documentation

- [Getting Started](docs/getting-started.md)
- [Philosophy](docs/rawagents_philosophy.md)
- [Component Guides](docs/components/)

---

**RawAgents is an anti-framework.**
We don't build the castle for you. We give you the sharpest bricks — and get out of your way.
