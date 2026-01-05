"""Full Agent Loop Integration.

This is the "Golden Path" example connecting all three components:
1. LLM Client (Brain)
2. Conversation (Memory)
3. Tool Executor (Hands)

It simulates a complete turn: User -> LLM -> Tool -> LLM -> User.
"""

import asyncio
import os
from typing import Annotated

# Mock client import if not installed
try:
    from rawagents.llm import LLM
    from rawagents.state import Conversation
    from rawagents.tools import tool, ToolExecutor, Inject
except ImportError:
    print("Requires full library installation.")
    exit(1)

# --- 1. Tool Definition ---
@tool
def get_stock_price(symbol: str, user: Annotated[str, Inject]) -> str:
    """Get the current stock price.
    
    :param symbol: The stock ticker symbol (e.g., AAPL).
    """
    # Mock logic
    price = 150.00 if symbol == "AAPL" else 100.00
    return f"{symbol} price is ${price} (User: {user})"

async def main():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Skipping real LLM calls (OPENAI_API_KEY not set).")
        return

    print("--- Initializing Agent ---")
    
    # Components
    client = LLM()
    conv = Conversation()
    executor = ToolExecutor([get_stock_price])
    
    # Setup Context
    conv.add_system("You are a financial assistant.")
    user_id = "investor_001"
    
    # --- Turn 1: User Input ---
    query = "What is the price of Apple?"
    conv.add_user(query)
    print(f"User: {query}")
    
    # --- Turn 2: LLM Decide ---
    print("LLM Thinking...")
    response = client.complete_with_tools(
        messages=conv.get_history(),
        tools=executor.get_schemas(),  # Pass schemas from executor
        model="openai/gpt-4o"
    )
    
    conv.add_assistant(
        content=response.content or "",
        tool_calls=response.tool_calls,
        metadata={"cost": response.cost}
    )
    
    if response.tool_calls:
        print(f"LLM called tools: {[t.name for t in response.tool_calls]}")
        
        # --- Turn 3: Tool Execution ---
        for call in response.tool_calls:
            # Inject runtime context
            result = await executor.execute(
                call, 
                context={"user": user_id}
            )
            
            # Save result
            conv.add_tool_result(
                tool_call_id=result.tool_call_id,
                content=result.content
            )
            print(f"Tool Output: {result.content}")
            
        # --- Turn 4: Final Response ---
        print("LLM Finalizing...")
        final = client.complete(
            messages=conv.get_history(),
            model="openai/gpt-4o"
        )
        conv.add_assistant(final.content)
        print(f"AI: {final.content}")

if __name__ == "__main__":
    asyncio.run(main())

