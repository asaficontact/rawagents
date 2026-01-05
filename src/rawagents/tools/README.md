# Tool Executor Component

A lightweight, type-safe tool dispatching library for AI agents.

## Overview

The Tool Executor (`rawagents.tools`) acts as the "Hands" of your agentic system. It bridges the gap between Large Language Models (LLMs) and Python code by:

*   **Universal Adaptor**: Wraps Python functions, coroutines, and classes into LLM-compatible tools.
*   **Auto-Schema**: Automatically generates OpenAI/Anthropic-compatible JSON schemas from Python type hints and docstrings.
*   **Safe Dispatching**: Executes tools with error boundaries, converting exceptions into readable tool outputs instead of crashing the process.
*   **Context Injection**: Supports "Invisible Arguments" (Dependency Injection) to pass runtime state (User ID, Database, API Keys) to tools without exposing them to the LLM.

## Quick Start

```python
import asyncio
from typing import Annotated
from ai_components.tools import tool, ToolExecutor, Inject

# 1. Define a Tool
@tool
def get_weather(location: str, api_key: Annotated[str, Inject]) -> str:
    """Get weather for a location.
    
    :param location: The city and state (e.g. 'San Francisco, CA').
    """
    # api_key is injected at runtime; the LLM never sees it or generates it.
    return f"Sunny in {location} (using key {api_key})"

async def main():
    # 2. Initialize Executor
    executor = ToolExecutor([get_weather])
    
    # 3. Get Schemas for LLM (OpenAI format)
    # Note: 'api_key' is hidden from the schema!
    schemas = executor.get_schemas()
    
    # 4. Execute (Simulating an LLM Tool Call)
    # ToolCall would typically come from LLMClient
    from ai_components._shared.types import ToolCall
    call = ToolCall(id="call_1", name="get_weather", arguments={"location": "NYC"})
    
    # Runtime context contains the injected dependencies
    result = await executor.execute(
        call, 
        context={"api_key": "secret_123"}
    )
    
    print(result.content) # "Sunny in NYC (using key secret_123)"

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Core Features

### 1. Polymorphic Definitions
Define tools however you like. The `@tool` decorator handles validation and metadata.

```python
# Standard Function
@tool
def add(a: int, b: int) -> int: ...

# Async Coroutine
@tool
async def search(q: str) -> str: ...

# With Pydantic Models (Implicit)
class User(BaseModel):
    name: str
    age: int

@tool
def create_user(user: User) -> str: ...
```

### 2. Automatic Schema Generation
The executor inspects type hints and docstrings (Google/Sphinx style) to generate rich JSON schemas.

```python
@tool
def search(query: str, limit: int = 10):
    """Search the database.
    
    :param query: The search term.
    :param limit: Max results to return.
    """
    ...
```

Generates:
```json
{
  "name": "search",
  "description": "Search the database.",
  "parameters": {
    "type": "object",
    "properties": {
      "query": {"type": "string", "description": "The search term."},
      "limit": {"type": "integer", "description": "Max results to return."}
    },
    "required": ["query"]
  }
}
```

### 3. Dependency Injection (Context)
Deep agents often need access to runtime state (DB connections, user sessions) that the LLM cannot provide. Use `Annotated[T, Inject]` to mark these.

```python
from ai_components.tools import Inject

@tool
def query_db(query: str, db: Annotated[Database, Inject]):
    return db.execute(query)

# The LLM only sees 'query'. The 'db' param is stripped from the schema.
# You must provide 'db' in the context dict during execution.
```

### 4. Safe Execution & Error Handling
Exceptions in tools are caught and converted to `ToolResult(is_error=True)`. This prevents one bad tool call from crashing your entire agent loop.

```python
# If a tool raises ValueError("Invalid ID")...
result = await executor.execute(call)
print(result.is_error) # True
print(result.content)  # "Tool 'my_tool' raised ValueError: Invalid ID"
```

---

## Integration with LLM Client & Conversation

The components are designed to work together using shared types.

```python
# 1. Setup
executor = ToolExecutor([get_weather])
client = LLMClient()
conv = Conversation()

# 2. Get Schemas & Call LLM
schemas = executor.get_schemas()
response = client.complete_with_tools(
    messages=conv.get_history(),
    tools=schemas  # Pass raw schemas directly
)

# 3. Execute & Save
if response.tool_calls:
    for call in response.tool_calls:
        # Execute
        result = await executor.execute(call, context={...})
        
        # Save to history
        conv.add_tool_result(
            tool_call_id=result.tool_call_id,
            content=result.content
        )
```

