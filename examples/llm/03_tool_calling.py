"""Example 3: Tool Calling

This example demonstrates function/tool calling with the LLM client.

IMPORTANT: The client returns tool call REQUESTS but does NOT execute them.
You are responsible for executing tools and continuing the conversation.

Requirements:
    - Set OPENAI_API_KEY environment variable

Usage:
    uv run python examples/llm_client/03_tool_calling.py --model openai/gpt-4o-mini
"""

import json
import argparse
from pydantic import BaseModel, Field

from rawagents import LLM


# Define tools as Pydantic models
class GetWeather(BaseModel):
    """Get the current weather for a location."""

    location: str = Field(description="City and state, e.g., 'San Francisco, CA'")
    unit: str = Field(default="fahrenheit", description="Temperature unit")


class SearchWeb(BaseModel):
    """Search the web for information."""

    query: str = Field(description="The search query")
    max_results: int = Field(default=5, description="Maximum number of results")


class Calculator(BaseModel):
    """Perform a mathematical calculation."""

    expression: str = Field(description="Mathematical expression to evaluate")


# Simulated tool implementations
def execute_tool(name: str, args: dict) -> str:
    """Execute a tool and return the result."""
    if name == "GetWeather":
        # Simulated weather data
        return json.dumps(
            {
                "location": args["location"],
                "temperature": 72,
                "unit": args.get("unit", "fahrenheit"),
                "condition": "sunny",
            }
        )
    elif name == "SearchWeb":
        # Simulated search results
        return json.dumps(
            {
                "query": args["query"],
                "results": [
                    {"title": "Result 1", "snippet": "Some information..."},
                    {"title": "Result 2", "snippet": "More information..."},
                ],
            }
        )
    elif name == "Calculator":
        # Actually evaluate (be careful with this in production!)
        try:
            result = eval(args["expression"])  # noqa: S307
            return json.dumps({"expression": args["expression"], "result": result})
        except Exception as e:
            return json.dumps({"error": str(e)})
    return json.dumps({"error": f"Unknown tool: {name}"})


def main(model: str) -> None:
    client = LLMClient()

    print(f"Using model: {model}")
    print("=" * 60)
    print("Tool Calling Example")
    print("=" * 60)

    # Initial conversation
    messages = [
        {"role": "user", "content": "What's the weather like in New York City?"}
    ]

    # Step 1: Get tool calls from the model
    print("\n--- Step 1: Ask the model ---")
    response = client.complete_with_tools(
        model=model,
        messages=messages,
        tools=[GetWeather, SearchWeb, Calculator],
        tool_choice="auto",
    )

    print(f"Model response: {response.content or '(no text, tool call requested)'}")
    print(f"Tool calls: {len(response.tool_calls)}")

    # Step 2: Execute tool calls (YOUR responsibility)
    if response.tool_calls:
        print("\n--- Step 2: Execute tools ---")

        # Add assistant message with tool calls
        messages.append(
            {
                "role": "assistant",
                "content": response.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                    }
                    for tc in response.tool_calls
                ],
            }
        )

        # Execute each tool and add results
        for tool_call in response.tool_calls:
            print(f"  Executing: {tool_call.name}({tool_call.arguments})")
            result = execute_tool(tool_call.name, tool_call.arguments)
            print(f"  Result: {result}")

            # Add tool result to conversation
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )

        # Step 3: Get final response
        print("\n--- Step 3: Get final response ---")
        final_response = client.complete_with_tools(
            model=model,
            messages=messages,
            tools=[GetWeather, SearchWeb, Calculator],
            tool_choice="auto",
        )
        print(f"Final response: {final_response.content}")
    else:
        print("Model didn't request any tool calls.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the tool calling example with optional model selection.")
    parser.add_argument(
        "--model", "-m",
        type=str,
        default="openai/gpt-4o-mini",
        help="Model name to use (default: openai/gpt-4o-mini)",
    )
    args = parser.parse_args()
    main(args.model)
