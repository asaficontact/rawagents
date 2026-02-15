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

## Built-in Tools

RawAgents ships with built-in tools for file system operations, shell
command execution, and web fetching. These tools follow the same `@tool`
decorator pattern shown above and can be passed directly to a
`ToolExecutor`.

Each tool category uses a `SecurityContext` to restrict operations to a
workspace directory:

```python
from rawagents.tools.builtin.fs import read, write, set_security_context, SecurityContext

# Configure the security boundary (required before calling any fs tool)
set_security_context(SecurityContext(workspace="/path/to/project"))

# Pass built-in tools to your executor alongside your own
tools = ToolExecutor([search_web, read, write])
```

Shell tools work the same way:

```python
from rawagents.tools.builtin.shell import bash, set_security_context, SecurityContext

set_security_context(SecurityContext(workspace="/path/to/project"))
```

For the full list of available tools and detailed configuration options, see
the [Built-in Tools documentation](tools/index.md).
