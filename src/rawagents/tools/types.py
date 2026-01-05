"""Type definitions for the Tool Executor component."""

from __future__ import annotations

from rawagents.utils.types import ToolResult

__all__ = [
    "Inject",
    "ToolResult",
]


class Inject:
    """Marker for dependency injection.

    Use with typing.Annotated to mark parameters that should be injected
    at runtime rather than provided by the LLM.

    Injected parameters are:
    - Hidden from the JSON schema sent to the LLM
    - Resolved from the context dict at execution time
    - Matched by parameter name (e.g., context={'db': my_db})

    Example:
        from typing import Annotated
        from ai_components.tools import tool, Inject

        @tool
        def query_database(
            sql: str,
            db: Annotated[Database, Inject],
        ) -> str:
            '''Execute a SQL query.'''
            return db.execute(sql)

        # At execution time:
        result = await executor.execute(
            tool_call,
            context={'db': my_db_connection}
        )
    """

    pass
