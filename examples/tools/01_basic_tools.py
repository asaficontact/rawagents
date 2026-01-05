"""Basic usage of the Tool Executor.

This example demonstrates:
1. Defining a simple tool using the @tool decorator.
2. Generating JSON schemas for the LLM.
3. Executing the tool with a mock ToolCall.
"""

import asyncio
import json
from rawagents.tools import tool, ToolExecutor
from rawagents.utils.types import ToolCall

# 1. Define a tool
@tool
def calculator(a: int, b: int, operation: str = "add") -> int:
    """Perform a basic calculation.
    
    :param a: The first number.
    :param b: The second number.
    :param operation: The operation to perform (add, sub, mul).
    """
    if operation == "add":
        return a + b
    elif operation == "sub":
        return a - b
    elif operation == "mul":
        return a * b
    else:
        raise ValueError(f"Unknown operation: {operation}")

async def main():
    print("--- 1. Tool Definition ---")
    # 2. Initialize Executor
    executor = ToolExecutor([calculator])
    print(f"Registered tools: {executor.get_tool_names()}")
    
    # 3. Generate Schema (What the LLM sees)
    print("\n--- 2. Schema Generation ---")
    schemas = executor.get_schemas()
    print(json.dumps(schemas[0], indent=2))
    
    # 4. Execute (Simulating LLM call)
    print("\n--- 3. Execution ---")
    
    # Mock a ToolCall (usually comes from LLM)
    call = ToolCall(
        id="call_123",
        name="calculator",
        arguments={"a": 10, "b": 5, "operation": "mul"}
    )
    
    result = await executor.execute(call)
    
    print(f"Tool Call: {call.name}({call.arguments})")
    print(f"Result: {result.content}")
    print(f"Is Error: {result.is_error}")

if __name__ == "__main__":
    asyncio.run(main())

