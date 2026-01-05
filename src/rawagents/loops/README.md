# Loops Component

The transparent control logic for Unchained agents.

## Overview

The Loops Component (`unchained.loops`) orchestrates the interaction between the LLM (Brain), Conversation (State), and Tools (Hands). Unlike other frameworks that hide the execution logic inside black-box classes, Unchained uses **Generator Functions**.

This means the loop yields its status at every step, giving you:
*   **Total Visibility:** See exactly what the agent is thinking and doing in real-time.
*   **Control:** Pause, resume, or stop the loop whenever you want.
*   **Ease of Use:** Connects easily to UIs (Streamlit, React) via streaming.

---

## Quick Start

```python
import asyncio
from unchained import loops, llm, state, tools

async def main():
    # 1. Initialize Components
    brain = llm.AsyncLLM()
    memory = state.Conversation()
    toolkit = tools.ToolExecutor([my_tool])
    
    memory.add_user("Help me with...")

    # 2. Run the Loop
    # The loop is a GENERATOR. It yields control back to you.
    async for step in loops.simple(brain, memory, toolkit):
        
        if step.type == "thought":
            print(f"🤖 Thinking: {step.content}")
            
        elif step.type == "tool_call":
            print(f"🛠️ Calling: {step.tool_calls}")
            
        elif step.type == "tool_result":
            print(f"✅ Result: {step.tool_results}")
            
    print(f"🏁 Final: {memory.last_message.content}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Strategies

### 1. `simple()` - The Standard Loop
The classic ReAct pattern: `Think -> Act -> Observe -> Repeat`.
*   **Best for:** Autonomous agents, chatbots, data extraction.
*   **Behavior:** Runs until the LLM decides to stop or `max_steps` is reached.

### 2. `interactive()` - Human-in-the-Loop
Pauses execution before running tools to ask for permission.
*   **Best for:** Dangerous actions (delete file, buy stock), admin tools.
*   **Behavior:** Yields `approval_request` and waits for you to send `True` (approve) or `False` (deny) back into the generator.

```python
runner = loops.interactive(brain, memory, toolkit)

async for step in runner:
    if step.type == "approval_request":
        user_ok = input(f"Allow {step.tool_calls}? (y/n): ") == "y"
        await runner.asend(loops.ApprovalDecision(approved=user_ok))
```

---

## Configuration

Control loop behavior with the `LoopConfig` object.

```python
from unchained.loops import LoopConfig

config = LoopConfig(
    max_steps=30,           # Safety limit (default: 15)
    stop_on_error=True,     # Stop if a tool crashes (default: False)
    temperature=0.0,        # LLM temperature for this run
    tool_choice="auto"      # Force tool use or let LLM decide
)

loops.simple(..., config=config)
```

---

## Data Models

Every step yielded by the loop is a `LoopStep` Pydantic model.

| Field | Type | Description |
| :--- | :--- | :--- |
| `type` | `str` | `thought`, `tool_call`, `tool_result`, `approval_request`, `error`, `finish` |
| `content` | `str` | The text content (for thoughts/results). |
| `tool_calls` | `list[ToolCall]` | The tools the LLM wants to run. |
| `tool_results` | `list[ToolResult]` | The output of executed tools. |
| `metadata` | `dict` | Cost, latency, and token usage for this step. |

---

## Integration

The `loops` component is designed to work seamlessly with the Unchained ecosystem:
*   **State:** Automatically reads history from and writes results to `unchained.state`.
*   **Tools:** Automatically fetches schemas from `unchained.tools` (unless overridden).
*   **LLM:** Handles retries and provider abstraction via `unchained.llm`.

