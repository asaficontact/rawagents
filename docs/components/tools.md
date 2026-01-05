# Tools Component (`rawagents.tools`)

The tools component provides the **\"hands\"** of your agent:

- `@tool` decorator to turn functions into LLM-callable tools
- `Inject` marker for dependency injection
- `ToolExecutor` to execute tools safely with context

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
    schemas = executor.get_schemas()  # For LLM tool schemas
    # ... call LLM with schemas, get back a ToolCall ...
```

See `src/rawagents/tools/README.md` for details on schema generation, DI, and error handling.


