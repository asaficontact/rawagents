# Tools Component (`rawagents.tools`)

The tools component provides the **"hands"** of your agent -- a stateless dispatcher that turns Python functions into LLM-callable tools. It handles schema generation, dependency injection, and safe execution so the LLM can invoke real code without the agent loop needing to know the details.

It focuses on:

- defining tools from regular Python functions via the `@tool` decorator
- automatic OpenAI-compatible JSON schema generation from type hints and docstrings
- dependency injection with `Annotated[T, Inject]` for runtime context (DB, API keys)
- async-first execution with an error boundary that never raises

It deliberately does **not** call the LLM or manage conversation state -- those are handled by the `llm` and `state` components respectively.

---

## Quick start

```python
import asyncio
from typing import Annotated
from rawagents import tool, ToolExecutor, Inject


@tool
def get_weather(location: str, api_key: Annotated[str, Inject]) -> str:
    """Get weather for a location."""
    return f"Sunny in {location} (key={api_key})"


async def main() -> None:
    executor = ToolExecutor([get_weather])
    schemas = executor.get_schemas()  # OpenAI-compatible tool schemas

    # After an LLM returns a ToolCall:
    from rawagents.utils.types import ToolCall

    call = ToolCall(id="call_1", name="get_weather", arguments={"location": "NYC"})
    result = await executor.execute(call, context={"api_key": "secret_123"})
    print(result.content)   # "Sunny in NYC (key=secret_123)"
    print(result.is_error)  # False
```

See the full README in `src/rawagents/tools/README.md` for additional examples.

---

## `@tool` Decorator

The `@tool` decorator validates the function signature at decoration time (fail fast) and attaches metadata for schema generation and execution. Both sync and async functions are supported.

```python
from rawagents import tool

# Basic usage (name and description inferred from function)
@tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

# With explicit overrides
@tool(name="search", description="Search the web")
async def web_search(query: str, limit: int = 10) -> list[str]:
    """Search the web for results."""
    ...
```

**Signature requirements:**

- Every parameter must have a type annotation.
- A return type annotation is required (`-> str`, `-> int`, etc.).
- Non-injected parameters must be JSON-compatible: `str`, `int`, `float`, `bool`, `list`, `dict`, `Literal`, PEP 604 unions (`str | None`), or Pydantic `BaseModel` subclasses.

---

## Parameter Types and `Annotated`

Parameter descriptions are extracted automatically from Google-style or Sphinx-style docstrings. You can also use `Annotated[T, "description"]` for inline documentation:

```python
from typing import Annotated

@tool
def search(
    query: Annotated[str, "The search query"],
    limit: Annotated[int, "Max results"] = 10,
) -> str:
    """Search the database."""
    ...
```

Optional parameters (those with defaults) are omitted from the schema's `required` list, matching standard OpenAI function-calling conventions.

---

## `Inject` -- Dependency Injection

The `Inject` marker hides a parameter from the LLM schema and resolves it from a context dictionary at execution time. This keeps secrets and runtime state (database connections, API keys, user sessions) invisible to the model.

```python
from typing import Annotated
from rawagents import tool, Inject

@tool
def query_db(
    sql: str,                              # LLM provides this
    db: Annotated[Database, Inject],       # You provide at runtime
) -> str:
    """Execute a SQL query."""
    return db.execute(sql)
```

At execution time, pass injected values via the `context` dict:

```python
result = await executor.execute(call, context={"db": my_db_connection})
```

If a required injected parameter is missing from `context`, the executor returns a `ToolResult` with `is_error=True` describing the missing key.

---

## `ToolExecutor`

`ToolExecutor` is the registry and dispatcher. It holds a set of registered tools, produces schemas for the LLM, and executes tool calls.

### Construction

```python
from rawagents import ToolExecutor

executor = ToolExecutor(
    tools=[tool_a, tool_b],                 # list of @tool functions (optional)
    on_before=lambda tc: print(tc.name),    # called before each execution (optional)
    on_after=lambda tc, r: log(r.content),  # called after each execution (optional)
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tools` | `list[Callable] \| None` | `None` | Initial `@tool` decorated functions to register. |
| `on_before` | `Callable[[ToolCall], None] \| None` | `None` | Callback invoked before each tool execution. |
| `on_after` | `Callable[[ToolCall, ToolResult], None] \| None` | `None` | Callback invoked after each tool execution. |

### Key Methods

| Method | Description |
|--------|-------------|
| `register(func)` | Register a single `@tool` decorated function. Raises `ValueError` if not decorated or name conflicts. |
| `unregister(name)` | Remove a tool by name. Raises `KeyError` if not found. |
| `get_schemas() -> list[dict]` | Return OpenAI-compatible schemas for all registered tools. Pass directly to `client.complete_with_tools(tools=schemas)`. |
| `get_tool_names() -> list[str]` | Return names of all registered tools. |
| `execute(tool_call, context) -> ToolResult` | Execute a single tool call (async). Never raises -- errors become `ToolResult(is_error=True)`. |
| `execute_batch(tool_calls, context) -> list[ToolResult]` | Execute multiple tool calls concurrently via `asyncio.gather()`. Results are in the same order as input. Each call is isolated -- one failure does not affect others. |
| `execute_sync(tool_call, context) -> ToolResult` | Synchronous convenience wrapper around `execute()`. Uses `asyncio.run()`. |

---

## `ToolResult`

Every execution returns a `ToolResult` (a Pydantic model). Exceptions inside a tool are caught and returned as an error result, never propagated.

| Field | Type | Description |
|-------|------|-------------|
| `tool_call_id` | `str` | ID matching the original `ToolCall`. |
| `name` | `str` | Name of the tool that was executed. |
| `content` | `str` | Output string (JSON-serialized if structured). |
| `is_error` | `bool` | `True` if execution failed. Default `False`. |

**Example error result:**

```python
result = await executor.execute(call)
if result.is_error:
    print(result.content)
    # "Tool 'my_tool' raised ValueError: Invalid ID"
```

---

## Callbacks

Use `on_before` and `on_after` for logging, metrics, or observability. Callback exceptions are silently swallowed so they never interfere with tool execution.

```python
def on_before(tool_call: ToolCall) -> None:
    print(f"Executing: {tool_call.name}({tool_call.arguments})")

def on_after(tool_call: ToolCall, result: ToolResult) -> None:
    status = "error" if result.is_error else "ok"
    print(f"  -> {status}: {result.content[:80]}")

executor = ToolExecutor(tools=[my_tool], on_before=on_before, on_after=on_after)
```

---

## Schema Generation

Schemas are auto-generated from the function's type hints and docstring at decoration time. The output follows the OpenAI function-calling format:

```json
{
  "type": "function",
  "function": {
    "name": "get_weather",
    "description": "Get weather for a location.",
    "parameters": {
      "type": "object",
      "properties": {
        "location": { "type": "string", "description": "City name." }
      },
      "required": ["location"]
    }
  }
}
```

Supported type mappings: `str` -> `string`, `int` -> `integer`, `float` -> `number`, `bool` -> `boolean`, `list[T]` -> `array`, `dict[str, T]` -> `object`, `Literal[...]` -> `enum`, `BaseModel` -> nested `object`, `T | None` -> optional field.

---

## Built-in Tools

RawAgents ships with built-in tool suites for file-system operations and shell execution. See `src/rawagents/tools/builtin/` for the full catalogue.

---

## Error Handling

Tools should return error information as strings (e.g., `"Error: file not found"`) rather than raising exceptions. The executor catches all exceptions and wraps them as `ToolResult(is_error=True)`, but explicit error-string returns give you control over the message the LLM sees.

All tool-related exceptions inherit from `ToolError`:

| Exception | When |
|-----------|------|
| `ToolDefinitionError` | Invalid signature detected at decoration time (missing types, non-JSON params). |
| `ToolExecutionError` | Execution failure (caught by executor, converted to error result). |
| `InjectionError` | Missing context for an `Inject`-marked parameter. |
