"""Minimal adaptive personalization signal flow."""

from orbit import MemoryEngine


def main() -> None:
    engine = MemoryEngine(api_key="<jwt-token>")
    user_id = "alice"

    try:
        # Repeated topic signals trigger inferred_learning_pattern memories.
        for _ in range(3):
            engine.ingest(
                content="I still don't understand Python for loops.",
                event_type="user_question",
                entity_id=user_id,
            )

        # Assistant responses + feedback drive inferred_preference memories.
        response = engine.ingest(
            content="Use a for loop when you need to repeat steps a fixed number of times.",
            event_type="assistant_response",
            entity_id=user_id,
        )
        engine.feedback(memory_id=response.memory_id, helpful=True, outcome_value=1.0)

        memories = engine.retrieve(
            query="What should I know about Alice's weak spots and preferences?",
            entity_id=user_id,
            limit=10,
        )
        for memory in memories.memories:
            intent = memory.metadata.get("intent", "unknown")
            print(f"[{intent}] {memory.content}")
    finally:
        engine.close()


if __name__ == "__main__":
    main()
