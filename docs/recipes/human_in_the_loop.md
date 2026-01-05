# Recipe: Human-in-the-Loop Approval

This example shows how to pause the loop to ask for human approval before executing tools.

Source: `examples/loops/03_human_in_the_loop.py`

```python
import asyncio
from rawagents import (
    AsyncLLM,
    ApprovalDecision,
    Conversation,
    ToolExecutor,
    tool,
    loops,
)


@tool
def dangerous_action(target: str) -> str:
    """An action that should be approved by a human."""
    return f"Did something potentially dangerous to {target}"


async def main() -> None:
    llm = AsyncLLM(model="openai/gpt-4o")
    conv = Conversation()
    executor = ToolExecutor([dangerous_action])

    conv.add_system("You are an assistant that must get approval for risky actions.")
    conv.add_user("Delete the 'test' database.")

    runner = loops.interactive(
        llm=llm,
        conversation=conv,
        tools=executor,
    )

    async for step in runner:
        if step.type == "approval_request":
            print("Model wants to run tools:", step.tool_calls)
            approve = input("Approve? [y/N] ") == "y"
            decision = ApprovalDecision(approved=approve)
            try:
                await runner.asend(decision)
            except StopAsyncIteration:
                break
        elif step.type == "finish":
            print("Assistant:", step.content)
            break


if __name__ == "__main__":
    asyncio.run(main())
```


