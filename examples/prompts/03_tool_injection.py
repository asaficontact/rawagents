"""Tool Injection and JSON Formatting example."""

from pydantic import BaseModel, Field
from ai_components.prompts import PromptManager
from ai_components.tools import ToolExecutor, tool

# Define some tools
@tool
def search_web(query: str) -> str:
    """Search the web."""
    return "results"

@tool
def calculate(expression: str) -> int:
    """Calculate math."""
    return 42

# Define output schema
class AnalysisResult(BaseModel):
    """Structured analysis result."""
    summary: str = Field(description="Brief summary")
    confidence: float = Field(description="0.0 to 1.0")

def main():
    # Setup components
    manager = PromptManager("./examples/prompts/templates")
    executor = ToolExecutor([search_web, calculate])
    
    # Get schemas
    tool_schemas = executor.get_schemas()
    response_schema = AnalysisResult.model_json_schema()
    
    # Render with 'to_json' filter automatically handling complex objects
    prompt = manager.render(
        "03_tools.j2",
        tools=tool_schemas,
        query="What is 2+2 and who is the president?",
        response_schema=response_schema
    )
    
    print("--- Prompt with Injected Tools & Schema ---")
    print(prompt)

if __name__ == "__main__":
    main()

