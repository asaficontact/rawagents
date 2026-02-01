# Recipe: Tool-Using Assistant

This example shows an assistant that can call tools to answer questions.

Source: `examples/loops/02_tool_using_assistant.py`

```python
import asyncio
from typing import Annotated
from rawagents import AsyncLLM, Conversation, ToolExecutor, Inject, tool, loops


@tool
def get_stock_price(symbol: str, user: Annotated[str, Inject]) -> str:
    """Get the current stock price."""
    price = 150.00 if symbol == "AAPL" else 100.00
    return f"{symbol} price is ${price} (User: {user})"


async def main() -> None:
    client = AsyncLLM(model="openai/gpt-4o")
    conv = Conversation()
    executor = ToolExecutor([get_stock_price])

    conv.add_system("You are a financial assistant.")
    conv.add_user("What is the price of Apple?")

    async for step in loops.simple(
        llm=client,
        conversation=conv,
        tools=executor,
        context={"user": "investor_001"},
    ):
        if step.type == "finish":
            print("Assistant:", step.content)
            break


if __name__ == "__main__":
    asyncio.run(main())
```


