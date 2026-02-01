# LLM Component (`rawagents.llm`)

The LLM component provides **stateless, provider-agnostic clients** for talking to 100+ models via [LiteLLM](https://github.com/BerriAI/litellm) and [Instructor](https://python.useinstructor.com/).

It focuses on:

- unified access to chat / reasoning models
- structured output with Pydantic
- tool / function calling
- streaming text

It deliberately does **not** manage conversation state, tools, or loops – those are handled by other RawAgents components.

---

## Quick start

```python
from rawagents import LLM, AsyncLLM

# Sync client
client = LLM(model="openai/gpt-4o", timeout=60)

response = client.complete(
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.content)

# Async client
async_client = AsyncLLM(model="openai/gpt-4o", timeout=60)
```

See the full README in `src/rawagents/llm/README.md` for detailed API docs.

---

## Response Types

### LLMResponse

Standard response from completion calls.

| Field | Type | Description |
|-------|------|-------------|
| `content` | `str` | The text content of the response. Empty string if no text (e.g., tool-only response). |
| `model` | `str` | The model identifier that generated the response (e.g., `"gpt-4o-2024-05-13"`). |
| `usage` | `dict[str, int]` | Token usage statistics: `prompt_tokens`, `completion_tokens`, `total_tokens`. |
| `cost` | `float \| None` | Estimated cost in USD (from LiteLLM). `None` if cost tracking unavailable. |
| `latency_ms` | `float` | Request latency in milliseconds. |
| `raw_response` | `Any` | The original LiteLLM response object for advanced use cases. |
| `reasoning_content` | `str \| None` | The model's reasoning/thinking text (for reasoning models). `None` if not enabled. |
| `reasoning_blocks` | `list[dict] \| None` | Provider-specific reasoning blocks (e.g., Anthropic thinking_blocks). |

**Example:**
```python
response = client.complete(messages=[{"role": "user", "content": "Hello!"}])
print(f"Response: {response.content}")
print(f"Model: {response.model}")
print(f"Cost: ${response.cost:.4f}")
print(f"Tokens: {response.usage['total_tokens']}")
print(f"Latency: {response.latency_ms:.0f}ms")
```

### ToolResponse

Response that includes tool call requests. Inherits all fields from `LLMResponse`.

| Field | Type | Description |
|-------|------|-------------|
| `tool_calls` | `list[ToolCall]` | List of tool calls the model wants to execute. Empty list if no tools requested. |

**Example:**
```python
response = client.complete_with_tools(
    messages=[{"role": "user", "content": "What's the weather in NYC?"}],
    tools=[GetWeather]
)

for tc in response.tool_calls:
    print(f"Call: {tc.name}({tc.arguments})")
```

---

## Reasoning Models

The LLM client supports **reasoning models** that expose their chain-of-thought process. These models include:

| Provider | Models | Notes |
|----------|--------|-------|
| OpenAI | `o1`, `o1-mini`, `o3-mini` | Extended thinking with `reasoning_effort` |
| Anthropic | Claude 3.7+ (Sonnet/Opus) | Thinking blocks via `thinking_blocks` |
| Google | Gemini 2.5+ | Extended thinking support |

### Using reasoning_effort

The `reasoning_effort` parameter controls how much "thinking" the model does before responding.

| Value | Description | Use Case |
|-------|-------------|----------|
| `"low"` | Quick reasoning, minimal depth | Simple queries, fast responses |
| `"medium"` | Balanced reasoning | General problem-solving |
| `"high"` | Deep reasoning, thorough analysis | Complex math, code review, multi-step problems |

**Example: Basic reasoning**
```python
response = client.complete(
    model="openai/o3-mini",
    messages=[{"role": "user", "content": "Solve: If 2x + 5 = 13, what is x?"}],
    reasoning_effort="medium"
)

print(f"Answer: {response.content}")
print(f"Reasoning: {response.reasoning_content}")
```

**Example: With structured output**
```python
class MathSolution(BaseModel):
    answer: float
    steps: list[str]

solution, metadata = client.complete_structured(
    model="openai/o3-mini",
    messages=[{"role": "user", "content": "Solve: 3x^2 - 12 = 0"}],
    response_model=MathSolution,
    reasoning_effort="high",
    include_metadata=True
)

print(f"Answer: {solution.answer}")
print(f"Reasoning: {metadata.reasoning_content}")
```

**Example: With tool calling**
```python
response = client.complete_with_tools(
    model="openai/o3-mini",
    messages=[{"role": "user", "content": "Calculate the area of a 5x3 rectangle"}],
    tools=[CalculateArea],
    reasoning_effort="low"
)

# Access reasoning alongside tool calls
if response.reasoning_content:
    print(f"Model's reasoning: {response.reasoning_content}")
```

### Provider-Specific Behavior

**OpenAI (o1/o3):**
- `reasoning_content` contains the full chain-of-thought
- `reasoning_blocks` is typically `None`

**Anthropic (Claude 3.7+):**
- `reasoning_content` may be `None`
- `reasoning_blocks` contains structured thinking blocks:
  ```python
  [
      {"type": "thinking", "text": "Let me analyze..."},
      {"type": "thinking", "text": "The key insight is..."}
  ]
  ```

**Note:** Not all models support `reasoning_effort`. If passed to a non-reasoning model, LiteLLM will ignore it or raise an error depending on the provider.

