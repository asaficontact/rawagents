"""Example 2: Tool Using Assistant

This example demonstrates how the loop orchestrates tool execution.
The loop automatically:
1. Detects the LLM wants to call a tool.
2. Executes the tool using `ToolExecutor`.
3. Feeds the result back to the LLM.
4. Continues until the LLM answers.

Key Concepts:
1.  **Dependency Injection**: We pass `user_id` in the loop `context`, not the prompt.
"""

import asyncio
import os
from typing import Annotated

from rawagents import AsyncLLM, Conversation
from rawagents.tools import ToolExecutor, tool, Inject
from rawagents import loops

# --- Define Tools ---

@tool
def get_customer_info(user_id: Annotated[str, Inject]) -> str:
    """Get profile information for the current customer."""
    # Mock database lookup
    if user_id == "admin":
        return "Name: Alice Admin, Plan: Enterprise, Region: US-East"
    return "Name: Bob Basic, Plan: Free, Region: EU-West"

@tool
def check_system_status(region: str) -> str:
    """Check system health in a specific region."""
    return f"All systems operational in {region}."

async def main():
    # 1. Setup
    llm = AsyncLLM(model="openai/gpt-4o")
    conv = Conversation()
    conv.add_system("You are a technical support assistant.")
    
    # Register tools
    executor = ToolExecutor([get_customer_info, check_system_status])
    
    # 2. User Query
    # Note: The user doesn't say who they are. The tool gets that from context.
    conv.add_user("Check the system status for my region.")
    
    print(f"User: {conv.get_all_messages()[-1].content}")

    # 3. Run Loop with Context
    # We inject 'user_id' here. The tool `get_customer_info` will receive it automatically.
    context_data = {"user_id": "admin"}
    
    async for step in loops.simple(llm, conv, executor, context=context_data):
        
        if step.type == "thought":
            print(f"🤖 Thought: {step.content}")
            
        elif step.type == "tool_call":
            tool_names = [tc.name for tc in step.tool_calls]
            print(f"🛠️  Agent requested tools: {tool_names}")
            
        elif step.type == "tool_result":
            for res in step.tool_results:
                print(f"✅ Tool Output ({res.name}): {res.content}")

    print(f"\n🏁 Final Answer: {conv.get_all_messages()[-1].content}")

if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        print("Please set OPENAI_API_KEY.")
    else:
        asyncio.run(main())

