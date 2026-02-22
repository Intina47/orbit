"""Basic Orbit SDK usage."""

from orbit import MemoryEngine


def main() -> None:
    engine = MemoryEngine(api_key="<jwt-token>")

    ingest = engine.ingest(
        content="User asked about Python for-loops.",
        event_type="user_question",
        entity_id="user_alice",
    )
    print("Ingested:", ingest.memory_id, ingest.stored)

    results = engine.retrieve(
        query="What should I know about user_alice?",
        entity_id="user_alice",
        limit=5,
    )
    for memory in results.memories:
        print(memory.rank_position, memory.content)

    engine.close()


if __name__ == "__main__":
    main()
