"""Tests for JSON schema generation."""

from typing import Annotated, Literal

from pydantic import BaseModel

from rawagents.tools import Inject, tool
from rawagents.tools.schema import generate_tool_schema, type_to_json_schema


class TestTypeToJsonSchema:
    """Tests for type_to_json_schema function."""

    def test_str_type(self) -> None:
        """String type converts correctly."""
        assert type_to_json_schema(str) == {"type": "string"}

    def test_int_type(self) -> None:
        """Integer type converts correctly."""
        assert type_to_json_schema(int) == {"type": "integer"}

    def test_float_type(self) -> None:
        """Float type converts correctly."""
        assert type_to_json_schema(float) == {"type": "number"}

    def test_bool_type(self) -> None:
        """Boolean type converts correctly."""
        assert type_to_json_schema(bool) == {"type": "boolean"}

    def test_list_type(self) -> None:
        """List type converts correctly."""
        schema = type_to_json_schema(list[str])
        assert schema["type"] == "array"
        assert schema["items"] == {"type": "string"}

    def test_dict_type(self) -> None:
        """Dict type converts correctly."""
        schema = type_to_json_schema(dict[str, int])
        assert schema["type"] == "object"
        assert schema["additionalProperties"] == {"type": "integer"}

    def test_literal_type(self) -> None:
        """Literal type converts to enum."""
        schema = type_to_json_schema(Literal["a", "b", "c"])
        assert schema["type"] == "string"
        assert schema["enum"] == ["a", "b", "c"]

    def test_optional_type(self) -> None:
        """Optional type extracts base type."""
        schema = type_to_json_schema(str | None)
        assert schema["type"] == "string"

    def test_pydantic_model_type(self) -> None:
        """Pydantic model converts to object schema."""

        class TestModel(BaseModel):
            name: str
            count: int

        schema = type_to_json_schema(TestModel)
        assert schema["type"] == "object"
        assert "name" in schema["properties"]
        assert "count" in schema["properties"]


class TestGenerateToolSchema:
    """Tests for generate_tool_schema function."""

    def test_simple_function_schema(self) -> None:
        """Simple function generates correct schema."""

        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        schema = generate_tool_schema("add", "Add two numbers.", add, set())

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "add"
        assert schema["function"]["description"] == "Add two numbers."
        assert "a" in schema["function"]["parameters"]["properties"]
        assert "b" in schema["function"]["parameters"]["properties"]
        assert schema["function"]["parameters"]["required"] == ["a", "b"]

    def test_function_with_defaults(self) -> None:
        """Parameters with defaults are not required."""

        def greet(name: str, greeting: str = "Hello") -> str:
            """Greet someone."""
            return f"{greeting}, {name}"

        schema = generate_tool_schema("greet", "Greet someone.", greet, set())

        required = schema["function"]["parameters"]["required"]
        assert "name" in required
        assert "greeting" not in required

    def test_injected_params_hidden(self) -> None:
        """Injected parameters are excluded from schema."""

        def query(sql: str, db: str) -> str:
            """Query database."""
            return sql

        schema = generate_tool_schema("query", "Query database.", query, {"db"})

        properties = schema["function"]["parameters"]["properties"]
        assert "sql" in properties
        assert "db" not in properties

    def test_schema_type_mapping(self) -> None:
        """Types are correctly mapped in schema."""

        def func(
            s: str,
            i: int,
            f: float,
            b: bool,
        ) -> str:
            """Test function."""
            return ""

        schema = generate_tool_schema("func", "Test.", func, set())
        props = schema["function"]["parameters"]["properties"]

        assert props["s"]["type"] == "string"
        assert props["i"]["type"] == "integer"
        assert props["f"]["type"] == "number"
        assert props["b"]["type"] == "boolean"


class TestSchemaWithDecorator:
    """Tests for schema generation via @tool decorator."""

    def test_schema_generated_on_decoration(self) -> None:
        """Schema is generated when @tool is applied."""

        @tool
        def my_tool(x: int) -> int:
            """My tool."""
            return x

        assert hasattr(my_tool, "__tool_schema__")
        assert my_tool.__tool_schema__["type"] == "function"

    def test_schema_excludes_injected_params(self) -> None:
        """Schema excludes Inject-marked parameters."""

        @tool
        def query_tool(
            sql: str,
            db: Annotated[dict[str, str], Inject],
        ) -> str:
            """Query tool."""
            return sql

        props = query_tool.__tool_schema__["function"]["parameters"]["properties"]
        assert "sql" in props
        assert "db" not in props

    def test_schema_uses_docstring_description(self) -> None:
        """Schema uses docstring as description."""

        @tool
        def described_tool(x: int) -> int:
            """This is the tool description."""
            return x

        desc = described_tool.__tool_schema__["function"]["description"]
        assert desc == "This is the tool description."

    def test_schema_uses_custom_description(self) -> None:
        """Schema uses custom description when provided."""

        @tool(description="Custom description")
        def custom_tool(x: int) -> int:
            """Original docstring."""
            return x

        desc = custom_tool.__tool_schema__["function"]["description"]
        assert desc == "Custom description"
