# Getting Started with RawAgents

This guide shows how to install RawAgents and run your first agent loop.

## Installation

**Requires Python 3.13+**

RawAgents is published as a Python package:

```bash
pip install git+https://github.com/tawab-safi/rawagents.git
```

You will also need an API key for at least one LLM provider (for example, OpenAI) and set it in your environment:

```bash
export OPENAI_API_KEY=sk-...
```

## First agent loop

The minimal building blocks are:

- `AsyncLLM` – talks to the model (async client).
- `LLM` – sync client, if you prefer blocking calls.
- `Conversation` – stores messages and metadata.
- `@tool` + `ToolExecutor` – define and execute tools.
- `loops.simple` – an async generator that runs the loop.

```python
from rawagents import AsyncLLM, Conversation, ToolExecutor, tool, loops


@tool
def search_web(query: str) -> str:
    """Pretend to search the web for a query."""
    return f"Results for: {query}"


async def main() -> None:
    client = AsyncLLM(model="openai/gpt-4o")
    conv = Conversation()
    tools = ToolExecutor([search_web])

    conv.add_system("You are a helpful assistant.")
    conv.add_user("Find resources to learn about agent frameworks.")

    async for step in loops.simple(
        llm=client,
        conversation=conv,
        tools=tools,
    ):
        if step.type == "finish":
            print("Final answer:", step.content)
            break
```

See the [Recipes](recipes/basic_chat_bot.md) section for more complete examples.


