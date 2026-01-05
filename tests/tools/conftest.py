"""Shared fixtures for tool tests."""

from typing import Annotated

import pytest

from rawagents.tools import Inject, ToolExecutor, tool


@pytest.fixture
def simple_tool():
    """A simple sync tool that adds two numbers."""

    @tool
    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    return add


@pytest.fixture
def tool_with_defaults():
    """A tool with default parameter values."""

    @tool
    def greet(name: str, greeting: str = "Hello") -> str:
        """Greet someone."""
        return f"{greeting}, {name}!"

    return greet


@pytest.fixture
def tool_with_injection():
    """A tool that requires dependency injection."""

    @tool
    def query(sql: str, db: Annotated[dict[str, str], Inject]) -> str:
        """Execute a query using injected database."""
        return db.get(sql, "not found")

    return query


@pytest.fixture
def async_tool():
    """An async tool."""

    @tool
    async def fetch(url: str) -> str:
        """Fetch content from URL."""
        return f"Content from {url}"

    return fetch


@pytest.fixture
def tool_that_raises():
    """A tool that raises an exception."""

    @tool
    def divide(a: int, b: int) -> float:
        """Divide two numbers."""
        return a / b

    return divide


@pytest.fixture
def executor(
    simple_tool,
    tool_with_defaults,
    tool_with_injection,
    async_tool,
    tool_that_raises,
):
    """Executor with various tools registered."""
    return ToolExecutor(
        [
            simple_tool,
            tool_with_defaults,
            tool_with_injection,
            async_tool,
            tool_that_raises,
        ]
    )


@pytest.fixture
def mock_db() -> dict[str, str]:
    """Mock database for injection tests."""
    return {
        "SELECT * FROM users": '{"users": ["alice", "bob"]}',
        "SELECT 1": "1",
    }
