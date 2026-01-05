# Recipe: Basic Chat Bot

This example shows the smallest useful RawAgents loop: a single agent that chats with a user.

Source: `examples/loops/01_basic_chat_bot.py`

```python
import asyncio
from rawagents import AsyncLLM, Conversation, loops


async def main() -> None:
    client = AsyncLLM(model="openai/gpt-4o")
    conv = Conversation()

    conv.add_system("You are a helpful assistant.")
    conv.add_user("Hello! Who are you?")

    async for step in loops.simple(
        conversation=conv,
        llm=client,
        tools=None,
    ):
        if step.type == "finish":
            print("Assistant:", step.content)
            break


if __name__ == "__main__":
    asyncio.run(main())
```


