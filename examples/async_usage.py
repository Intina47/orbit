"""Async Orbit SDK usage."""

from __future__ import annotations

import asyncio

from orbit import AsyncMemoryEngine


async def main() -> None:
    engine = AsyncMemoryEngine(api_key="<jwt-token>")
    try:
        await engine.ingest(content="Async event", event_type="system_event")
        results = await engine.retrieve(query="What happened?")
        print("Retrieved:", len(results.memories))
    finally:
        await engine.aclose()


if __name__ == "__main__":
    asyncio.run(main())
