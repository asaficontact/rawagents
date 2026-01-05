# RawAgents

RawAgents is an **anti-framework** for AI agents.

Instead of hiding orchestration behind a single `Agent` or `Executor` object, it gives you **raw, composable primitives** – LLM clients, conversation state, tools, and async loops – that you wire together yourself.

```bash
pip install rawagents
```

## Hello, RawAgents

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

    async for step in loops.simple(
        conversation=conv,
        llm=client,
        tools=tools,
    ):
        print(step.type, step.content or step.tool_calls or step.tool_results)
```

To understand the philosophy and architecture, read:

- [RawAgents: The Anti-Framework for AI Agents](rawagents.md)
- [RawAgents Philosophy](rawagents_philosophy.md)
- [Issues with Agent Frameworks](issues_with_agent_frameworks.md)


