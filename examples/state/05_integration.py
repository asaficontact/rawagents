"""Full integration example with LLM Client and Tools.

This example demonstrates the "Golden Path":
1. Setting up an LLM Client
2. Defining Tools (Pydantic)
3. Running a multi-turn loop with tool execution
4. Recording metrics
"""

import os
import json
from typing import Any
from pydantic import BaseModel, Field

# Mock the LLM Client if API key not present to make example runnable
try:
    from ai_components.llm_client import LLMClient, ToolResponse
except ImportError:
    print("LLMClient not found. Integration example requires ai_components.llm_client")
    exit(1)

from ai_components.conversation import Conversation

# --- Tool Definitions ---
class GetWeather(BaseModel):
    """Get current weather."""
    location: str = Field(description="City, State")

# --- Mock Tool Executor ---
def execute_weather(location: str) -> str:
    """Mock weather API."""
    return json.dumps({"temp": 72, "condition": "sunny", "location": location})

def main():
    # Check for API key (skip real calls if missing)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Skipping real LLM calls (OPENAI_API_KEY not set).")
        print("This example code demonstrates the integration pattern.")
        return

    # 1. Setup
    client = LLMClient()
    conv = Conversation()
    conv.add_system("You are a helpful assistant with access to tools.")
    
    # 2. User Input
    user_query = "What's the weather in San Francisco?"
    conv.add_user(user_query)
    print(f"User: {user_query}")

    # 3. Turn 1: LLM decides to call tool
    # Note: In a real loop, you'd call client.complete_with_tools()
    print("\n[LLM Thinking...]")
    response = client.complete_with_tools(
        messages=conv.get_history(),
        tools=[GetWeather],
        model="openai/gpt-4o"
    )
    
    # 4. Add Assistant Message (with Tool Calls) to History
    # We pass the raw tool_calls from the response
    msg = conv.add_assistant(
        content=response.content or "",
        tool_calls=response.tool_calls,
        metadata={
            "cost": response.cost,
            "latency_ms": response.latency_ms,
            "model": response.model,
            "usage": response.usage,
        }
    )
    print(f"AI requests tool: {response.tool_calls[0].name}")

    # 5. Execute Tool
    if response.tool_calls:
        for tool_call in response.tool_calls:
            if tool_call.name == "GetWeather":
                result_str = execute_weather(**tool_call.arguments)
                
                # 6. Add Tool Result to History
                conv.add_tool_result(
                    tool_call_id=tool_call.id,
                    content=result_str
                )
                print(f"Tool Output: {result_str}")

    # 7. Turn 2: Final Response
    print("\n[LLM Finalizing...]")
    final_response = client.complete(
        messages=conv.get_history(),
        model="openai/gpt-4o"
    )
    
    conv.add_assistant(
        content=final_response.content,
        metadata={"cost": final_response.cost}
    )
    print(f"AI: {final_response.content}")

if __name__ == "__main__":
    main()

