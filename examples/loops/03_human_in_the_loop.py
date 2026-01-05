"""Example 3: Human-in-the-Loop (Safety)

This example demonstrates the `interactive` loop strategy.
Unlike `simple`, which runs autonomously, `interactive` PAUSES 
before executing tools to ask for approval.

Key Concepts:
1.  **Approval Request**: The loop yields a special step type.
2.  **Generator Send**: We use `runner.asend()` to inject the human's decision.
"""

import asyncio
import os

from rawagents import AsyncLLM, Conversation
from rawagents.tools import ToolExecutor, tool
from rawagents import loops
from rawagents.loops import ApprovalDecision

# --- Define Tools ---

@tool
def list_files() -> str:
    """List files in the current directory (Safe)."""
    return "report.pdf, salary.xlsx, notes.txt"

@tool
def delete_file(filename: str) -> str:
    """Delete a file (Dangerous!)."""
    return f"Deleted {filename} successfully."

async def main():
    llm = AsyncLLM(model="openai/gpt-4o")
    conv = Conversation()
    tools = ToolExecutor([list_files, delete_file])
    
    conv.add_system("You are a file manager.")
    
    # User asks to do something dangerous
    conv.add_user("Delete salary.xlsx")
    print("User: Delete salary.xlsx")

    # 1. Create the Interactive Runner
    # We do not iterate with a simple 'for' loop because we need to send data back.
    runner = loops.interactive(llm, conv, tools)

    # 2. Manual Iteration
    try:
        async for step in runner:
            
            if step.type == "thought":
                print(f"🤖 {step.content}")
                
            elif step.type == "approval_request":
                # LOOP PAUSED HERE
                print(f"\n⚠️  APPROVAL REQUEST: Agent wants to call {step.tool_calls}")
                
                # Ask Human
                choice = input("Allow this? (y/n): ").lower()
                
                if choice == "y":
                    print(">> User Approved.")
                    decision = ApprovalDecision(approved=True)
                else:
                    reason = input("Reason for denial: ")
                    print(f">> User Denied: {reason}")
                    decision = ApprovalDecision(approved=False, feedback=reason)
                
                # Resume Loop with Decision
                await runner.asend(decision)
                
            elif step.type == "tool_result":
                print(f"✅ Tool executed: {step.tool_results[0].content}")
                
    except Exception as e:
        print(f"Loop ended: {e}")

    print(f"\n🏁 Final State: {conv.get_all_messages()[-1].content}")

if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        print("Please set OPENAI_API_KEY.")
    else:
        asyncio.run(main())

