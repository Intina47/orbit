from __future__ import annotations

from pathlib import Path

from decision_engine.config import EngineConfig
from decision_engine.engine import DecisionEngine
from decision_engine.models import OutcomeFeedback, RawEvent
from decision_engine.semantic_encoding import (
    ContextSemanticProvider,
    DeterministicEmbeddingProvider,
)


def test_end_to_end_event_retrieve_feedback(tmp_path: Path) -> None:
    config = EngineConfig(
        sqlite_path=str(tmp_path / "memory.db"),
        embedding_dim=32,
        persistent_confidence_prior=0.0,
        ephemeral_confidence_prior=0.0,
        ranker_min_training_samples=2,
        ranker_training_batch_size=2,
    )
    engine = DecisionEngine(
        config=config,
        embedding_provider=DeterministicEmbeddingProvider(embedding_dim=32),
        semantic_provider=ContextSemanticProvider(),
    )

    try:
        for idx in range(3):
            event = RawEvent(
                content=f"Developer debugged production issue {idx}",
                context={
                    "summary": "Debugged prod issue",
                    "intent": "incident_resolution",
                    "entities": ["service:api", "env:prod"],
                    "relationships": ["developer->service:api"],
                },
            )
            decision, stored = engine.process_event(event)
            assert decision.should_store
            assert stored is not None

        assert engine.memory_count() == 3

        retrieved = engine.retrieve("prod api incident", top_k=2)
        assert len(retrieved) == 2

        feedback = OutcomeFeedback(
            query="prod api incident",
            ranked_memory_ids=[item.memory.memory_id for item in retrieved],
            helpful_memory_ids=[retrieved[0].memory.memory_id],
            outcome_signal=1.0,
        )
        losses = engine.record_feedback(feedback)
        assert losses["importance_loss"] is not None
    finally:
        engine.close()
