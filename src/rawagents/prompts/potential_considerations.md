# Potential Considerations: PromptManager

This document outlines future improvements and architectural considerations for the `PromptManager` component, prioritized by impact on "Deep Agent" capabilities.

---

## 1. Context-Aware Filters (High Importance)
**Context:** Deep agents often process massive logs or search results that exceed token limits.
**Problem:** Currently, truncation logic must happen in Python code *before* rendering, or prompts will crash.
**Proposal:** Add filters to handle token/length constraints directly in the template.
*   `truncate_tokens(text, limit=1000)`: Intelligently truncates text to a token budget.
*   `summarize_list(items, max_items=5)`: Automatically limits list output.
**Benefit:** Keeps Python code clean; presentation logic stays in the template.

## 2. Chat Template Support (Medium Importance)
**Context:** Some models (like Llama 3 or certain open-weights models) are sensitive to specific chat formatting (e.g., `<|im_start|>`).
**Problem:** Currently, `render` returns a single `str`.
**Proposal:** Add `render_messages(template_name, **kwargs) -> list[dict]` which parses a rendered template (perhaps YAML/JSON structured) into a list of message objects (`system`, `user`, `assistant`).
**Benefit:** Allows complex multi-turn prompt engineering within a single template file.

## 3. Hot Reloading (Dev Experience)
**Context:** Developers iterate rapidly on prompts.
**Problem:** Changes to `.j2` files might require restarting the application depending on how the `Environment` caches templates.
**Proposal:** Add a `auto_reload=True` flag to `__init__` that clears the Jinja2 cache on every render during development.
**Benefit:** Faster "Edit -> Run -> Debug" loop for prompt engineering.

## 4. Partial Validation (Advanced)
**Context:** A workflow might want to "pre-fill" parts of a prompt (e.g., global tools) but render the rest later.
**Problem:** `StrictUndefined` raises an error if *any* variable is missing.
**Proposal:** Implement a `render_partial` method that returns a `jinja2.Template` with some context bound, allowing deferred rendering.
**Benefit:** Optimization for complex pipelines where context is gathered incrementally.

## 5. Async Rendering (Low Importance)
**Context:** Jinja2 supports `enable_async=True`.
**Problem:** Currently, rendering is synchronous.
**Proposal:** Expose `render_async` for high-throughput systems where rendering large templates might block the event loop.
**Benefit:** Marginal performance gain for massive templates; mostly relevant for extremely high-concurrency agents.

