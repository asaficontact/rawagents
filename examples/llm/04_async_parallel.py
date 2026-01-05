"""Example 4: Async and Parallel Requests

This example demonstrates using the async client for parallel LLM requests,
which can significantly speed up batch processing.

Requirements:
    - Set OPENAI_API_KEY environment variable

Usage:
    uv run python examples/llm_client/04_async_parallel.py --model openai/gpt-4o-mini
"""

import argparse
import asyncio
import time
import json

from pydantic import BaseModel

from rawagents import AsyncLLM, LLMConfig


class Sentiment(BaseModel):
    """Sentiment analysis result."""

    text: str
    sentiment: str  # positive, negative, neutral
    confidence: float


async def analyze_single(
    client: AsyncLLMClient, text: str, model: str
) -> tuple[str, Sentiment]:
    """Analyze sentiment of a single text."""
    result = await client.complete_structured(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "Analyze the sentiment of the given text. Return positive, negative, or neutral.",
            },
            {"role": "user", "content": text},
        ],
        response_model=Sentiment,
    )
    return text, result


async def main(model: str) -> None:
    # Sample texts to analyze
    texts = [
        "I absolutely love this product! Best purchase ever!",
        "This is the worst experience I've ever had.",
        "The weather is nice today.",
        "I'm so frustrated with the customer service.",
        "Just finished my morning coffee.",
        "Amazing performance, exceeded all expectations!",
    ]

    config = LLMConfig(model=model)
    client = AsyncLLMClient(config=config)
    print(f"Using model: {model}")

    # Sequential processing (for comparison)
    print("=" * 60)
    print("Sequential Processing")
    print("=" * 60)

    start = time.perf_counter()
    sequential_results = []
    for text in texts[:3]:  # Only do 3 for speed
        _, result = await analyze_single(client, text, model)
        sequential_results.append(result)
    sequential_time = time.perf_counter() - start
    print(f"Time for 3 texts (sequential): {sequential_time:.2f}s")

    # Parallel processing
    print("\n" + "=" * 60)
    print("Parallel Processing")
    print("=" * 60)

    start = time.perf_counter()
    tasks = [analyze_single(client, text, model) for text in texts]
    results = await asyncio.gather(*tasks)
    parallel_time = time.perf_counter() - start

    print(f"Time for {len(texts)} texts (parallel): {parallel_time:.2f}s")
    print(f"Speedup: {(sequential_time / 3 * len(texts)) / parallel_time:.1f}x")

    # Print Raw Result
    print(results)

    # Print results
    print("\n" + "=" * 60)
    print("Results")
    print("=" * 60)

    for text, sentiment in results:
        emoji = {"positive": "😊", "negative": "😞", "neutral": "😐"}.get(
            sentiment.sentiment, "❓"
        )
        print(f"{emoji} [{sentiment.sentiment}] ({sentiment.confidence:.0%})")
        print(f"   \"{text[:50]}...\"" if len(text) > 50 else f"   \"{text}\"")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the async/parallel LLM example with optional model selection.")
    parser.add_argument(
        "--model", "-m",
        type=str,
        default="openai/gpt-4o-mini",
        help="Model name to use (default: openai/gpt-4o-mini)",
    )
    args = parser.parse_args()
    asyncio.run(main(args.model))
