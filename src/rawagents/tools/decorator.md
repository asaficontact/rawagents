# The `@tool` Decorator

## What It Does

The `@tool` decorator transforms a regular Python function into a tool that can be:
- Registered with `ToolExecutor`
- Described to an LLM via JSON schema
- Executed safely with dependency injection

## Basic Usage

```python
from rawagents.tools import tool

@tool
def get_weather(location: str) -> str:
    """Get weather for a location."""
    return f"Sunny in {location}"
```

Or with custom options:

```python
@tool(name="weather", description="Fetch current weather")
def get_weather(location: str) -> str:
    return f"Sunny in {location}"
```

## What Happens When You Apply `@tool`

```
Your Function                     @tool                      Ready for ToolExecutor
      │                             │                                │
      ▼                             ▼                                ▼
def search(query: str) ───► Validate + Attach Metadata ───► search (with hidden data)
```

### Step 1: Validation (Fail Fast)

The decorator checks your function immediately:

| Check | Error If Missing |
|-------|------------------|
| Return type | `"must have a return type annotation"` |
| Parameter types | `"must have a type annotation"` |
| JSON-compatible types | `"not JSON-serializable"` |

```python
# This fails immediately when the code loads:
@tool
def bad_tool(x):  # Missing types!
    return x
# ToolDefinitionError: Parameter 'x' must have a type annotation
```

### Step 2: Find Injected Parameters

The decorator identifies which parameters use `Annotated[T, Inject]`:

```python
@tool
def search(
    query: str,                          # LLM provides → included in schema
    db: Annotated[Database, Inject],     # You provide → excluded from schema
) -> str:
    ...
```

### Step 3: Generate JSON Schema

Creates an OpenAI-compatible schema, hiding injected parameters:

```python
# For the search function above, the schema is:
{
    "type": "function",
    "function": {
        "name": "search",
        "description": "...",
        "parameters": {
            "properties": {"query": {"type": "string"}},
            "required": ["query"]
        }
    }
}
# Note: "db" is not in the schema!
```

### Step 4: Attach Metadata

The decorator attaches hidden attributes to your function:

| Attribute | Purpose |
|-----------|---------|
| `__tool_name__` | Name for registration |
| `__tool_description__` | Description for LLM |
| `__tool_schema__` | The JSON schema |
| `__tool_is_async__` | Whether to await |
| `__tool_injected_params__` | Parameters needing injection |
| `__tool_original_func__` | The actual function to call |

## JSON-Compatible Types

Parameters the LLM provides must be JSON-serializable:

| Allowed Type | Example |
|--------------|---------|
| `str` | `"hello"` |
| `int` | `42` |
| `float` | `3.14` |
| `bool` | `True` |
| `list[T]` | `["a", "b"]` |
| `dict[str, T]` | `{"key": "value"}` |
| `Literal["a", "b"]` | `"a"` |
| Pydantic models | `UserInput(name="...")` |

Non-JSON types require `Inject`:

```python
# Wrong - Database is not JSON-serializable
@tool
def query(db: Database) -> str:  # ToolDefinitionError!
    ...

# Correct - Mark it for injection
@tool
def query(db: Annotated[Database, Inject]) -> str:
    ...
```

## Async Support

The decorator automatically detects async functions:

```python
@tool
async def fetch_data(url: str) -> str:
    """Fetch data from URL."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()

# fetch_data.__tool_is_async__ == True
```

The `ToolExecutor` uses this to know whether to `await` the function.

## Decorator Syntax Options

Both styles work:

```python
# Without parentheses - uses function name and docstring
@tool
def my_tool(x: str) -> str:
    """This becomes the description."""
    return x

# With parentheses - custom name and description
@tool(name="custom_name", description="Custom description")
def my_tool(x: str) -> str:
    """This docstring is ignored."""
    return x
```

## Function Still Works Normally

After decorating, you can still call the function directly:

```python
@tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

# Works normally:
result = add(2, 3)  # Returns 5

# Also works with ToolExecutor:
executor = ToolExecutor([add])
```

## Complete Flow Example

```python
from typing import Annotated
from rawagents.tools import tool, ToolExecutor, Inject

# 1. Define with @tool
@tool
def search_users(
    query: str,
    limit: int = 10,
    db: Annotated[Database, Inject],
) -> str:
    """Search for users in the database."""
    return db.find_users(query, limit)

# 2. Decorator validates and attaches metadata
#    - Checks types ✓
#    - Finds injected params: {"db"}
#    - Generates schema (query, limit only)

# 3. Register with executor
executor = ToolExecutor([search_users])

# 4. Get schema for LLM
schemas = executor.get_schemas()
# [{"type": "function", "function": {"name": "search_users", ...}}]

# 5. Execute with injection
result = await executor.execute(
    tool_call,
    context={"db": my_database}
)
```

## Error Messages

The decorator provides clear error messages:

```python
# Missing return type
@tool
def bad(x: str):  # No -> Type
    return x
# ToolDefinitionError: Tool 'bad' must have a return type annotation.
# Add '-> ReturnType' to the function signature.

# Missing parameter type
@tool
def bad(x) -> str:  # x has no type
    return x
# ToolDefinitionError: Parameter 'x' in tool 'bad' must have a type annotation.

# Non-JSON type without Inject
@tool
def bad(db: Database) -> str:
    return "ok"
# ToolDefinitionError: Parameter 'db' in tool 'bad' has type 'Database'
# which is not JSON-serializable. Use Annotated[Database, Inject]...
```

## Summary

The `@tool` decorator:
1. **Validates** your function signature immediately (fail fast)
2. **Identifies** which parameters need injection
3. **Generates** an OpenAI-compatible JSON schema
4. **Attaches** metadata for `ToolExecutor` to use
5. **Preserves** normal function behavior
