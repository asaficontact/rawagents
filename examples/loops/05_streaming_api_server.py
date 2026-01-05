"""Example 5: Streaming API Server (FastAPI Style)

This example simulates how you would serve an agent loop over HTTP.
Because `loops.simple` is a generator, it maps 1:1 to StreamingResponse.

Key Concepts:
1.  **API Integration**: The loop fits inside a route handler.
2.  **Streaming**: We yield chunks to the client in real-time.
"""

import asyncio
import json
import os

from rawagents import AsyncLLM, Conversation, loops
from rawagents.tools import ToolExecutor

# Mocking FastAPI's StreamingResponse for this script
async def mock_streaming_response(generator):
    print("HTTP/1.1 200 OK")
    print("Content-Type: text/event-stream\n")
    async for chunk in generator:
        print(chunk)  # In real app, this goes to the network socket

async def chat_endpoint(user_message: str):
    """Simulates a POST /chat endpoint handler."""
    
    # 1. Rehydrate State (Simulated)
    conv = Conversation()
    conv.add_user(user_message)
    
    llm = AsyncLLM(model="openai/gpt-4o-mini")
    tools = ToolExecutor([]) # No tools for this demo
    
    # 2. Create the Loop Generator
    agent_stream = loops.simple(llm, conv, tools)
    
    # 3. Stream to Client (Server-Sent Events format)
    async for step in agent_stream:
        if step.type == "thought":
            # Send text chunks
            payload = {"type": "delta", "content": step.content}
            yield f"data: {json.dumps(payload)}\n\n"
            
        elif step.type == "tool_call":
            # Notify client we are working
            payload = {"type": "status", "status": "calling_tools"}
            yield f"data: {json.dumps(payload)}\n\n"
            
        elif step.type == "finish":
            yield "data: [DONE]\n\n"

async def main():
    print("--- Simulating HTTP Request ---")
    request = "Tell me a joke."
    
    # Pass the handler to our mock server
    await mock_streaming_response(chat_endpoint(request))

if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        print("Please set OPENAI_API_KEY.")
    else:
        asyncio.run(main())

