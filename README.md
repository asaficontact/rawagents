# RawAgents: The Anti‑Framework for AI Agents

**Status:** Pre‑Alpha  
**Vision:** "Raw primitives. Maximum control."

---

## The Problem: Frameworks That Eat Your Agent

The current landscape of AI agent engineering is dominated by two extremes:

1. **Vendor Walled Gardens** – SDKs (OpenAI, Anthropic, Google, etc.) that lock you into their models, formats, and “one true way” to call their APIs.
2. **Heavy Agent Frameworks** – Libraries (LangChain, CrewAI, AutoGen, etc.) that wrap simple loops in complex abstractions: “Agents,” “Executors,” “Graphs,” “Crews.” They promise structure, but deliver:
   - Hidden control flow
   - Opaque error handling
   - Debugging nightmares when you want to do real research

They give you castles when all you wanted were **good bricks**.

**They promised to build the agent for you. Instead, they took control of the loop.**

---

## The Solution: RawAgents

**RawAgents** is a lightweight, **anti‑framework** for building agentic systems.  
It is built for **engineers and researchers** who want **raw, composable primitives** and **full control** over the loop.

We don’t give you an “Agent” class.  
We give you the **raw agents**: LLM calls, state containers, tools, and loops — wired together by you.

We reject the “Framework” label.  
We provide **Primitives**, not prescriptions.

---

## Core Philosophy

1. **State Before Execution**  
   Separate *what happened* (**State**) from *what to do next* (**Compute**).  
   Your state is explicit and serializable; your loop is just Python.

2. **No Magic, Just Loops**  
   If you can’t implement the main agent loop in ~10 lines of Python using RawAgents, we failed.  
   No background engines, no invisible “executors,” no event buses you never asked for.

3. **Raw, Provider‑Agnostic Compute**  
   We support all major providers (OpenAI, Anthropic, Google, local models) via a **thin, raw interface**.  
   No “chains.” No hard‑coded patterns. Just text‑in / struct‑out.

4. **Type‑Safe by Default**  
   Everything is **Pydantic‑first**. Configuration is code. Tool schemas, structured outputs, and state snapshots are all strongly typed, inspectable, and testable.

5. **Masterless by Design**  
   RawAgents never “owns” your process.  
   You hold the loop, the state, and the error handling. We’re a library, not your runtime.

---

## The Architecture

RawAgents breaks an agent down into **four atomic components** — no metaphors, no mega‑classes:

| Component        | Import                | Description                                         | Research Equivalent |
| :--------------- | :-------------------- | :-------------------------------------------------- | :------------------ |
| **Compute**      | `rawagents.llm`       | Raw intelligence. Stateless text-in, struct-out.    | Policy ($\pi$)      |
| **State**        | `rawagents.state`     | Short-term memory. History, context windows, forks. | State ($S_t$)       |
| **Capabilities** | `rawagents.tools`     | Tools + DI. The agent’s “hands.”                    | Action Space ($A$)  |
| **Control**      | `rawagents.loops`     | Transparent Python loops. No hidden engines.        | Control Policy      |
| **Recall**       | `rawagents.memory`    | (Coming Soon) Long‑term vector retrieval.           | Long‑term Memory    |

You can use any one of these in isolation, or compose them into full agents.

---

## Example: The “Raw” Agent Loop

This is not pseudocode. This is how you build an agent in RawAgents.

```python
from rawagents import llm, state, tools, loops
from typing import Annotated

# 1. Define Tools (The Hands)
@tools.tool
def search(query: str) -> str:
    """Search the web for the given query."""
    # ... implementation ...
    return "Results..."

@tools.tool
def get_user_profile(user_id: str, db: Annotated[object, tools.Inject]) -> dict:
    """Fetch a user profile from the database."""
    return db.get_user(user_id)

# 2. Initialize State (The Memory)
session = state.Conversation()
session.add_system("You are a concise research assistant.")
session.add_user("Find me three good resources to learn about agent frameworks.")

# 3. Build the Toolkit
executor = tools.ToolExecutor([search, get_user_profile])

# 4. Run the Loop (The Controller)
# You see the loop. You own the loop.
async for step in loops.simple(
    llm=llm.AsyncLLM(model="openai/gpt-4o"),
    conversation=session,
    tools=executor,
    config=loops.LoopConfig(max_steps=8),
):
    if step.type == "thought":
        print(f"Model thinking: {step.content}")
    elif step.type == "tool_call":
        print(f"Tool calls: {[c.name for c in step.tool_calls]}")
    elif step.type == "tool_result":
        print("Tool results:", step.tool_results)
    elif step.type == "finish":
        print("Final answer:", step.content)
```

No hidden agent engine. No executor class you never wrote.  
Just **raw primitives** wired together in your own loop.

---

## Why “RawAgents”?

- **Raw, Not Overcooked**  
  We refuse to over‑abstract. RawAgents keeps everything visible and debuggable: messages, tool calls, tokens, and control flow.

- **Agents, Not Frameworks**  
  Frameworks try to own your architecture. RawAgents just helps you build agents — whether it’s ReAct, Tree‑of‑Thought, or something nobody has named yet.

- **Primitives Over Patterns**  
  Instead of shipping a catalog of “agent types,” we give you the fundamental building blocks:
  - A robust LLM client (`rawagents.llm`)
  - A conversation/state model with branching and snapshotting (`rawagents.state`)
  - Tool definitions with dependency injection (`rawagents.tools`)
  - Async generator‑based loops (`rawagents.loops`)

- **Research‑Grade Control**  
  Need to:
  - Pause for human approval?
  - Run multiple agents in parallel and watch each step?
  - Swap out the context strategy mid‑run?
  
  All of that lives in your code, not in ours. RawAgents makes it easy — it never makes it invisible.

---

## What RawAgents Is (and Is Not)

**RawAgents *is*:**

- A set of **minimal, composable components** for:
  - LLM calls
  - Agent state
  - Tools and DI
  - Control loops
- Small enough to read in an afternoon.
- Explicit enough to use in research prototypes and production systems.

**RawAgents is *not*:**

- A workflow orchestrator or DAG engine.
- A hosted service or job runner.
- A “just call `.run()` and pray” framework.

---

## Installation

```bash
pip install git+https://github.com/tawab-safi/rawagents.git
```

---

## Roadmap (High‑Level)

- **v0.1 – Primitives Stable**
  - `rawagents.llm`: sync + async clients, structured output, tools
  - `rawagents.state`: conversation, branching, snapshots
  - `rawagents.tools`: `@tool`, `Inject`, `ToolExecutor`
  - `rawagents.loops.simple`: async generator loop with max_steps and tool support

- **v0.2 – Human‑in‑the‑Loop**
  - `rawagents.loops.interactive`: approval steps and interventions
  - Better observability on `LoopStep` (latency, token counts, cost)

- **v0.3 – Swarms & Coordination**
  - `rawagents.loops.swarm`: coordinate multiple agents in parallel
  - Basic patterns: planner/worker, supervisor/worker, multi‑expert

- **Future – Recall & Persistence**
  - `rawagents.memory`: vector recall plugged cleanly into state & loops
  - Optional storage backends for state (DBs, KV stores, object storage)

---

**RawAgents is not here to build the castle for you.  
It is here to give you the sharpest, cleanest bricks you can get — and get out of your way.**
