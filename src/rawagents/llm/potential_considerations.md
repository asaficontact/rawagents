# Potential Considerations

Future enhancements to consider based on usage patterns.

---

## Add `temperature`, `reasoning_effort`, `max_tokens` to Config

**Status:** Deferred

**Context:** Currently these parameters are only available per-call with hardcoded defaults (`temperature=0.7`, others `None`). Users who want consistent values must repeat them on every call.

**Current Design Rationale:**
- Config holds **infrastructure concerns** (model, retries, timeout, fallbacks)
- Per-call params are **request semantics** (temperature, reasoning_effort, max_tokens)
- Keeps config simple and avoids scope creep
- Explicitness in calls makes behavior clear when reading code

**When to Reconsider:**
- Multiple users request "set once, use everywhere" for these params
- Common patterns emerge (e.g., always `temperature=0` for structured output pipelines)

**Implementation if Needed:**
```python
@dataclass
class LLMConfig:
    # ... existing fields ...
    temperature: float | None = None  # None = use method default (0.7)
    reasoning_effort: Literal["low", "medium", "high"] | None = None
    max_tokens: int | None = None
```

Methods would then use: `temperature = temperature if temperature is not None else self.config.temperature or 0.7`
