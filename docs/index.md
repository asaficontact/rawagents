# RawAgents

RawAgents is an **anti-framework** for AI agents.

**Primitives, not prescriptions.**

```python
async for step in loops.simple(llm, conv, tools):
    print(step)  # Your entire agent. Visible. Controllable.
```

## Installation

```bash
pip install git+https://github.com/tawab-safi/rawagents.git
```

## Four Building Blocks

| Component | Import | What It Does |
|-----------|--------|--------------|
| **LLM** | `rawagents.llm` | Any provider, one interface |
| **Conversation** | `rawagents.state` | Memory that forks, merges, checkpoints |
| **Tools** | `rawagents.tools` | Python functions with auto-generated schemas |
| **Loops** | `rawagents.loops` | Orchestration as readable, testable Python |

## Quick Example

```python
from rawagents import AsyncLLM, Conversation, ToolExecutor, tool, loops


@tool
def echo(message: str) -> str:
    """Return the same message."""
    return message


async def main() -> None:
    client = AsyncLLM(model="openai/gpt-4o")
    conv = Conversation()
    tools = ToolExecutor([echo])

    conv.add_system("You are a concise assistant.")
    conv.add_user("Say hello and call the echo tool with 'Hello from RawAgents'.")

    async for step in loops.simple(llm=client, conversation=conv, tools=tools):
        print(step.type, step.content or step.tool_calls or step.tool_results)
```

## Learn More

- [Getting Started](getting-started.md) — Installation and first agent
- [Philosophy](rawagents_philosophy.md) — Design principles
- [Architecture](rawagents.md) — How it all fits together
- [Vision](vision.md) — Where we're headed

## Component Guides

- [LLM](components/llm.md)
- [State (Conversation)](components/state.md)
- [Tools](components/tools.md)
- [Prompts](components/prompts.md)
- [RAG](components/rag.md)

## Built-in Tools

RawAgents ships with ready-to-use tools for common agent tasks:

- [Overview](tools/index.md)
- [File System](tools/fs.md) -- read, write, edit, glob, grep, and more
- [Shell](tools/shell.md) -- run commands with session management
- [Web](tools/web.md) -- fetch pages and search the web

## Recipes

- [Basic Chatbot](recipes/basic_chat_bot.md)
- [Tool-Using Assistant](recipes/tool_using_assistant.md)
- [Human-in-the-Loop](recipes/human_in_the_loop.md)
- [Stateful Researcher](recipes/stateful_researcher.md)
- [Streaming API Server](recipes/streaming_api_server.md)
