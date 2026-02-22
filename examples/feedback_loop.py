"""Feedback workflow example."""

from orbit import MemoryEngine


def main() -> None:
    engine = MemoryEngine(api_key="<jwt-token>")
    try:
        results = engine.retrieve("What happened last time?", limit=3)
        if not results.memories:
            return
        memory = results.memories[0]
        feedback = engine.feedback(
            memory_id=memory.memory_id,
            helpful=True,
            outcome_value=0.9,
        )
        print("Feedback recorded:", feedback.recorded)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
