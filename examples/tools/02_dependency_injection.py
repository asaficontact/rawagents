"""Dependency Injection (Context) example.

This example demonstrates how to inject runtime dependencies (like a User ID
or Database connection) into a tool without the LLM seeing or providing them.
This is critical for building secure, context-aware agents.
"""

import asyncio
from typing import Annotated, Any
from rawagents.tools import tool, ToolExecutor, Inject
from rawagents.utils.types import ToolCall

# Mock Database
class MockDatabase:
    def get_user(self, user_id: str) -> dict[str, Any]:
        return {"id": user_id, "name": "Alice", "plan": "premium"}

# 1. Define a tool with Injection
@tool
def get_user_info(
    db: Annotated[MockDatabase, Inject],  # Injected!
    user_id: Annotated[str, Inject],      # Injected!
) -> str:
    """Get information about the current user.
    
    Note: This tool takes NO arguments from the LLM.
    Everything is injected from context.
    """
    user = db.get_user(user_id)
    return f"User: {user['name']} ({user['plan']})"

async def main():
    # 2. Initialize
    executor = ToolExecutor([get_user_info])
    
    # 3. Verify Schema (Should be empty parameters!)
    schemas = executor.get_schemas()
    print("--- Tool Schema (LLM View) ---")
    print(f"Name: {schemas[0]['function']['name']}")
    # The parameters should be empty because everything is injected
    props = schemas[0]['function']['parameters']['properties']
    print(f"Parameters: {list(props.keys())} (Expected: [])")
    
    # 4. Execution Context
    db_instance = MockDatabase()
    runtime_context = {
        "db": db_instance,
        "user_id": "user_999"
    }
    
    # 5. Execute
    call = ToolCall(id="call_1", name="get_user_info", arguments={})
    
    print("\n--- Execution ---")
    result = await executor.execute(call, context=runtime_context)
    
    print(f"Result: {result.content}")

if __name__ == "__main__":
    asyncio.run(main())

