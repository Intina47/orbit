from __future__ import annotations

import os

from decision_engine.config import EngineConfig as CoreEngineConfig


class EngineConfig(CoreEngineConfig):
    """Compatibility config for v1 module layout with intelligent-first defaults."""

    compression_min_count: int = 5
    compression_window_days: int = 7
    compression_max_items_in_summary: int = 20
    metrics_path: str = "metrics.json"
    metrics_flush_interval: int = 50

    @classmethod
    def from_env(cls) -> EngineConfig:
        base = CoreEngineConfig.from_env()
        return cls(
            embedding_dim=base.embedding_dim,
            sqlite_path=base.sqlite_path,
            database_url=base.database_url,
            max_content_chars=base.max_content_chars,
            assistant_max_content_chars=base.assistant_max_content_chars,
            store_raw_embedding=base.store_raw_embedding,
            assistant_response_max_share=base.assistant_response_max_share,
            enable_adaptive_personalization=base.enable_adaptive_personalization,
            personalization_repeat_threshold=base.personalization_repeat_threshold,
            personalization_similarity_threshold=base.personalization_similarity_threshold,
            personalization_window_days=base.personalization_window_days,
            personalization_min_feedback_events=base.personalization_min_feedback_events,
            personalization_preference_margin=base.personalization_preference_margin,
            persistent_confidence_prior=base.persistent_confidence_prior,
            ephemeral_confidence_prior=base.ephemeral_confidence_prior,
            importance_learning_rate=base.importance_learning_rate,
            ranker_learning_rate=base.ranker_learning_rate,
            decay_learning_rate=base.decay_learning_rate,
            ranker_min_training_samples=base.ranker_min_training_samples,
            ranker_training_batch_size=base.ranker_training_batch_size,
            compression_min_count=int(os.getenv("MDE_COMPRESSION_MIN_COUNT", "5")),
            compression_window_days=int(os.getenv("MDE_COMPRESSION_WINDOW_DAYS", "7")),
            compression_max_items_in_summary=int(
                os.getenv("MDE_COMPRESSION_MAX_ITEMS_IN_SUMMARY", "20")
            ),
            metrics_path=os.getenv("MDE_METRICS_PATH", "metrics.json"),
            metrics_flush_interval=int(os.getenv("MDE_METRICS_FLUSH_INTERVAL", "50")),
        )
