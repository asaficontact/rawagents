"""Example 5: Streaming Responses

This example demonstrates streaming text responses in real-time,
which is useful for chat interfaces and long-form content generation.

Note: Streaming does NOT support tools or structured output in v1.0.

Requirements:
    - Set OPENAI_API_KEY environment variable

Usage:
    uv run python examples/llm_client/05_streaming.py --model openai/gpt-4o-mini
"""

import argparse
import asyncio

from rawagents import AsyncLLM, LLMClient


def sync_streaming_example(model: str) -> None:
    """Demonstrate synchronous streaming."""
    print("=" * 60)
    print("Synchronous Streaming")
    print("=" * 60)

    client = LLMClient()

    print("\nGenerating a short story...\n")
    print("-" * 40)

    for chunk in client.stream(
        model=model,
        messages=[
            {
                "role": "user",
                "content": "Write a very short story (3-4 sentences) about a robot learning to paint.",
            }
        ],
        temperature=0.8,
    ):
        print(chunk, end="", flush=True)

    print("\n" + "-" * 40)
    print("\nStreaming complete!")


async def async_streaming_example(model: str) -> None:
    """Demonstrate asynchronous streaming."""
    print("\n" + "=" * 60)
    print("Asynchronous Streaming")
    print("=" * 60)

    client = AsyncLLMClient()

    print("\nGenerating a haiku...\n")
    print("-" * 40)

    async for chunk in client.stream(
        model=model,
        messages=[
            {"role": "user", "content": "Write a haiku about programming."}
        ],
        temperature=0.9,
    ):
        print(chunk, end="", flush=True)
        await asyncio.sleep(0.01)  # Small delay to visualize streaming

    print("\n" + "-" * 40)
    print("\nAsync streaming complete!")


async def parallel_streams_example(model: str) -> None:
    """Demonstrate multiple parallel streams."""
    print("\n" + "=" * 60)
    print("Parallel Streaming (Async)")
    print("=" * 60)

    client = AsyncLLMClient()

    prompts = [
        "Count from 1 to 5, one number per line.",
        "List 5 colors, one per line.",
        "Name 5 animals, one per line.",
    ]

    async def stream_with_label(label: str, prompt: str) -> None:
        chunks = []
        async for chunk in client.stream(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50,
        ):
            chunks.append(chunk)
        print(f"\n[{label}]: {''.join(chunks)}")

    print("\nStarting 3 parallel streams...")

    await asyncio.gather(
        stream_with_label("Numbers", prompts[0]),
        stream_with_label("Colors", prompts[1]),
        stream_with_label("Animals", prompts[2]),
    )

    print("\nAll streams complete!")


def main(model: str) -> None:
    # Run sync example
    sync_streaming_example(model)

    # Run async examples
    asyncio.run(async_streaming_example(model))
    asyncio.run(parallel_streams_example(model))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run streaming LLM examples with optional model selection.")
    parser.add_argument(
        "--model", "-m",
        type=str,
        default="openai/gpt-4o-mini",
        help="Model name to use (default: openai/gpt-4o-mini)",
    )
    args = parser.parse_args()
    main(args.model)
