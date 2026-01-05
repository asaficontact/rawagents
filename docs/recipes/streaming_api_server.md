# Recipe: Streaming API Server

This example shows how to integrate RawAgents with a web server that streams responses to clients.

Source: `examples/loops/05_streaming_api_server.py`

```python
import asyncio
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from rawagents import AsyncLLM, Conversation, loops


app = FastAPI()
client = AsyncLLM(model="openai/gpt-4o")


@app.post("/chat")
async def chat(payload: dict) -> StreamingResponse:
    conv = Conversation()
    conv.add_system("You are a helpful assistant.")
    conv.add_user(payload["message"])

    async def stream():
        async for step in loops.simple(
            conversation=conv,
            llm=client,
            tools=None,
        ):
            if step.type == "thought" or step.type == "finish":
                chunk = step.content or ""
                if chunk:
                    yield chunk

    return StreamingResponse(stream(), media_type="text/plain")
```


