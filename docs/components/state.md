# State Component (`rawagents.state`)

The state component is a **conversation and message manager** for agents – the \"operating system for context\".

It provides:

- typed message models
- a `Conversation` container with branching and checkpointing
- pluggable context strategies (e.g. sliding window)
- storage-agnostic backends

---

## Quick start

```python
from rawagents import Conversation

conv = Conversation()

conv.add_system("You are a helpful assistant.")
conv.add_user("What is the capital of France?")

messages = conv.get_history()
```

See more details in `src/rawagents/state/README.md`.


