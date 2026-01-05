"""RAG (Retrieval Augmented Generation) component for RawAgents.

This module provides composable primitives for document chunking, embedding,
vector storage, and retrieval. Unlike monolithic RAG frameworks, each component
is a standalone primitive that can be used independently or composed together.

Core Types:
    Document: A source document before chunking.
    Chunk: A segment of a document, ready for embedding.
    SearchResult: A retrieved chunk with relevance score.

Protocols (Interfaces):
    Chunker: Protocol for document chunking strategies.
    Embedder: Protocol for text embedding.
    VectorStore: Protocol for vector storage (decoupled, general-purpose).
    Reranker: Protocol for result reranking.

Implementations:
    FixedSizeChunker: Split documents by character count with overlap.
    RecursiveChunker: Split by natural boundaries (paragraphs, sentences).
    LiteLLMEmbedder: Embedder using LiteLLM (100+ providers).
    MemoryVectorStore: In-memory vector store using NumPy.

Main Class:
    Retriever: Composes Embedder + VectorStore for RAG retrieval.

PromptManager Integration:
    format_chunk: Format a single chunk for prompt inclusion.
    format_context: Format search results as context for LLM.
    get_rag_filters: Get RAG-specific Jinja2 filters.

Example:
    >>> from rawagents.rag import (
    ...     Document, Chunk,
    ...     FixedSizeChunker, LiteLLMEmbedder, MemoryVectorStore,
    ...     Retriever,
    ... )
    >>>
    >>> # Create components
    >>> chunker = FixedSizeChunker(chunk_size=500)
    >>> embedder = LiteLLMEmbedder(model="text-embedding-3-small")
    >>> store = MemoryVectorStore()
    >>> retriever = Retriever(embedder, store)
    >>>
    >>> # Process documents
    >>> docs = [Document(content="Long text...", metadata={"source": "wiki"})]
    >>> chunks = chunker.chunk(docs)
    >>> retriever.add(chunks)
    >>>
    >>> # Retrieve
    >>> results = retriever.retrieve("What is X?", top_k=5)
"""

from rawagents.rag.chunkers import FixedSizeChunker, RecursiveChunker
from rawagents.rag.embedders import LiteLLMEmbedder
from rawagents.rag.exceptions import (
    ChunkingError,
    EmbeddingError,
    RAGError,
    RetrievalError,
    VectorStoreError,
)
from rawagents.rag.filters import format_chunk, format_context, get_rag_filters
from rawagents.rag.protocols import Chunker, Embedder, Reranker, VectorStore
from rawagents.rag.retriever import Retriever
from rawagents.rag.stores import MemoryVectorStore
from rawagents.rag.types import Chunk, Document, SearchResult

__all__ = [
    # Types
    "Document",
    "Chunk",
    "SearchResult",
    # Protocols
    "Chunker",
    "Embedder",
    "VectorStore",
    "Reranker",
    # Exceptions
    "RAGError",
    "ChunkingError",
    "EmbeddingError",
    "VectorStoreError",
    "RetrievalError",
    # Main class
    "Retriever",
    # Filters
    "format_chunk",
    "format_context",
    "get_rag_filters",
    # Implementations
    "FixedSizeChunker",
    "RecursiveChunker",
    "LiteLLMEmbedder",
    "MemoryVectorStore",
]
