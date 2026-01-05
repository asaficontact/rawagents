"""Example 2: Structured Output

This example demonstrates extracting structured data from LLM responses
using Pydantic models.

Requirements:
    - Set OPENAI_API_KEY environment variable

Usage:
    uv run python examples/llm_client/02_structured_output.py --model openai/gpt-4o-mini
"""

import argparse
from pydantic import BaseModel, Field

from rawagents import LLM


# Define the structure you want to extract
class Person(BaseModel):
    """Information about a person."""

    name: str = Field(description="The person's full name")
    age: int = Field(description="The person's age in years")
    occupation: str = Field(description="The person's job or profession")


class MovieReview(BaseModel):
    """A structured movie review."""

    title: str
    rating: float = Field(ge=0, le=10, description="Rating from 0-10")
    pros: list[str] = Field(description="Positive aspects")
    cons: list[str] = Field(description="Negative aspects")
    summary: str = Field(max_length=200)


def main(model: str) -> None:
    client = LLMClient()
    print(f"Using model: {model}")
    # Example 1: Extract person information
    print("=" * 50)
    print("Example 1: Extract Person")
    print("=" * 50)

    person = client.complete_structured(
        model=model,
        messages=[
            {
                "role": "user",
                "content": "John Smith is a 35-year-old software engineer from Seattle.",
            }
        ],
        response_model=Person,
    )

    print(f"Name: {person.name}")
    print(f"Age: {person.age}")
    print(f"Occupation: {person.occupation}")

    # Example 2: Extract with metadata (for cost tracking)
    print("\n" + "=" * 50)
    print("Example 2: Extract with Metadata")
    print("=" * 50)

    review, metadata = client.complete_structured(
        model=model,
        messages=[
            {
                "role": "user",
                "content": """
                Review the movie "Inception" (2010).
                It's a mind-bending sci-fi thriller about dreams within dreams.
                Great visuals and acting, but can be confusing to follow.
                """,
            }
        ],
        response_model=MovieReview,
        include_metadata=True,
    )

    print(f"Title: {review.title}")
    print(f"Rating: {review.rating}/10")
    print(f"Pros: {', '.join(review.pros)}")
    print(f"Cons: {', '.join(review.cons)}")
    print(f"Summary: {review.summary}")
    print(f"\n--- Metadata ---")
    print(f"Cost: ${metadata.cost:.6f}" if metadata.cost else "Cost: N/A")
    print(f"Tokens: {metadata.usage['total_tokens']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the structured output example with optional model selection.")
    parser.add_argument(
        "--model", "-m",
        type=str,
        default="openai/gpt-4o-mini",
        help="Model name to use (default: openai/gpt-4o-mini)",
    )
    args = parser.parse_args()
    main(args.model)
