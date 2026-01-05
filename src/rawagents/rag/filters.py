"""Jinja2 filters for RAG context formatting in PromptManager."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from rawagents.rag.types import Chunk, SearchResult


__all__ = [
    "format_chunk",
    "format_context",
    "get_rag_filters",
]


def format_chunk(chunk: Chunk, include_metadata: bool = False) -> str:
    """Format a single chunk for prompt inclusion.

    Args:
        chunk: The chunk to format.
        include_metadata: Whether to include metadata in the output.

    Returns:
        Formatted chunk string.

    Example in template:
        {{ chunk | format_chunk }}
        {{ chunk | format_chunk(include_metadata=true) }}
    """
    if include_metadata and chunk.metadata:
        # Filter out internal metadata keys
        visible_meta = {k: v for k, v in chunk.metadata.items() if not k.startswith("_")}
        if visible_meta:
            meta_str = ", ".join(f"{k}: {v}" for k, v in visible_meta.items())
            return f"[{meta_str}]\n{chunk.content}"
    return chunk.content


def format_context(
    results: list[SearchResult],
    separator: str = "\n---\n",
    include_scores: bool = False,
    include_metadata: bool = False,
    max_results: int | None = None,
) -> str:
    """Format search results as context for LLM prompts.

    Formats a list of SearchResults into a single string suitable for
    inclusion in an LLM prompt. Each result is numbered for easy reference.

    Args:
        results: List of SearchResults to format.
        separator: String to separate chunks (default: "\\n---\\n").
        include_scores: Whether to include relevance scores.
        include_metadata: Whether to include chunk metadata.
        max_results: Maximum number of results to include.

    Returns:
        Formatted context string.

    Example in template:
        {{ results | format_context }}
        {{ results | format_context(include_scores=true, separator="\\n\\n") }}

    Example output:
        [1]
        First chunk content...
        ---
        [2]
        Second chunk content...
    """
    if not results:
        return ""

    if max_results is not None:
        results = results[:max_results]

    formatted: list[str] = []
    for i, r in enumerate(results, 1):
        chunk_text = format_chunk(r.chunk, include_metadata)

        if include_scores:
            formatted.append(f"[{i}] (score: {r.score:.3f})\n{chunk_text}")
        else:
            formatted.append(f"[{i}]\n{chunk_text}")

    return separator.join(formatted)


def get_rag_filters() -> dict[str, Callable[..., Any]]:
    """Get RAG-specific Jinja2 filters for PromptManager.

    Returns a dictionary of filter functions that can be registered
    with a PromptManager to enable RAG formatting in templates.

    Returns:
        Dict mapping filter names to filter functions.

    Example:
        >>> from rawagents import PromptManager
        >>> from rawagents.rag import get_rag_filters
        >>>
        >>> manager = PromptManager("./templates")
        >>> for name, func in get_rag_filters().items():
        ...     manager.add_filter(name, func)
        >>>
        >>> # Now use in templates:
        >>> # {{ results | format_context }}
    """
    return {
        "format_chunk": format_chunk,
        "format_context": format_context,
    }
