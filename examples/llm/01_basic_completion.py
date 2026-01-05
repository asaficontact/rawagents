"""Example 1: Basic Completion

This example demonstrates the simplest usage of LLM
for basic text completion, and now supports setting the model
via a command-line parameter.

Requirements:
    - Set OPENAI_API_KEY environment variable (or use another provider)

Usage:
    python llm/01_basic_completion.py --model openai/gpt-4o-mini
    uv run python examples/llm/01_basic_completion.py --model openai/gpt-4o-mini
"""

import argparse
from rawagents import LLM


def main(model: str) -> None:
    # Create client with defaults
    client = LLM()

    # Simple completion
    response = client.complete(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is the capital of France?"},
        ],
        temperature=0.7,
        max_tokens=1000,
    )

    # Access response data
    print(f"Response: {response.content}")
    print(f"Model: {response.model}")
    print(f"Tokens used: {response.usage}")
    print(f"Cost: ${response.cost:.6f}" if response.cost else "Cost: N/A")
    print(f"Latency: {response.latency_ms:.2f}ms")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a basic LLM completion with optional model selection.")
    parser.add_argument(
        "--model", "-m",
        type=str,
        default="openai/gpt-4o-mini",
        help="Model name to use (default: openai/gpt-4o-mini)",
    )
    args = parser.parse_args()
    main(args.model)
