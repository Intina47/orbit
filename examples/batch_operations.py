"""Batch operations with Orbit SDK."""

from orbit import MemoryEngine


def main() -> None:
    engine = MemoryEngine(api_key="<jwt-token>")
    try:
        ingest_responses = engine.ingest_batch(
            [
                {"content": "Event 1", "event_type": "agent_decision"},
                {"content": "Event 2", "event_type": "agent_decision"},
                {"content": "Event 3", "event_type": "agent_decision"},
            ]
        )
        feedback_payload = [
            {"memory_id": item.memory_id, "helpful": True}
            for item in ingest_responses
            if item.stored
        ]
        feedback_responses = engine.feedback_batch(feedback_payload)
        print("Ingested:", len(ingest_responses), "Feedback:", len(feedback_responses))
    finally:
        engine.close()


if __name__ == "__main__":
    main()
