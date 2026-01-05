# RawAgents Test Suite

This directory contains the test suite for the RawAgents library. All tests use pytest with full type annotations and follow consistent patterns across modules.

## Quick Start

```bash
# Run all tests
uv run pytest tests/

# Run with verbose output
uv run pytest tests/ -v

# Run specific module
uv run pytest tests/tools/

# Run with coverage
uv run pytest tests/ --cov=src/rawagents --cov-report=html
```

## Test Structure

```
tests/
├── conversation/        # State management tests
│   ├── conftest.py     # Conversation fixtures
│   ├── test_branching.py
│   ├── test_conversation.py
│   ├── test_storage.py
│   ├── test_strategies.py
│   └── test_types.py
├── llm_client/          # LLM client tests
│   ├── conftest.py     # LLM response mocks
│   ├── test_async_client.py
│   ├── test_client.py
│   ├── test_config.py
│   └── test_tools.py
├── loops/               # Agent loop tests
│   ├── conftest.py     # Mock LLM & tools
│   ├── test_interactive.py
│   ├── test_safety.py
│   ├── test_simple.py
│   └── test_types.py
├── prompts/             # Prompt management tests
│   ├── conftest.py     # Template fixtures
│   ├── test_filters.py
│   ├── test_manager.py
│   └── test_security.py
└── tools/               # Tool system tests
    ├── conftest.py     # Tool fixtures
    ├── test_decorator.py
    ├── test_executor.py
    ├── test_injection.py
    └── test_schema.py
```

## Module Overview

| Module | Tests | Description |
|--------|-------|-------------|
| `conversation/` | 107 | Conversation state, branching, storage, strategies |
| `tools/` | 78 | @tool decorator, executor, injection, schema generation |
| `prompts/` | 62 | PromptManager, Jinja2 filters, security sandbox |
| `loops/` | 51 | Simple and interactive agent loops, safety features |
| `llm_client/` | 42 | Sync/async clients, config, tool conversion |

**Total: 340+ tests**

## Running Tests

### Basic Commands

```bash
# All tests
uv run pytest tests/

# Verbose with short tracebacks
uv run pytest tests/ -v --tb=short

# Stop on first failure
uv run pytest tests/ -x

# Run last failed tests
uv run pytest tests/ --lf
```

### Running Specific Tests

```bash
# Single module
uv run pytest tests/tools/

# Single file
uv run pytest tests/tools/test_decorator.py

# Single class
uv run pytest tests/tools/test_decorator.py::TestToolDecoratorBasic

# Single test
uv run pytest tests/tools/test_decorator.py::TestToolDecoratorBasic::test_decorator_preserves_function_behavior

# Tests matching pattern
uv run pytest tests/ -k "injection"
```

### Coverage

```bash
# With terminal report
uv run pytest tests/ --cov=src/rawagents --cov-report=term-missing

# With HTML report
uv run pytest tests/ --cov=src/rawagents --cov-report=html
# Open htmlcov/index.html in browser
```

### Test Markers

```bash
# Skip integration tests (when implemented)
uv run pytest tests/ -m "not integration"

# Skip slow tests (when implemented)
uv run pytest tests/ -m "not slow"
```

## Writing Tests

### Test File Structure

Each test file follows this pattern:

```python
"""Tests for [component]."""

from typing import ...
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from rawagents import ...


class TestFeatureName:
    """Tests for [feature]."""

    def test_behavior_description(self) -> None:
        """One-line description of expected behavior."""
        # Arrange
        ...
        # Act
        result = ...
        # Assert
        assert result == expected
```

### Naming Conventions

- **Test files:** `test_<module>.py`
- **Test classes:** `TestFeatureName` (PascalCase)
- **Test methods:** `test_<what>_<expected_behavior>` (snake_case)
- **Fixtures:** `<descriptive_name>` (snake_case)

### Examples

```python
# Good test names
def test_decorator_preserves_function_behavior(self) -> None:
def test_missing_return_type_raises_error(self) -> None:
def test_execute_with_injection(self) -> None:

# Good docstrings
"""Decorated function can still be called normally."""
"""Missing return type raises ToolDefinitionError."""
"""Tool with injection executes with context."""
```

## Fixtures

### Using Fixtures

Fixtures are defined in `conftest.py` files and automatically available to tests in that directory:

```python
class TestToolExecutor:
    def test_register_tool(self, simple_tool) -> None:
        """Tool can be registered."""
        executor = ToolExecutor()
        executor.register(simple_tool)
        assert "add" in executor
```

### Key Fixtures by Module

#### `tools/conftest.py`
- `simple_tool` - Basic @tool decorated function
- `async_tool` - Async decorated function
- `tool_with_injection` - Tool with Inject parameters
- `executor` - Pre-configured ToolExecutor
- `mock_db` - Mock database for injection tests

#### `llm_client/conftest.py`
- `default_config` - Default LLMConfig
- `client` - Test LLMClient instance
- `mock_litellm_response` - Standard LLM response
- `mock_tool_call_response` - Response with tool calls
- `sample_messages` - Test conversation messages

#### `loops/conftest.py`
- `mock_conversation` - Mock Conversation with history
- `mock_llm_no_tools` - LLM responding without tools
- `mock_llm_with_tools` - LLM requesting then completing
- `mock_tools` - Mock ToolExecutor (success)
- `mock_tools_with_error` - Error-returning executor

#### `prompts/conftest.py`
- `template_dir` - Temporary directory with test templates
- `manager` - PromptManager instance
- `sample_user` - Pydantic model for testing

#### `conversation/conftest.py`
- `empty_conversation` - Fresh Conversation
- `sample_conversation` - Conversation with messages
- `in_memory_storage` - InMemoryStorage instance

### Creating Fixtures

```python
# conftest.py
import pytest
from rawagents.tools import tool

@pytest.fixture
def my_tool():
    """Create a test tool."""
    @tool
    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b
    return add
```

## Async Tests

Async tests are automatically detected via `asyncio_mode = "auto"` in pytest config:

```python
import pytest

class TestAsyncFeature:
    @pytest.mark.asyncio
    async def test_async_operation(self) -> None:
        """Async operation completes successfully."""
        result = await some_async_function()
        assert result == expected
```

### Async Generator Testing (Loops)

```python
@pytest.mark.asyncio
async def test_loop_yields_steps(self, mock_conversation, mock_llm) -> None:
    """Loop yields expected steps."""
    steps: list[LoopStep] = []
    async for step in simple(mock_conversation, mock_llm, mock_tools):
        steps.append(step)

    assert len(steps) == 2
    assert steps[0].type == "thought"
    assert steps[1].type == "finish"
```

## Mocking

### Mocking External Calls

```python
from unittest.mock import patch, MagicMock

def test_complete_calls_litellm(self, client, sample_messages) -> None:
    """Complete calls LiteLLM with correct parameters."""
    with patch("rawagents.llm.client.completion") as mock:
        mock.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Hello"))],
            model="gpt-4o-mini",
            usage=MagicMock(prompt_tokens=10, completion_tokens=5),
        )
        response = client.complete(messages=sample_messages)

    mock.assert_called_once()
    assert response.content == "Hello"
```

### Mocking Async Functions

```python
from unittest.mock import AsyncMock

@pytest.fixture
def mock_llm() -> AsyncMock:
    """Mock LLM that responds without tools."""
    llm = AsyncMock()
    llm.complete_with_tools.return_value = ToolResponse(
        content="Hello!",
        tool_calls=[],
        ...
    )
    return llm
```

### Side Effects for Multiple Calls

```python
llm.complete_with_tools.side_effect = [
    ToolResponse(content="Let me search.", tool_calls=[...]),  # First call
    ToolResponse(content="Here's your answer.", tool_calls=[]),  # Second call
]
```

## Error Testing

```python
import pytest
from rawagents.tools import ToolDefinitionError

def test_missing_type_raises_error(self) -> None:
    """Missing type annotation raises ToolDefinitionError."""
    with pytest.raises(ToolDefinitionError, match="type annotation"):
        @tool
        def bad_func(x) -> int:
            return x
```

## Best Practices

### Do

- Write one assertion per test when possible
- Use descriptive test names that explain the expected behavior
- Add type hints to all test functions
- Use fixtures for shared setup
- Mock external dependencies (APIs, databases)
- Test both success and error cases
- Keep tests fast (no real API calls)

### Don't

- Share state between tests
- Use `time.sleep()` in tests
- Make real API calls (mock everything)
- Write overly complex test setup
- Skip writing docstrings
- Ignore type hints

### Test Organization

```python
class TestFeature:
    """Tests for Feature."""

    # Happy path tests first
    def test_basic_usage(self) -> None: ...
    def test_with_options(self) -> None: ...

    # Edge cases
    def test_empty_input(self) -> None: ...
    def test_large_input(self) -> None: ...

    # Error cases last
    def test_invalid_input_raises_error(self) -> None: ...
    def test_missing_required_param_raises_error(self) -> None: ...
```

## Configuration

Pytest configuration in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
addopts = ["-v", "--tb=short", "--strict-markers"]
markers = [
    "integration: marks tests requiring real API calls",
    "slow: marks tests as slow",
]

[tool.coverage.run]
source = ["src/rawagents"]
branch = true
```

## Troubleshooting

### Common Issues

**Import errors:**
```bash
# Ensure package is installed in dev mode
uv pip install -e ".[dev]"
```

**Async test not running:**
```python
# Make sure to add the decorator
@pytest.mark.asyncio
async def test_async_function(self) -> None:
    ...
```

**Fixture not found:**
```bash
# Check fixture is in conftest.py in same or parent directory
# Check fixture name matches exactly
```

**Mock not working:**
```python
# Patch where the function is used, not where it's defined
with patch("rawagents.llm.client.completion"):  # Correct
with patch("litellm.completion"):  # Wrong
```

## Contributing

When adding new tests:

1. Follow existing patterns in the module
2. Add fixtures to `conftest.py` if reusable
3. Include docstrings for all tests
4. Ensure all tests pass before submitting
5. Aim for high coverage of new code

```bash
# Run tests before committing
uv run pytest tests/ -v

# Check coverage of your changes
uv run pytest tests/ --cov=src/rawagents --cov-report=term-missing
```
