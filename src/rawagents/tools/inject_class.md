# The `Inject` Class

## What Problem Does It Solve?

When you define a tool for an LLM, some parameters should be decided by the LLM (like "which city to search"), while others are internal to your application (like "which database connection to use").

The LLM shouldn't see or provide internal dependencies - that's your code's responsibility.

`Inject` marks parameters that should be:
- **Hidden** from the LLM's schema
- **Provided by you** at execution time via a context dict

## Basic Usage

```python
from typing import Annotated
from rawagents.tools import tool, ToolExecutor, Inject

@tool
def search_users(
    query: str,                              # LLM provides this
    db: Annotated[Database, Inject],         # You provide this (hidden from LLM)
) -> str:
    """Search for users in the database."""
    return db.find(query)
```

**What the LLM sees:**
```json
{"name": "search_users", "parameters": {"query": {"type": "string"}}}
```

The `db` parameter is hidden.

**At execution time:**
```python
executor = ToolExecutor([search_users])

result = await executor.execute(
    tool_call,
    context={"db": my_database}  # You inject the database here
)
```

## Multiple Inject Parameters

You can inject as many parameters as needed:

```python
@tool
def create_order(
    product_id: str,                                # LLM provides
    quantity: int,                                  # LLM provides
    db: Annotated[Database, Inject],                # You inject
    logger: Annotated[Logger, Inject],              # You inject
    email_service: Annotated[EmailService, Inject], # You inject
) -> str:
    """Create a new order."""
    logger.info(f"Creating order for {product_id}")
    order = db.create_order(product_id, quantity)
    email_service.send_confirmation(order)
    return f"Order {order.id} created"
```

Provide all of them in the context:
```python
result = await executor.execute(
    tool_call,
    context={
        "db": my_database,
        "logger": my_logger,
        "email_service": my_email_service,
    }
)
```

## How It Works

```
LLM Request                    Your Code
     |                              |
     v                              v
{"query": "cats"}           context={"db": my_db}
     |                              |
     +-------------+----------------+
                   |
                   v
            ToolExecutor combines both
                   |
                   v
         search_users(query="cats", db=my_db)
```

## Error Handling

Missing context parameters return a clear error:

```python
result = await executor.execute(tool_call, context={})
# ToolResult(is_error=True, content="Missing required context: db")
```

## Common Use Cases

| Inject Parameter | Purpose |
|------------------|---------|
| Database connection | Query/update data |
| Logger | Track tool execution |
| API clients | Call external services |
| User session | Access current user info |
| Cache | Store/retrieve cached data |
| Config | Access application settings |

## Summary

- `Inject` is a marker that hides parameters from the LLM
- Use `Annotated[Type, Inject]` syntax
- Provide injected values via `context={"param_name": value}`
- Keeps LLM-facing schema clean while giving tools access to internal resources
