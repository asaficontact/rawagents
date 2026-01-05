# Recipe: Stateful Researcher with Branching

This example shows how to use `Conversation.fork()` and `merge()` to explore multiple reasoning paths.

Source: `examples/loops/04_stateful_researcher.py`

```python
import asyncio
from rawagents import AsyncLLM, Conversation, loops


async def run_branch(label: str, conv: Conversation, client: AsyncLLM) -> Conversation:
    branch = conv.fork()
    branch.add_user(f"Explore approach: {label}")

    async for step in loops.simple(
        conversation=branch,
        llm=client,
        tools=None,
    ):
        if step.type == "finish":
            print(f"[{label}] Final:", step.content)
            break

    return branch


async def main() -> None:
    client = AsyncLLM(model="openai/gpt-4o")
    conv = Conversation()
    conv.add_system("You are a research assistant.")
    conv.add_user("Design an experiment to compare two algorithms.")

    branch_a = await run_branch("A", conv, client)
    branch_b = await run_branch("B", conv, client)

    # Merge the chosen branch back into the main conversation
    conv.merge(branch_a)


if __name__ == "__main__":
    asyncio.run(main())
```


