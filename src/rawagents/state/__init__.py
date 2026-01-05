"""Conversation component for agent memory and state management.

This module provides a "smart container" for managing conversation history,
branching, checkpointing, and context strategies for LLM interactions.

Features:
    - Canonical Data Model: Strongly-typed Pydantic models
    - Branching Support: fork()/merge() for tree-of-thought reasoning
    - State Checkpointing: snapshot()/load() for pause/resume workflows
    - Context Strategies: Pluggable logic for context window management
    - Storage Agnosticism: Swappable storage backends

Example:
    >>> from rawagents.state import Conversation
    >>> conv = Conversation()
    >>> conv.add_system("You are a helpful assistant.")
    >>> conv.add_user("Hello!")
    >>> messages = conv.get_history()  # Ready for LLM API
"""

from rawagents.state.conversation import Conversation
from rawagents.state.storage import BaseStorage, InMemoryStorage
from rawagents.state.strategies import (
    BaseStrategy,
    FullHistory,
    SlidingWindow,
)
from rawagents.state.types import (
    ContentBlock,
    Message,
    MessageMetadata,
    ToolCall,
)

__all__ = [
    # Main class
    "Conversation",
    # Types
    "ContentBlock",
    "Message",
    "MessageMetadata",
    "ToolCall",
    # Storage
    "BaseStorage",
    "InMemoryStorage",
    # Strategies
    "BaseStrategy",
    "FullHistory",
    "SlidingWindow",
]
