"""Example 1: Basic Chat Bot (Hello World)

This example demonstrates the simplest usage of the `unchained` loop.
It sets up a basic "Think -> Act -> Reply" loop, although in this case
there are no tools, so it just acts as a chat interface.

Key Concepts:
1.  **Transparency**: We print every "thought" the AI yields.
2.  **Stateless Loop**: The loop function doesn't hold state; `conversation` does.
"""

import asyncio
import os

# Mock imports - in a real app these would be from `unchained`
from rawagents import AsyncLLM, Conversation
from rawagents.tools import ToolExecutor
from rawagents import loops

async def main():
    # 1. Initialize Components
    # The "Brain"
    llm = AsyncLLM(model="openai/gpt-4o")
    
    # The "Memory"
    conv = Conversation()
    conv.add_system("You are a helpful, concise assistant.")
    
    # The "Hands" (Empty for no
    tools = ToolExecutor([])

    print("--- Chat Started (Type 'quit' to exit) ---")

    while True:
        user_input = input("\nUser: ")
        if user_input.lower() in ("quit", "exit"):
            break

        conv.add_user(user_input)

        print("\n[Agent Loop Running]")
        
        # 2. Run the Loop
        # The loop is a GENERATOR. We iterate over it to watch the agent think.
        async for step in loops.simple(llm, conv, tools):
            
            if step.type == "thought":
                # The agent is "thinking" (generating text)
                print(f"🤖 AI: {step.content}")
                
            elif step.type == "tool_call":
                # Should not happen in this example, but good to handle
                print(f"🛠️ Calling: {step.tool_calls}")
                
            elif step.type == "finish":
                # Loop is done for this turn
                pass

if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        print("Please set OPENAI_API_KEY to run this example.")
    else:
        asyncio.run(main())

