# LLM Client

A unified interface for 100+ LLM providers with structured output and tool calling support.

## Quick Start

```bash
pip install git+https://github.com/tawab-safi/ai-components.git
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk...
export GEMINI_API_KEY=AIza...
```

```python
from ai_components import LLMClient

# Simple initialization with defaults
client = LLMClient()

# Or configure inline with kwargs
client = LLMClient(model="openai/gpt-4o", timeout=120)

response = client.complete(
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.content)
```

---

## Methods

### `complete()` — Basic Text Completion

**Technology:** LiteLLM direct call

Returns text responses from any supported provider.

```python
response = client.complete(
    messages=[{"role": "user", "content": "What is 2+2?"}],
    model="openai/gpt-4o",      # Optional, uses config default
    temperature=0.7,             # 0.0-2.0
    max_tokens=100,              # Optional limit
    reasoning_effort="medium",   # Optional: "low", "medium", "high" (o1/o3/Claude 3.7+)
    metadata={"user_id": "123"}, # Optional logging metadata
)
# Returns: LLMResponse(content, model, usage, cost, latency_ms, ...)
```

---

### `complete_structured()` — Pydantic Extraction

**Technology:** [Instructor](https://python.useinstructor.com/) + LiteLLM

Extracts validated Pydantic models from LLM responses. Automatically retries on validation failure.

```python
from pydantic import BaseModel

class Person(BaseModel):
    name: str
    age: int

person = client.complete_structured(
    messages=[{"role": "user", "content": "John is 30 years old"}],
    response_model=Person,
    temperature=0.7,             # Optional
    reasoning_effort="medium",   # Optional: "low", "medium", "high"
)
# Returns: Person(name="John", age=30)

# With metadata (for cost/usage tracking):
person, metadata = client.complete_structured(..., include_metadata=True)
# Returns: tuple[Person, LLMResponse]
```

**Why Instructor?** Provides automatic JSON schema injection, response parsing, and validation retry logic with error feedback to the LLM.

---

### `complete_with_tools()` — Tool/Function Calling

**Technology:** LiteLLM direct call with Pydantic→OpenAI schema conversion

Returns tool call *requests* — the client does NOT execute tools.

```python
from pydantic import BaseModel, Field

class GetWeather(BaseModel):
    """Get current weather."""
    location: str = Field(description="City, State")

response = client.complete_with_tools(
    messages=[{"role": "user", "content": "Weather in NYC?"}],
    tools=[GetWeather],
    tool_choice="auto",          # "auto", "required", or "none"
    temperature=0.7,             # Optional
    max_tokens=100,              # Optional
    reasoning_effort="medium",   # Optional
)
# Returns: ToolResponse with tool_calls list

for tc in response.tool_calls:
    print(tc.name, tc.arguments)  # "GetWeather", {"location": "NYC"}
    # YOU execute the tool and continue the conversation
```

**Structured Responses via Tools:** Include a "FinalAnswer" tool for structured final responses:

```python
class FinalAnswer(BaseModel):
    """Return when ready to answer."""
    answer: str
    confidence: float

response = client.complete_with_tools(
    messages=[...],
    tools=[GetWeather, SearchWeb, FinalAnswer],  # Response model as tool
)
```

---

### `stream()` — Streaming Text

**Technology:** LiteLLM streaming

Yields text chunks as they arrive. Does NOT support tools or structured output.

```python
for chunk in client.stream(
    messages=[{"role": "user", "content": "Write a story..."}],
    model="openai/gpt-4o",       # Optional
    temperature=0.7,             # Optional
    max_tokens=100,              # Optional
):
    print(chunk, end="", flush=True)
# Yields: str chunks
```

---

## Reasoning Models

For reasoning models (OpenAI o1/o3/o4/gpt-5, Anthropic Claude 3.7+, Gemini 2.5+), use the `reasoning_effort` parameter to control reasoning depth:

```python
response = client.complete(
    model="openai/o3-mini",
    messages=[{"role": "user", "content": "Solve this complex problem..."}],
    reasoning_effort="high",  # "low", "medium", or "high"
)

# Access the model's reasoning process
print(response.reasoning_content)  # "Let me think step by step..."
print(response.reasoning_blocks)   # Provider-specific reasoning blocks
```

**Default Behavior:** When `reasoning_effort` is not specified, reasoning models default to `"medium"`. The model will still reason — this parameter controls *how much* reasoning, not *whether* to reason.

**LiteLLM Unified Mapping:** The parameter is automatically mapped to provider-specific parameters:

| `reasoning_effort` | OpenAI | Anthropic `budget_tokens` | Gemini `budget_tokens` |
|-------------------|--------|---------------------------|------------------------|
| `"low"` | `"low"` | 1,024 | 1,024 |
| `"medium"` (default) | `"medium"` | 2,048 | 2,048 |
| `"high"` | `"high"` | 4,096 | 4,096 |

Supported on: `complete()`, `complete_structured()`, `complete_with_tools()`.

---

## Configuration

Initialize directly with kwargs (simplest):

```python
from ai_components import LLMClient

client = LLMClient(
    model="openai/gpt-4o",                    # Default model
    retries=3,                                 # API retries (429, 5xx)
    structured_validation_retries=3,           # Pydantic validation retries
    timeout=60,                                # Request timeout (seconds)
    fallbacks=["anthropic/claude-3-5-sonnet-latest"],
)
```

Or use a config object (useful for sharing settings):

```python
from ai_components import LLMConfig, LLMClient

config = LLMConfig(
    model="openai/gpt-4o",
    retries=3,
    fallbacks=["anthropic/claude-3-5-sonnet-latest"],
)

# Create multiple clients with same config
client1 = LLMClient(config=config)
client2 = LLMClient(config=config, timeout=120)  # kwargs override config
```

---

## Response Types

```python
@dataclass
class LLMResponse:
    content: str                        # Response text
    model: str                          # Model that responded
    usage: dict[str, int]               # {prompt_tokens, completion_tokens, total_tokens}
    cost: float | None                  # USD cost estimate
    latency_ms: float                   # Request latency
    raw_response: Any                   # Original LiteLLM response
    reasoning_content: str | None       # Model's reasoning text (reasoning models only)
    reasoning_blocks: list[dict] | None # Provider-specific reasoning blocks

@dataclass
class ToolCall:
    id: str                   # For follow-up messages
    name: str                 # Tool name
    arguments: dict[str, Any] # Parsed arguments

@dataclass
class ToolResponse(LLMResponse):
    tool_calls: list[ToolCall]  # Empty if no tools called
```

---

## Async Client

```python
from ai_components import AsyncLLMClient

# Same initialization options as LLMClient
client = AsyncLLMClient(model="openai/gpt-4o", timeout=120)

response = await client.complete(...)
person = await client.complete_structured(...)
response = await client.complete_with_tools(...)
async for chunk in client.stream(...): ...
```

---

## Exception Handling

All methods raise LiteLLM exceptions (OpenAI-style):

```python
from litellm.exceptions import (
    RateLimitError,           # 429
    AuthenticationError,      # 401
    BadRequestError,          # 400
    Timeout,
    APIConnectionError,
    ServiceUnavailableError,  # 503
)
```

---

## Architecture Summary

| Method | Backend | Use Case |
|--------|---------|----------|
| `complete()` | LiteLLM | Basic chat/completion |
| `complete_structured()` | Instructor + LiteLLM | Data extraction with validation |
| `complete_with_tools()` | LiteLLM | Agentic tool use |
| `stream()` | LiteLLM | Real-time text streaming |

**Design principle:** The client is stateless and side-effect free. It does not execute tools, manage conversation history, or run agent loops.
