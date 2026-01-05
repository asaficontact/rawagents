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


