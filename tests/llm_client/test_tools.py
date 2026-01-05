"""Tests for tool schema conversion."""

from typing import Literal

from pydantic import BaseModel, Field

from rawagents.llm.tools import pydantic_to_tool_schema, tools_to_schemas


class TestPydanticToToolSchema:
    """Tests for pydantic_to_tool_schema function."""

    def test_basic_model_conversion(self) -> None:
        """Converts a basic Pydantic model to tool schema."""

        class GetWeather(BaseModel):
            """Get current weather for a location."""

            location: str

        schema = pydantic_to_tool_schema(GetWeather)

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "GetWeather"
        assert (
            schema["function"]["description"] == "Get current weather for a location."
        )
        assert "location" in schema["function"]["parameters"]["properties"]

    def test_model_with_field_descriptions(self) -> None:
        """Converts model with Field descriptions."""

        class SearchWeb(BaseModel):
            """Search the web for information."""

            query: str = Field(description="The search query")
            max_results: int = Field(
                default=10, description="Maximum results to return"
            )

        schema = pydantic_to_tool_schema(SearchWeb)

        props = schema["function"]["parameters"]["properties"]
        assert props["query"]["description"] == "The search query"
        assert props["max_results"]["description"] == "Maximum results to return"

    def test_model_with_required_fields(self) -> None:
        """Required fields are marked in schema."""

        class CreateFile(BaseModel):
            filename: str
            content: str
            overwrite: bool = False

        schema = pydantic_to_tool_schema(CreateFile)

        required = schema["function"]["parameters"].get("required", [])
        assert "filename" in required
        assert "content" in required
        assert "overwrite" not in required

    def test_model_with_enum_field(self) -> None:
        """Converts model with Literal/enum fields."""

        class SetTemperature(BaseModel):
            """Set temperature unit."""

            unit: Literal["celsius", "fahrenheit"]

        schema = pydantic_to_tool_schema(SetTemperature)

        props = schema["function"]["parameters"]["properties"]
        assert "enum" in props["unit"] or "anyOf" in props["unit"]

    def test_model_without_docstring(self) -> None:
        """Handles model without docstring."""

        class NoDocModel(BaseModel):
            value: str

        schema = pydantic_to_tool_schema(NoDocModel)

        assert schema["function"]["name"] == "NoDocModel"
        assert schema["function"]["description"] == ""


class TestToolsToSchemas:
    """Tests for tools_to_schemas function."""

    def test_converts_multiple_tools(self) -> None:
        """Converts multiple tools to schemas."""

        class ToolA(BaseModel):
            """Tool A."""

            a: str

        class ToolB(BaseModel):
            """Tool B."""

            b: int

        schemas = tools_to_schemas([ToolA, ToolB])

        assert len(schemas) == 2
        assert schemas[0]["function"]["name"] == "ToolA"
        assert schemas[1]["function"]["name"] == "ToolB"

    def test_empty_list_returns_empty(self) -> None:
        """Empty tool list returns empty schema list."""
        schemas = tools_to_schemas([])
        assert schemas == []
