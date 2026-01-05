"""Example 4: Stateful Researcher (Tree of Thoughts)

This example demonstrates how `loops` and `conversation.fork()` work together.
The loop is just a function. We can run it on *different conversations*
to explore multiple paths in parallel.

Key Concepts:
1.  **Branching**: `conv.fork()` creates isolated state.
2.  **Parallel Loops**: We run `loops.simple` on multiple branches.
3.  **Merging**: We combine the best result back into the main trunk.
"""

import asyncio
import os

from rawagents import AsyncLLM, Conversation
from rawagents.tools import ToolExecutor, tool
from rawagents import loops

@tool
def search_wikipedia(query: str) -> str:
    """Simulated wikipedia search."""
    if "quantum" in query.lower():
        return "Quantum computing uses qubits..."
    if "biological" in query.lower():
        return "Biological computing uses DNA..."
    return "No results."

async def main():
    llm = AsyncLLM(model="openai/gpt-4o-mini")
    tools = ToolExecutor([search_wikipedia])
    
    # Main Trunk
    main_conv = Conversation()
    main_conv.add_user("Compare Quantum Computing vs Biological Computing.")
    
    print("--- branching ---")
    
    # 1. Create Branches
    branch_a = main_conv.fork()
    branch_a.add_system("Focus ONLY on Quantum Computing aspects.")
    
    branch_b = main_conv.fork()
    branch_b.add_system("Focus ONLY on Biological Computing aspects.")
    
    # 2. Define a helper to run a branch
    async def run_branch(name, conv):
        print(f"[{name}] Starting...")
        # Run loop for max 3 steps to gather info
        cfg = loops.LoopConfig(max_steps=3)
        async for step in loops.simple(llm, conv, tools, config=cfg):
            if step.type == "tool_result":
                print(f"[{name}] Found info: {step.tool_results[0].content[:30]}...")
        return conv.get_all_messages()[-1].content

    # 3. Run Parallel
    result_a, result_b = await asyncio.gather(
        run_branch("Branch A", branch_a),
        run_branch("Branch B", branch_b)
    )
    
    print("\n--- merging ---")
    
    # 4. Merge & Finalize
    # We manually construct the synthesis because we are the controller
    main_conv.add_user(f"Research A found: {result_a}")
    main_conv.add_user(f"Research B found: {result_b}")
    main_conv.add_user("Now synthesize a comparison.")
    
    # Run final loop on main trunk
    async for step in loops.simple(llm, main_conv, tools):
        if step.type == "thought":
            print(f"Synthesizing: {step.content}")

if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        print("Please set OPENAI_API_KEY.")
    else:
        asyncio.run(main())

