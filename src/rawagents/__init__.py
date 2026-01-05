"""RawAgents - Raw primitives. Maximum control.

This library provides atomic building blocks for AI systems:
    - llm: Compute (LLM clients)
    - state: State (Conversation memory)
    - tools: Capabilities (Tool execution)
    - loops: Control (Agent loops)
    - prompts: Presentation (Prompt management)
    - rag: Knowledge (Retrieval Augmented Generation)

Example:
    >>> from rawagents import LLMClient, Conversation, loops
    >>> client = LLMClient()
    >>> conv = Conversation()
    >>> async for step in loops.simple(client, conv, tools):
    ...     print(step.content)
"""

from rawagents.state import (
    Conversation,
    FullHistory,
    Message,
    MessageMetadata,
    SlidingWindow,
)
from rawagents.llm import (
    LLM,
    AsyncLLM,
    LLMClient,
    AsyncLLMClient,
    LLMConfig,
    LLMResponse,
    ToolCall,
    ToolResponse,
)
from rawagents.prompts import (
    PromptError,
    PromptManager,
    PromptRenderingError,
    TemplateConfigError,
    TemplateNotFoundError,
)
from rawagents.tools import (
    Inject,
    ToolExecutor,
    ToolResult,
    tool,
)

# Import loops as a module for namespace access (loops.simple, loops.interactive)
from rawagents import loops
from rawagents.loops import (
    ApprovalDecision,
    LoopCancelledError,
    LoopConfig,
    LoopError,
    LoopStep,
    MaxStepsExceededError,
)
from rawagents.rag import (
    # Types
    Chunk,
    Document,
    SearchResult,
    # Protocols
    Chunker,
    Embedder,
    Reranker,
    VectorStore,
    # Main class
    Retriever,
    # Implementations
    FixedSizeChunker,
    LiteLLMEmbedder,
    MemoryVectorStore,
    RecursiveChunker,
    # Filters
    format_chunk,
    format_context,
    get_rag_filters,
)


__version__ = "0.1.0"

__all__ = [
    # LLM Client (short names)
    "AsyncLLM",
    "LLM",
    # LLM Client (aliases)
    "AsyncLLM",
    "LLM",
    # LLM Client (aliases)
    "AsyncLLMClient",
    "LLMClient",
    # LLM types
    "LLMConfig",
    "LLMResponse",
    "ToolCall",
    "ToolResponse",
    # Conversation
    "Conversation",
    "FullHistory",
    "Message",
    "MessageMetadata",
    "SlidingWindow",
    # Tools
    "Inject",
    "ToolExecutor",
    "ToolResult",
    "tool",
    # Prompts
    "PromptError",
    "PromptManager",
    "PromptRenderingError",
    "TemplateConfigError",
    "TemplateNotFoundError",
    # Loops
    "loops",
    "ApprovalDecision",
    "LoopCancelledError",
    "LoopConfig",
    "LoopError",
    "LoopStep",
    "MaxStepsExceededError",
    # RAG Types
    "Chunk",
    "Document",
    "SearchResult",
    # RAG Protocols
    "Chunker",
    "Embedder",
    "Reranker",
    "VectorStore",
    # RAG Main class
    "Retriever",
    # RAG Implementations
    "FixedSizeChunker",
    "LiteLLMEmbedder",
    "MemoryVectorStore",
    "RecursiveChunker",
    # RAG Filters
    "format_chunk",
    "format_context",
    "get_rag_filters",
]
