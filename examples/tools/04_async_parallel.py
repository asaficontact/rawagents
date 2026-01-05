"""Async parallel execution of tools.

This example demonstrates how the ToolExecutor supports async tools natively,
allowing for high-concurrency operations (like searching multiple sources).
"""

import asyncio
import time
from rawagents.tools import tool, ToolExecutor
from rawagents.utils.types import ToolCall

# 1. Define slow async tool
@tool
async def slow_search(source: str) -> str:
    """Simulate a slow network search."""
    print(f"Start searching {source}...")
    await asyncio.sleep(1.0)  # Simulate I/O
    print(f"Finished searching {source}.")
    return f"Results from {source}"

async def main():
    executor = ToolExecutor([slow_search])
    
    # 2. Create multiple calls
    sources = ["Google", "Bing", "DuckDuckGo", "Wikipedia"]
    calls = [
        ToolCall(id=f"call_{i}", name="slow_search", arguments={"source": src})
        for i, src in enumerate(sources)
    ]
    
    print(f"--- Starting {len(calls)} parallel searches ---")
    start_time = time.perf_counter()
    
    # 3. Execute all in parallel using asyncio.gather
    # ToolExecutor.execute is async, so it doesn't block!
    tasks = [executor.execute(call) for call in calls]
    results = await asyncio.gather(*tasks)
    
    end_time = time.perf_counter()
    duration = end_time - start_time
    
    print("\n--- Results ---")
    for res in results:
        print(res.content)
        
    print(f"\nTotal time: {duration:.2f}s")
    # Should be ~1.0s, not 4.0s (proof of parallelism)
    assert duration < 1.5
    print("Success: Execution was parallel.")

if __name__ == "__main__":
    asyncio.run(main())

