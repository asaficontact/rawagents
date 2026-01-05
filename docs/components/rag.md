# RAG Component (`rawagents.rag`)

**Version:** 0.1
**Date:** December 2024
**Status:** Partially implemented (MVP shipped); remaining items are marked as **Planned**
**Package:** `rawagents.rag`

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Background & Motivation](#2-background--motivation)
3. [Goals & Non-Goals](#3-goals--non-goals)
4. [Technical Architecture](#4-technical-architecture)
5. [Core Types](#5-core-types)
6. [Protocols (Contracts)](#6-protocols-contracts)
7. [Implementations](#7-implementations)
8. [PromptManager Integration](#8-promptmanager-integration)
9. [Usage Patterns](#9-usage-patterns)
10. [Project Structure](#10-project-structure)
11. [Component Interactions](#11-component-interactions)
12. [Implementation Roadmap](#12-implementation-roadmap)
13. [Testing Strategy](#13-testing-strategy)
14. [Future Extensibility](#14-future-extensibility)

---

## 1. Executive Summary

### 1.1 What We're Building

The **RAG Component** (`rawagents.rag`) provides the **"knowledge"** primitives for agents—the ability to retrieve relevant information from external sources before or during LLM interactions.

Unlike monolithic RAG frameworks (LangChain, LlamaIndex), `rawagents.rag` follows our core philosophy of **"Primitives over Frameworks"**:

- **Chunkers**: Split documents into retrievable units
- **Embedders**: Convert text to vector representations
- **VectorStores**: Store and search vectors (completely decoupled)
- **Retrievers**: Compose embedder + store for document retrieval

Each component is a **standalone primitive** that can be used independently or composed together. The VectorStore is intentionally decoupled—it's a general-purpose storage primitive, not RAG-specific.

### 1.2 Key Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Architecture** | Protocols + Implementations | Users can swap any component. We provide defaults, they bring their own. |
| **VectorStore** | Decoupled Primitive | Vector stores have uses beyond RAG (caching, deduplication). Keep it general. |
| **Context Formatting** | PromptManager Responsibility | Formatting retrieved context is a presentation concern. RAG provides filters for PromptManager. |
| **Embeddings** | LiteLLM + SentenceTransformers | LiteLLM already in codebase (100+ providers). Optional local embeddings via sentence-transformers. |
| **Async** | Async-First | Embedding APIs are I/O bound. Async is essential for production. |
| **Dependencies** | Minimal Core | Core needs only `numpy`. ChromaDB, sentence-transformers are optional extras. |

### 1.3 Core Principle

**"Retrieval is Separate from Presentation"**: The RAG module finds relevant chunks and returns structured data. How that data is formatted for the LLM is handled by `PromptManager` templates.

### 1.4 Implementation Status (summary)

- **Implemented (MVP)**  
  - **Core types**: `Document`, `Chunk`, `SearchResult`
  - **Protocols**: `Chunker`, `Embedder`, `VectorStore`, `Reranker` (interface only; no built-in rerankers yet)
  - **Chunkers**: `FixedSizeChunker`, `RecursiveChunker`
  - **Embedders**: `LiteLLMEmbedder` (LiteLLM-based remote embeddings)
  - **VectorStore**: `MemoryVectorStore` (NumPy-based, cosine similarity, metadata filters)
  - **Retriever**: `Retriever` with `add` / `aadd`, `retrieve` / `aretrieve`, `delete`, length, optional reranker hook
  - **PromptManager integration**: `format_chunk`, `format_context`, `get_rag_filters`

- **Planned (not yet implemented in `src/rawagents/rag` at this time)**  
  - Additional chunkers such as `SemanticChunker`
  - Local embeddings via `SentenceTransformerEmbedder`
  - Persistent / external stores such as `ChromaVectorStore`
  - Concrete rerankers such as `CrossEncoderReranker`
  - Helper APIs for parent-document expansion and richer retrieval strategies (e.g. hybrid retrievers)
  - Query transformers, evaluation utilities, and streaming ingestion (see [Future Extensibility](#14-future-extensibility))

---

## 2. Background & Motivation

### 2.1 Problem Statement

1. **Monolithic Frameworks**: Existing RAG libraries bundle everything together. Want to swap ChromaDB for Qdrant? Good luck untangling the dependencies.

2. **Vendor Lock-in**: Many RAG solutions are tightly coupled to specific vector databases or embedding providers.

3. **Hidden Complexity**: "Just call `index.query()`" hides critical decisions about chunking, retrieval, and context formatting that dramatically affect quality.

4. **No Composability**: Can't easily use RAG as a tool, as a pre-processing step, or in custom workflows without framework buy-in.

### 2.2 Solution Strategy

We decompose RAG into atomic, protocol-based primitives:

```
Document → Chunker → Chunks → Embedder → Vectors → VectorStore
                                                         ↓
                              Query → Embedder → Vector → Search → Results
                                                                      ↓
                                                        PromptManager → LLM
```

Each arrow is a **function call with typed inputs and outputs**. No hidden state, no magic.

### 2.3 Research Foundation

This design is informed by extensive research into production RAG best practices:

- **Chunking**: NVIDIA 2024 benchmarks show up to 9% recall difference between strategies
- **Hybrid Search**: Combining vector + keyword search improves nDCG significantly
- **Reranking**: Two-stage retrieval (retrieve many, rerank few) is industry standard
- **Context Formatting**: Prompt structure can completely change RAG system behavior
- **Metadata Filtering**: One of the "easiest ways to improve retrieval quality"

---

## 3. Goals & Non-Goals

### 3.1 Goals

**G1: Maximum Composability**
- Every component implements a Protocol
- Users can bring their own implementations
- Mix and match: OpenAI embeddings + Qdrant store + custom reranker

**G2: Decoupled VectorStore**
- VectorStore is a standalone primitive
- Usable for RAG, caching, semantic deduplication, etc.
- No RAG-specific logic in the store itself

**G3: Production-Ready Defaults**
- MemoryVectorStore for development (zero dependencies)
- LiteLLMEmbedder for any provider (OpenAI, Cohere, Voyage, etc.)
- Sensible chunking defaults based on research

**G4: PromptManager Integration**
- RAG provides Jinja2 filters for context formatting
- Templates control presentation, not Python code
- Maximum flexibility without code changes

**G5: Async-First**
- All I/O operations (embedding, search) are async
- Sync wrappers provided for simple scripts
- Batch processing with configurable concurrency

### 3.2 Non-Goals

**NG1: Document Loaders**
- We do NOT provide PDF parsers, web scrapers, etc.
- Document loading is too varied to abstract well
- Users load documents however they want, pass us `Document` objects

**NG2: Full-Text Search Engine**
- We provide vector search, not Elasticsearch
- Hybrid search composes with external keyword searchers
- BM25 implementations are out of scope for v1

**NG3: Streaming Ingestion**
- Real-time Kafka/Kinesis ingestion is out of scope
- Focus on batch indexing with incremental updates
- Users can build streaming on top of our primitives

**NG4: Automatic Evaluation**
- No built-in RAGAS/evaluation metrics
- Evaluation is a separate concern
- May add optional evaluation utilities later

---

## 4. Technical Architecture

### 4.1 High-Level Design

```
┌─────────────────────────────────────────────────────────────────────┐
│                           User Code                                  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          │                         │                         │
          ▼                         ▼                         ▼
┌─────────────────┐    ┌─────────────────────┐    ┌──────────────────┐
│    Chunker      │    │     Retriever       │    │   PromptManager  │
│   (Protocol)    │    │   (Composer Class)  │    │  + RAG Filters   │
│                 │    │                     │    │                  │
│ • FixedSize     │    │ Embedder + Store    │    │ • format_context │
│ • Recursive     │    │ + Optional Reranker │    │ • format_chunk   │
│ • Semantic      │    │                     │    │                  │
└─────────────────┘    └──────────┬──────────┘    └──────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
                    ▼                           ▼
          ┌─────────────────┐         ┌─────────────────┐
          │    Embedder     │         │   VectorStore   │
          │   (Protocol)    │         │   (Protocol)    │
          │                 │         │                 │
          │ • LiteLLM       │         │ • Memory        │
          │ • Sentence      │         │ • Chroma        │
          │   Transformers  │         │ • (User's own)  │
          └─────────────────┘         └─────────────────┘
```

### 4.2 Data Flow: Indexing

```python
# 1. User creates documents (we don't handle loading)
docs = [Document(content="...", metadata={"source": "file.pdf"})]

# 2. Chunker splits into retrievable units
chunks = chunker.chunk(docs)  # → list[Chunk]

# 3. Retriever embeds and stores
await retriever.aadd(chunks)  # Embedder → VectorStore
```

### 4.3 Data Flow: Retrieval

```python
# 1. User queries
results = await retriever.aretrieve("What is X?", top_k=5)  # → list[SearchResult]

# 2. PromptManager formats for LLM
prompt = manager.render("rag.j2", results=results, query="What is X?")

# 3. LLM generates response
response = await llm.complete(messages=[{"role": "user", "content": prompt}])
```

### 4.4 Data Flow: RAG as Tool

```python
@tool
async def search_docs(
    query: str,
    retriever: Annotated[Retriever, Inject],
) -> str:
    """Search knowledge base for relevant information."""
    results = await retriever.aretrieve(query, top_k=5)
    return "\n---\n".join(r.chunk.content for r in results)

# Tool is injected into agent loop
executor = ToolExecutor([search_docs])
context = {"retriever": my_retriever}

async for step in loops.simple(llm, conv, executor, context=context):
    ...
```

---

## 5. Core Types

### 5.1 Document

The input to the chunking process. Represents a source document before splitting.

```python
from pydantic import BaseModel, Field
from typing import Any
import uuid

class Document(BaseModel):
    """A source document before chunking.

    Attributes:
        content: The full text content of the document.
        metadata: Arbitrary metadata (source, author, date, etc.).
        id: Unique identifier. Auto-generated if not provided.
    """
    content: str = Field(description="The full text content of the document")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary metadata (source, author, date, etc.)",
    )
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier. Auto-generated if not provided.",
    )
```

### 5.2 Chunk

A segment of a document, ready for embedding and retrieval.

```python
class Chunk(BaseModel):
    """A chunk of a document, ready for embedding.

    Attributes:
        content: The text content of the chunk.
        metadata: Inherited from document + chunk-specific metadata.
        document_id: Reference to the source document.
        id: Unique identifier for this chunk.
        position: Position within the document (for context expansion).
    """
    content: str = Field(description="The text content of the chunk")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Inherited from document + chunk-specific metadata",
    )
    document_id: str | None = Field(
        default=None,
        description="Reference to the source document",
    )
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this chunk",
    )
    position: int | None = Field(
        default=None,
        description="Position within the document (0-indexed)",
    )
```

### 5.3 SearchResult

A retrieved chunk with relevance score.

```python
class SearchResult(BaseModel):
    """A retrieved chunk with relevance score.

    Attributes:
        chunk: The retrieved chunk.
        score: Relevance score (higher = more relevant).
            Score semantics depend on the vector store (cosine similarity, L2, etc.).
    """
    chunk: Chunk = Field(description="The retrieved chunk")
    score: float = Field(
        description="Relevance score (higher = more relevant)",
    )
```

---

## 6. Protocols (Contracts)

All protocols use `typing.Protocol` with `@runtime_checkable` for duck typing.

### 6.1 Chunker Protocol

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Chunker(Protocol):
    """Protocol for document chunking strategies.

    Chunkers split documents into smaller units for embedding and retrieval.
    Different strategies trade off between retrieval precision and context preservation.
    """

    def chunk(self, documents: list[Document]) -> list[Chunk]:
        """Split documents into chunks.

        Args:
            documents: Source documents to chunk.

        Returns:
            List of chunks with preserved metadata and position tracking.
        """
        ...
```

### 6.2 Embedder Protocol

```python
@runtime_checkable
class Embedder(Protocol):
    """Protocol for text embedding.

    Embedders convert text into dense vector representations
    for semantic similarity search.
    """

    @property
    def dimension(self) -> int:
        """The dimensionality of output embeddings."""
        ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts synchronously.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors (same length as texts).
        """
        ...

    async def aembed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts asynchronously.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors (same length as texts).
        """
        ...
```

### 6.3 VectorStore Protocol

The VectorStore is **intentionally minimal and decoupled**. It knows nothing about chunks or documents—only vectors, IDs, and metadata.

```python
@runtime_checkable
class VectorStore(Protocol):
    """Protocol for vector storage and similarity search.

    This is a general-purpose vector storage primitive, NOT RAG-specific.
    It can be used for semantic search, caching, deduplication, etc.

    The Retriever class composes an Embedder + VectorStore for RAG use cases.
    """

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        metadata: list[dict[str, Any]] | None = None,
    ) -> None:
        """Add vectors to the store.

        Args:
            ids: Unique identifiers for each vector.
            embeddings: Vector embeddings to store.
            metadata: Optional metadata for each vector.
        """
        ...

    def search(
        self,
        embedding: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
        score_threshold: float | None = None,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        """Search for similar vectors.

        Args:
            embedding: Query vector.
            top_k: Maximum number of results.
            filters: Optional metadata filters.
            score_threshold: Minimum score threshold.

        Returns:
            List of (id, score, metadata) tuples, sorted by score descending.
        """
        ...

    def delete(self, ids: list[str]) -> None:
        """Delete vectors by ID.

        Args:
            ids: IDs of vectors to delete.
        """
        ...
```

### 6.4 Reranker Protocol

```python
@runtime_checkable
class Reranker(Protocol):
    """Protocol for result reranking.

    Rerankers re-score search results using more expensive models
    for improved precision. Typically used in two-stage retrieval:
    1. Fast retrieval of top-N candidates
    2. Reranking to select final top-K results
    """

    def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Rerank search results.

        Args:
            query: The original search query.
            results: Initial search results to rerank.
            top_k: Number of results to return after reranking.

        Returns:
            Reranked results, sorted by new scores.
        """
        ...

    async def arerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Async version of rerank."""
        ...
```

---

## 7. Implementations

### 7.1 Chunkers

#### 7.1.1 FixedSizeChunker

Simple, predictable chunking by character/token count.  
**Status:** Implemented in `chunkers/fixed.py`.

```python
class FixedSizeChunker:
    """Split documents into fixed-size chunks with overlap.

    Best for: Homogeneous content (news articles, blog posts).
    Trade-off: May split mid-sentence, but predictable behavior.

    Args:
        chunk_size: Target size per chunk (characters).
        chunk_overlap: Overlap between consecutive chunks.
        length_function: Function to measure text length.
            Default is len() for characters. Use tiktoken for tokens.
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        length_function: Callable[[str], int] = len,
    ) -> None: ...

    def chunk(self, documents: list[Document]) -> list[Chunk]: ...
```

#### 7.1.2 RecursiveChunker

Respects natural text boundaries (paragraphs, sentences).  
**Status:** Implemented in `chunkers/recursive.py`.

```python
class RecursiveChunker:
    """Split by natural boundaries, falling back to smaller separators.

    Tries separators in order: paragraphs → sentences → words → characters.
    Produces semantically coherent chunks that respect document structure.

    Best for: Structured documents (reports, documentation).
    Trade-off: Variable chunk sizes, slightly more complex.

    Args:
        chunk_size: Maximum size per chunk.
        chunk_overlap: Overlap between chunks.
        separators: Ordered list of separators to try.
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        separators: list[str] = ["\n\n", "\n", ". ", " "],
    ) -> None: ...

    def chunk(self, documents: list[Document]) -> list[Chunk]: ...
```

#### 7.1.3 SemanticChunker

Groups by semantic similarity (requires an embedder).  
**Status:** **Planned** (not yet implemented in `rawagents.rag`).

```python
class SemanticChunker:
    """Split by semantic similarity between sentences.

    Embeds each sentence and groups consecutive sentences with
    high similarity together. Produces the most semantically
    coherent chunks but requires embedding computation.

    Best for: Accuracy-critical applications.
    Trade-off: Slower (requires embedding), variable sizes.

    Args:
        embedder: Embedder for computing sentence similarity.
        threshold: Similarity threshold for grouping (0-1).
        min_chunk_size: Minimum characters per chunk.
        max_chunk_size: Maximum characters per chunk.
    """

    def __init__(
        self,
        embedder: Embedder,
        threshold: float = 0.5,
        min_chunk_size: int = 100,
        max_chunk_size: int = 1000,
    ) -> None: ...

    def chunk(self, documents: list[Document]) -> list[Chunk]: ...
```

### 7.2 Embedders

#### 7.2.1 LiteLLMEmbedder

Embeddings via LiteLLM (OpenAI, Cohere, Voyage, Azure, etc.).  
**Status:** Implemented in `embedders/litellm.py`.

```python
class LiteLLMEmbedder:
    """Embeddings via LiteLLM supporting 100+ providers.

    Uses the same provider/model format as LLMClient:
    - "openai/text-embedding-3-small"
    - "cohere/embed-english-v3.0"
    - "voyage/voyage-2"

    Args:
        model: Model identifier in provider/model format.
        batch_size: Maximum texts per API call (respects rate limits).
        max_retries: Number of retries on failure.
        dimensions: Optional dimension override (for models that support it).
    """

    def __init__(
        self,
        model: str = "openai/text-embedding-3-small",
        batch_size: int = 100,
        max_retries: int = 3,
        dimensions: int | None = None,
    ) -> None: ...

    @property
    def dimension(self) -> int: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...

    async def aembed(self, texts: list[str]) -> list[list[float]]:
        """Async embedding with automatic batching.

        Splits texts into batches, embeds in parallel, combines results.
        Handles rate limits and retries automatically.
        """
        ...
```

#### 7.2.2 SentenceTransformerEmbedder

Local embeddings via sentence-transformers (optional dependency).  
**Status:** **Planned** (not yet implemented in `rawagents.rag`; shown here as a future extension).

```python
class SentenceTransformerEmbedder:
    """Local embeddings via sentence-transformers.

    Runs entirely locally—no API calls, no costs, full data privacy.
    Requires: pip install sentence-transformers

    Popular models:
    - "all-MiniLM-L6-v2": Fast, 384 dimensions
    - "all-mpnet-base-v2": Higher quality, 768 dimensions
    - "multi-qa-mpnet-base-dot-v1": Optimized for Q&A

    Args:
        model: Model name from sentence-transformers hub.
        device: Device for inference ("cpu", "cuda", "mps").
    """

    def __init__(
        self,
        model: str = "all-MiniLM-L6-v2",
        device: str | None = None,
    ) -> None: ...

    @property
    def dimension(self) -> int: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...

    async def aembed(self, texts: list[str]) -> list[list[float]]:
        """Async wrapper that runs sync embedding in thread pool."""
        ...
```

### 7.3 VectorStores

#### 7.3.1 MemoryVectorStore

Zero-dependency in-memory store using NumPy.  
**Status:** Implemented in `stores/memory.py` with fixed cosine similarity.

```python
class MemoryVectorStore:
    """In-memory vector store using NumPy.

    Perfect for development, testing, and small datasets.
    Data is lost when the process exits.

    Features:
    - Cosine similarity search
    - Metadata filtering
    - Score thresholding

    Limitations:
    - Not persistent
    - Linear search (O(n) per query)
    - Memory-bound (all vectors in RAM)
    """

    def __init__(self) -> None: ...

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        metadata: list[dict[str, Any]] | None = None,
    ) -> None: ...

    def search(
        self,
        embedding: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
        score_threshold: float | None = None,
    ) -> list[tuple[str, float, dict[str, Any]]]: ...

    def delete(self, ids: list[str]) -> None: ...

    def clear(self) -> None:
        """Remove all vectors."""
        ...

    def __len__(self) -> int:
        """Number of vectors in the store."""
        ...
```

#### 7.3.2 ChromaVectorStore

Persistent store via ChromaDB (optional dependency).  
**Status:** **Planned** (example API only; not implemented in `rawagents.rag` yet).

```python
class ChromaVectorStore:
    """Persistent vector store via ChromaDB.

    Suitable for production with moderate scale (millions of vectors).
    Requires: pip install chromadb

    Features:
    - Persistent storage to disk
    - Efficient HNSW indexing
    - Rich metadata filtering

    Args:
        collection_name: Name of the ChromaDB collection.
        persist_directory: Path for persistent storage. None for in-memory.
        embedding_function: Optional custom embedding function for Chroma.
            If None, assumes you're providing pre-computed embeddings.
    """

    def __init__(
        self,
        collection_name: str = "default",
        persist_directory: str | None = None,
    ) -> None: ...

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        metadata: list[dict[str, Any]] | None = None,
    ) -> None: ...

    def search(
        self,
        embedding: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
        score_threshold: float | None = None,
    ) -> list[tuple[str, float, dict[str, Any]]]: ...

    def delete(self, ids: list[str]) -> None: ...
```

### 7.4 Retriever

The Retriever is **not a protocol**—it's a concrete class that **composes** the primitives.  
**Status:** Implemented in `retriever.py` with `add` / `aadd`, `retrieve` / `aretrieve`, `delete` and an optional reranker hook.

```python
class Retriever:
    """Composes Embedder + VectorStore for document retrieval.

    This is the main "glue" class for RAG. It:
    1. Embeds chunks and stores them
    2. Embeds queries and searches for similar chunks
    3. Optionally reranks results
    4. Supports context expansion (parent-document retrieval)

    The VectorStore remains decoupled—users can also use it directly
    for non-RAG purposes.

    Args:
        embedder: Embedder for converting text to vectors.
        store: VectorStore for storing and searching vectors.
        reranker: Optional reranker for two-stage retrieval.
    """

    def __init__(
        self,
        embedder: Embedder,
        store: VectorStore,
        reranker: Reranker | None = None,
    ) -> None:
        self.embedder = embedder
        self.store = store
        self.reranker = reranker
        self._chunks: dict[str, Chunk] = {}  # id → Chunk mapping

    def add(self, chunks: list[Chunk]) -> None:
        """Embed and store chunks synchronously.

        Args:
            chunks: Chunks to add. IDs are auto-generated if not provided.
        """
        ...

    async def aadd(self, chunks: list[Chunk]) -> None:
        """Embed and store chunks asynchronously."""
        ...

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
        score_threshold: float | None = None,
    ) -> list[SearchResult]:
        """Retrieve relevant chunks for a query.

        Args:
            query: The search query.
            top_k: Maximum results to return.
            filters: Optional metadata filters.
            score_threshold: Minimum relevance score.

        Returns:
            List of SearchResult, sorted by relevance.
        """
        ...

    async def aretrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
        score_threshold: float | None = None,
    ) -> list[SearchResult]:
        """Async version of retrieve."""
        ...

    def delete(self, ids: list[str]) -> None:
        """Remove chunks from the retriever.

        Args:
            ids: IDs of chunks to delete.
        """
        ...

    def __len__(self) -> int:
        """Return the number of chunks currently tracked by the retriever."""
        ...

Note: `update` / `aupdate` helpers and parent-document expansion helpers described elsewhere in this document are **Planned** APIs and are not part of the current implementation.
```

### 7.5 Rerankers

#### 7.5.1 CrossEncoderReranker

Reranking via cross-encoder models (optional dependency).

```python
class CrossEncoderReranker:
    """Rerank results using a cross-encoder model.

    Cross-encoders jointly encode query + document for more accurate
    relevance scoring than bi-encoders, but are slower.

    Requires: pip install sentence-transformers

    Popular models:
    - "cross-encoder/ms-marco-MiniLM-L-6-v2": Fast, general purpose
    - "cross-encoder/ms-marco-MiniLM-L-12-v2": Higher quality

    Args:
        model: Cross-encoder model name.
        device: Device for inference.
    """

    def __init__(
        self,
        model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        device: str | None = None,
    ) -> None: ...

    def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int = 5,
    ) -> list[SearchResult]: ...

    async def arerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Async wrapper that runs sync reranking in thread pool."""
        ...
```

---

## 8. PromptManager Integration

Context formatting is handled by **PromptManager**, not the RAG module. RAG provides Jinja2 filters to make this easy.

### 8.1 RAG Filters

```python
# rawagents/rag/filters.py

def format_chunk(
    result: SearchResult,
    show_score: bool = False,
    show_source: bool = True,
) -> str:
    """Format a single search result for display.

    Args:
        result: The search result to format.
        show_score: Include relevance score.
        show_source: Include source metadata.

    Returns:
        Formatted string representation.
    """
    parts = []
    if show_score:
        parts.append(f"[Relevance: {result.score:.2f}]")
    if show_source and result.chunk.metadata.get("source"):
        parts.append(f"Source: {result.chunk.metadata['source']}")
    parts.append(result.chunk.content)
    return "\n".join(parts)


def format_context(
    results: list[SearchResult],
    max_results: int = 5,
    separator: str = "\n\n---\n\n",
    show_scores: bool = False,
) -> str:
    """Format search results as a single context string.

    Args:
        results: Search results to format.
        max_results: Maximum results to include.
        separator: String between chunks.
        show_scores: Include relevance scores.

    Returns:
        Formatted context string.
    """
    formatted = []
    for i, r in enumerate(results[:max_results]):
        chunk_text = r.chunk.content
        if show_scores:
            chunk_text = f"[{r.score:.2f}] {chunk_text}"
        formatted.append(chunk_text)
    return separator.join(formatted)


def get_rag_filters() -> dict[str, Callable]:
    """Get RAG-specific filters for PromptManager.

    Usage:
        from rawagents.rag.filters import get_rag_filters
        manager = PromptManager("./templates")
        for name, func in get_rag_filters().items():
            manager.add_filter(name, func)
    """
    return {
        "format_chunk": format_chunk,
        "format_context": format_context,
    }
```

### 8.2 Template Examples

**Basic RAG template (`templates/rag_basic.j2`):**
```jinja2
Use the following context to answer the question.
If you cannot find the answer in the context, say "I don't know."

## Context
{{ results | format_context(max_results=5) }}

## Question
{{ query }}
```

**Detailed RAG template with sources (`templates/rag_detailed.j2`):**
```jinja2
You are a helpful assistant with access to a knowledge base.
Answer the question using ONLY the provided context.
Cite your sources using [1], [2], etc.

## Retrieved Context

{% for result in results[:5] %}
### [{{ loop.index }}] {{ result.chunk.metadata.source | default("Unknown") }}
Relevance: {{ "%.1f" | format(result.score * 100) }}%

{{ result.chunk.content }}

{% endfor %}

{% if not results %}
*No relevant context found.*
{% endif %}

## Question
{{ query }}

## Instructions
- Answer based ONLY on the context above
- If the context doesn't contain the answer, say "I don't have information about that"
- Cite sources using [1], [2], etc.
```

### 8.3 Usage Pattern

```python
from rawagents import PromptManager, AsyncLLM
from rawagents.rag import Retriever, RecursiveChunker, LiteLLMEmbedder, MemoryVectorStore
from rawagents.rag.filters import get_rag_filters

# Setup RAG
chunker = RecursiveChunker()
embedder = LiteLLMEmbedder()
store = MemoryVectorStore()
retriever = Retriever(embedder=embedder, store=store)

# Setup PromptManager with RAG filters
manager = PromptManager("./templates")
for name, func in get_rag_filters().items():
    manager.add_filter(name, func)

# Index documents
docs = [Document(content="...", metadata={"source": "doc.pdf"})]
chunks = chunker.chunk(docs)
await retriever.aadd(chunks)

# Query
query = "What is the capital of France?"
results = await retriever.aretrieve(query, top_k=5)

# Format and generate
prompt = manager.render("rag_detailed.j2", results=results, query=query)
response = await llm.complete(messages=[{"role": "user", "content": prompt}])
```

---

## 9. Usage Patterns

### 9.1 Basic RAG Pipeline

```python
from rawagents.rag import (
    Document,
    RecursiveChunker,
    LiteLLMEmbedder,
    MemoryVectorStore,
    Retriever,
)

# 1. Initialize components
chunker = RecursiveChunker(chunk_size=512, chunk_overlap=50)
embedder = LiteLLMEmbedder(model="openai/text-embedding-3-small")
store = MemoryVectorStore()
retriever = Retriever(embedder=embedder, store=store)

# 2. Load and index documents
docs = [
    Document(content="Paris is the capital of France.", metadata={"source": "geography.txt"}),
    Document(content="Berlin is the capital of Germany.", metadata={"source": "geography.txt"}),
]
chunks = chunker.chunk(docs)
await retriever.aadd(chunks)

# 3. Retrieve
results = await retriever.aretrieve("What is the capital of France?", top_k=3)
for r in results:
    print(f"[{r.score:.2f}] {r.chunk.content}")
```

### 9.2 RAG as a Tool

```python
from typing import Annotated
from rawagents import tool, ToolExecutor, Inject, loops, AsyncLLM, Conversation
from rawagents.rag import Retriever

@tool
async def search_knowledge_base(
    query: str,
    retriever: Annotated[Retriever, Inject],
) -> str:
    """Search the knowledge base for relevant information.

    Args:
        query: The search query.

    Returns:
        Relevant information from the knowledge base.
    """
    results = await retriever.aretrieve(query, top_k=5)
    if not results:
        return "No relevant information found."
    return "\n---\n".join(r.chunk.content for r in results)

# Setup
retriever = ...  # Pre-configured retriever with indexed documents
executor = ToolExecutor([search_knowledge_base])
context = {"retriever": retriever}

llm = AsyncLLM()
conv = Conversation()
conv.add_system("You are a helpful assistant with access to a knowledge base.")
conv.add_user("What are the main features of Python?")

# Run agent
async for step in loops.simple(llm, conv, executor, context=context):
    if step.type == "finish":
        print(step.content)
```

### 9.3 Hybrid Retrieval with Custom Keyword Search

**Status:** **Planned** pattern. This example shows how you might compose a custom hybrid retriever on top of the existing primitives; it is not a built-in class.

```python
from rawagents.rag import Retriever, SearchResult

class HybridRetriever:
    """Combines vector search with keyword search."""

    def __init__(
        self,
        vector_retriever: Retriever,
        keyword_searcher: Callable[[str, int], list[SearchResult]],
        vector_weight: float = 0.7,
    ):
        self.vector = vector_retriever
        self.keyword = keyword_searcher
        self.vector_weight = vector_weight

    async def aretrieve(self, query: str, top_k: int = 5) -> list[SearchResult]:
        # Get results from both sources
        vector_results = await self.vector.aretrieve(query, top_k=top_k * 2)
        keyword_results = self.keyword(query, top_k * 2)

        # Reciprocal Rank Fusion
        scores: dict[str, float] = {}
        for i, r in enumerate(vector_results):
            scores[r.chunk.id] = scores.get(r.chunk.id, 0) + self.vector_weight / (i + 1)
        for i, r in enumerate(keyword_results):
            scores[r.chunk.id] = scores.get(r.chunk.id, 0) + (1 - self.vector_weight) / (i + 1)

        # Merge and sort
        all_results = {r.chunk.id: r for r in vector_results + keyword_results}
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

        return [
            SearchResult(chunk=all_results[id].chunk, score=scores[id])
            for id in sorted_ids[:top_k]
        ]
```

### 9.4 Custom VectorStore (e.g., Qdrant)

```python
from rawagents.rag import VectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Distance, VectorParams

class QdrantVectorStore:
    """Custom VectorStore implementation using Qdrant."""

    def __init__(self, url: str, collection: str, dimension: int):
        self.client = QdrantClient(url=url)
        self.collection = collection

        # Create collection if not exists
        self.client.recreate_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
        )

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        metadata: list[dict[str, Any]] | None = None,
    ) -> None:
        points = [
            PointStruct(id=id, vector=emb, payload=meta or {})
            for id, emb, meta in zip(ids, embeddings, metadata or [{}] * len(ids))
        ]
        self.client.upsert(collection_name=self.collection, points=points)

    def search(
        self,
        embedding: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
        score_threshold: float | None = None,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        results = self.client.search(
            collection_name=self.collection,
            query_vector=embedding,
            limit=top_k,
            score_threshold=score_threshold,
        )
        return [(str(r.id), r.score, r.payload) for r in results]

    def delete(self, ids: list[str]) -> None:
        self.client.delete(collection_name=self.collection, points_selector=ids)

# Usage with Retriever
store = QdrantVectorStore(url="localhost:6333", collection="docs", dimension=1536)
retriever = Retriever(embedder=embedder, store=store)
```

### 9.5 Parent Document Retrieval

**Status:** **Planned** helper pattern. `Retriever` currently tracks `document_id` and `position` per chunk, but convenience helpers such as `get_chunk_by_position` are not yet implemented; you can implement a thin wrapper or subclass to achieve this behavior.

```python
# Index with position tracking
docs = [Document(content=long_document, metadata={"source": "manual.pdf"})]
chunks = chunker.chunk(docs)  # Chunks have position set automatically

# After retrieval, expand context
async def retrieve_with_context(
    retriever: Retriever,
    query: str,
    context_window: int = 1,  # Include N chunks before/after
) -> list[SearchResult]:
    results = await retriever.aretrieve(query, top_k=5)

    expanded = []
    for r in results:
        # Get surrounding chunks by position
        doc_id = r.chunk.document_id
        pos = r.chunk.position

        if doc_id and pos is not None:
            # Retrieve chunks at position-1, position, position+1
            for offset in range(-context_window, context_window + 1):
                chunk = retriever.get_chunk_by_position(doc_id, pos + offset)
                if chunk:
                    expanded.append(SearchResult(chunk=chunk, score=r.score))
        else:
            expanded.append(r)

    return expanded
```

---

## 10. Project Structure

```text
src/rawagents/rag/
├── __init__.py              # Public API exports
├── types.py                 # Document, Chunk, SearchResult
├── protocols.py             # Chunker, Embedder, VectorStore, Reranker protocols
├── filters.py               # Jinja2 filters for PromptManager
├── exceptions.py            # RAGError, EmbeddingError, etc.
│
├── chunkers/
│   ├── __init__.py          # Exports: FixedSizeChunker, RecursiveChunker, SemanticChunker
│   ├── base.py              # Shared chunking utilities
│   ├── fixed.py             # FixedSizeChunker
│   ├── recursive.py         # RecursiveChunker
│   └── semantic.py          # SemanticChunker
│
├── embedders/
│   ├── __init__.py          # Exports: LiteLLMEmbedder, SentenceTransformerEmbedder
│   ├── base.py              # Shared embedding utilities (batching, retry)
│   ├── litellm.py           # LiteLLMEmbedder
│   └── sentence.py          # SentenceTransformerEmbedder
│
├── stores/
│   ├── __init__.py          # Exports: MemoryVectorStore, ChromaVectorStore
│   ├── memory.py            # MemoryVectorStore (numpy)
│   └── chroma.py            # ChromaVectorStore
│
├── rerankers/
│   ├── __init__.py          # Exports: CrossEncoderReranker
│   └── cross_encoder.py     # CrossEncoderReranker
│
└── retriever.py             # Retriever class
```

### 10.1 Module Exports (`__init__.py`)

```python
"""RAG Component - Retrieval Augmented Generation primitives.

The RAG component provides the "knowledge" primitives for agents:
- Chunkers: Split documents into retrievable units
- Embedders: Convert text to vector representations
- VectorStores: Store and search vectors (decoupled primitive)
- Retrievers: Compose embedder + store for document retrieval

Example:
    >>> from rawagents.rag import (
    ...     Document, Retriever,
    ...     RecursiveChunker, LiteLLMEmbedder, MemoryVectorStore,
    ... )
    >>>
    >>> chunker = RecursiveChunker()
    >>> embedder = LiteLLMEmbedder()
    >>> store = MemoryVectorStore()
    >>> retriever = Retriever(embedder=embedder, store=store)
    >>>
    >>> docs = [Document(content="...", metadata={"source": "file.pdf"})]
    >>> chunks = chunker.chunk(docs)
    >>> await retriever.aadd(chunks)
    >>>
    >>> results = await retriever.aretrieve("query", top_k=5)
"""

# Types
from rawagents.rag.types import Document, Chunk, SearchResult

# Protocols
from rawagents.rag.protocols import Chunker, Embedder, VectorStore, Reranker

# Chunkers
from rawagents.rag.chunkers import (
    FixedSizeChunker,
    RecursiveChunker,
    SemanticChunker,
)

# Embedders
from rawagents.rag.embedders import LiteLLMEmbedder
# SentenceTransformerEmbedder is optional - import directly if needed

# Stores
from rawagents.rag.stores import MemoryVectorStore
# ChromaVectorStore is optional - import directly if needed

# Rerankers
# CrossEncoderReranker is optional - import directly if needed

# Main retriever
from rawagents.rag.retriever import Retriever

# Filters for PromptManager
from rawagents.rag.filters import get_rag_filters, format_context, format_chunk

# Exceptions
from rawagents.rag.exceptions import RAGError, EmbeddingError, RetrievalError

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
    # Chunkers
    "FixedSizeChunker",
    "RecursiveChunker",
    "SemanticChunker",
    # Embedders
    "LiteLLMEmbedder",
    # Stores
    "MemoryVectorStore",
    # Retriever
    "Retriever",
    # Filters
    "get_rag_filters",
    "format_context",
    "format_chunk",
    # Exceptions
    "RAGError",
    "EmbeddingError",
    "RetrievalError",
]
```

---

## 11. Component Interactions

### 11.1 With LLM

The RAG module does **not** interact with the LLM directly. Retrieval results are passed to `PromptManager` for formatting, then to `LLM` for generation.

```
Retriever.aretrieve() → SearchResult[] → PromptManager.render() → LLM.complete()
```

### 11.2 With Tools

RAG can be exposed as a tool via the `@tool` decorator. The retriever is injected via context.

```
@tool search_docs(query, retriever: Inject) → ToolExecutor → loops.simple()
```

### 11.3 With State (Conversation)

RAG does **not** interact with Conversation directly. Retrieved context is formatted and added to the conversation as part of the user message or system prompt.

### 11.4 With PromptManager

- RAG provides Jinja2 filters (`format_context`, `format_chunk`)
- PromptManager templates use these filters to format retrieved results
- Clean separation: RAG finds, PromptManager presents

---

## 12. Implementation Roadmap

### Phase 1: Core (MVP)

**Goal**: Basic working RAG pipeline

| Component | Priority | Dependency |
|-----------|----------|------------|
| `types.py` (Document, Chunk, SearchResult) | P0 | None |
| `protocols.py` (all protocols) | P0 | types |
| `MemoryVectorStore` | P0 | numpy |
| `LiteLLMEmbedder` | P0 | litellm |
| `FixedSizeChunker` | P0 | None |
| `Retriever` | P0 | protocols |
| `filters.py` | P0 | types |
| `exceptions.py` | P0 | None |

**Deliverable**: Can index documents and retrieve results with in-memory store.

### Phase 2: Enhanced Chunking

**Goal**: Production-quality chunking

| Component | Priority | Dependency |
|-----------|----------|------------|
| `RecursiveChunker` | P1 | None |
| `SemanticChunker` | P2 | Embedder |
| Chunk position tracking | P1 | types |

**Deliverable**: Multiple chunking strategies, parent-document retrieval ready.

### Phase 3: Alternative Backends

**Goal**: Production storage and local embeddings

| Component | Priority | Dependency |
|-----------|----------|------------|
| `ChromaVectorStore` | P1 | chromadb (optional) |
| `SentenceTransformerEmbedder` | P1 | sentence-transformers (optional) |

**Deliverable**: Persistent storage, local embeddings without API costs.

### Phase 4: Advanced Retrieval

**Goal**: Production-quality retrieval

| Component | Priority | Dependency |
|-----------|----------|------------|
| `CrossEncoderReranker` | P2 | sentence-transformers (optional) |
| Metadata filtering | P1 | VectorStore |
| Update/delete operations | P1 | Retriever |

**Deliverable**: Two-stage retrieval, incremental updates.

---

## 13. Testing Strategy

### 13.1 Test Structure

```text
tests/rag/
├── conftest.py              # Shared fixtures
├── test_types.py            # Document, Chunk, SearchResult
├── test_chunkers/
│   ├── test_fixed.py
│   ├── test_recursive.py
│   └── test_semantic.py
├── test_embedders/
│   ├── test_litellm.py
│   └── test_sentence.py
├── test_stores/
│   ├── test_memory.py
│   └── test_chroma.py
├── test_retriever.py
├── test_rerankers/
│   └── test_cross_encoder.py
└── test_filters.py
```

### 13.2 Key Fixtures

```python
# conftest.py

@pytest.fixture
def sample_documents() -> list[Document]:
    """Sample documents for testing."""
    return [
        Document(content="Paris is the capital of France.", metadata={"source": "geo.txt"}),
        Document(content="Berlin is the capital of Germany.", metadata={"source": "geo.txt"}),
        Document(content="Tokyo is the capital of Japan.", metadata={"source": "geo.txt"}),
    ]

@pytest.fixture
def sample_chunks(sample_documents) -> list[Chunk]:
    """Pre-chunked documents."""
    chunker = FixedSizeChunker(chunk_size=100)
    return chunker.chunk(sample_documents)

@pytest.fixture
def mock_embedder() -> Embedder:
    """Mock embedder that returns deterministic vectors."""
    class MockEmbedder:
        @property
        def dimension(self) -> int:
            return 3

        def embed(self, texts: list[str]) -> list[list[float]]:
            # Simple hash-based embeddings for testing
            return [[hash(t) % 100 / 100, len(t) / 100, 0.5] for t in texts]

        async def aembed(self, texts: list[str]) -> list[list[float]]:
            return self.embed(texts)

    return MockEmbedder()

@pytest.fixture
def memory_store() -> MemoryVectorStore:
    """Fresh in-memory store."""
    return MemoryVectorStore()

@pytest.fixture
def retriever(mock_embedder, memory_store) -> Retriever:
    """Configured retriever with mock embedder."""
    return Retriever(embedder=mock_embedder, store=memory_store)
```

### 13.3 Test Categories

1. **Unit Tests**: Each component in isolation
2. **Integration Tests**: Retriever with real embedder (mocked API)
3. **End-to-End Tests**: Full pipeline from document to retrieval

### 13.4 Mocking Strategy

```python
# Mock LiteLLM embedding calls
@pytest.fixture
def mock_litellm_embedding():
    with patch("rawagents.rag.embedders.litellm.embedding") as mock:
        mock.return_value = MagicMock(
            data=[{"embedding": [0.1, 0.2, 0.3] * 512}]
        )
        yield mock
```

---

## 14. Future Extensibility

All components in this section are **future ideas / planned extensions** and are **not implemented** in the current `rawagents.rag` module.

### 14.1 Query Transformations (v2)

```python
# Future: Query transformation protocols
class QueryTransformer(Protocol):
    async def transform(self, query: str) -> str | list[str]: ...

class HyDETransformer:
    """Hypothetical Document Embeddings - generate answer first."""
    def __init__(self, llm: AsyncLLM): ...

class MultiQueryTransformer:
    """Generate multiple query variations."""
    def __init__(self, llm: AsyncLLM, num_queries: int = 3): ...
```

### 14.2 Hybrid Retrieval (v2)

```python
# Future: First-class hybrid search support
class HybridRetriever:
    """Combines vector and keyword search with RRF fusion."""
    def __init__(
        self,
        vector_retriever: Retriever,
        keyword_searcher: KeywordSearcher,
        vector_weight: float = 0.7,
        fusion_method: Literal["rrf", "weighted"] = "rrf",
    ): ...
```

### 14.3 Evaluation Utilities (v2)

```python
# Future: Optional evaluation module
@dataclass
class RetrievalMetrics:
    recall_at_k: float
    precision_at_k: float
    mrr: float
    ndcg: float

def evaluate_retrieval(
    retriever: Retriever,
    queries: list[str],
    ground_truth: list[list[str]],  # Expected chunk IDs
    k: int = 5,
) -> RetrievalMetrics: ...
```

### 14.4 Streaming Ingestion (v3)

```python
# Future: Real-time document updates
class StreamingRetriever:
    """Retriever with real-time update support."""

    async def watch(self, source: AsyncIterator[Document]) -> None:
        """Continuously index documents from a stream."""
        async for doc in source:
            chunks = self.chunker.chunk([doc])
            await self.aadd(chunks)
```

---

## Appendix A: Dependency Matrix

| Component | Required | Optional |
|-----------|----------|----------|
| Core Types | None | None |
| MemoryVectorStore | `numpy` | None |
| ChromaVectorStore | None | `chromadb` |
| LiteLLMEmbedder | `litellm` | None |
| SentenceTransformerEmbedder | None | `sentence-transformers` |
| CrossEncoderReranker | None | `sentence-transformers` |
| SemanticChunker | Embedder | None |

**Installation extras:**

```toml
# pyproject.toml
[project.optional-dependencies]
rag = ["numpy>=1.24"]
rag-chroma = ["chromadb>=0.4"]
rag-local = ["sentence-transformers>=2.2"]
```

---

## Appendix B: Migration Guide from Other Frameworks

### From LangChain

```python
# LangChain
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import Chroma
from langchain.embeddings import OpenAIEmbeddings

splitter = RecursiveCharacterTextSplitter(chunk_size=500)
embeddings = OpenAIEmbeddings()
vectorstore = Chroma.from_documents(docs, embeddings)
results = vectorstore.similarity_search(query)

# RawAgents
from rawagents.rag import RecursiveChunker, LiteLLMEmbedder, ChromaVectorStore, Retriever

chunker = RecursiveChunker(chunk_size=500)
embedder = LiteLLMEmbedder(model="openai/text-embedding-3-small")
store = ChromaVectorStore()
retriever = Retriever(embedder=embedder, store=store)

chunks = chunker.chunk(docs)
await retriever.aadd(chunks)
results = await retriever.aretrieve(query)
```

### From LlamaIndex

```python
# LlamaIndex
from llama_index import VectorStoreIndex, SimpleDirectoryReader

documents = SimpleDirectoryReader("data").load_data()
index = VectorStoreIndex.from_documents(documents)
query_engine = index.as_query_engine()
response = query_engine.query("What is X?")

# RawAgents (document loading is explicit)
from rawagents.rag import Document, RecursiveChunker, Retriever, LiteLLMEmbedder, MemoryVectorStore

# Load documents yourself (we don't abstract this)
docs = [Document(content=open(f).read(), metadata={"source": f}) for f in files]

chunker = RecursiveChunker()
retriever = Retriever(embedder=LiteLLMEmbedder(), store=MemoryVectorStore())

chunks = chunker.chunk(docs)
await retriever.aadd(chunks)

# RAG is retrieval only - generation is separate
results = await retriever.aretrieve("What is X?")
# Use PromptManager + LLM for generation
```

---

## Appendix C: Performance Considerations

### Embedding Batching

```python
# LiteLLMEmbedder handles batching automatically
embedder = LiteLLMEmbedder(
    model="openai/text-embedding-3-small",
    batch_size=100,  # Texts per API call
)

# For large datasets, chunks are batched automatically
await retriever.aadd(chunks)  # 10,000 chunks → 100 API calls
```

### Memory Usage

```python
# MemoryVectorStore memory estimation
# 1M vectors × 1536 dimensions × 4 bytes = ~6GB RAM

# For large datasets, use ChromaDB or external store
store = ChromaVectorStore(persist_directory="./chroma_db")
```

### Search Performance

```python
# MemoryVectorStore: O(n) linear scan
# ChromaVectorStore: O(log n) with HNSW index

# For >100k vectors, use indexed stores (Chroma, Qdrant, Pinecone)
```
