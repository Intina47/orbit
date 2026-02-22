from __future__ import annotations

from memory_engine.config import EngineConfig
from memory_engine.stage3_learning.feedback import FeedbackSignal


def test_feedback_signal_defaults() -> None:
    feedback = FeedbackSignal(
        memory_id="m1",
        semantic_key="k1",
        memory_age_days=2.0,
        outcome="success",
        outcome_signal=1.0,
    )
    assert feedback.memory_id == "m1"
    assert feedback.observed_at is not None


def test_engine_config_from_env(monkeypatch) -> None:
    monkeypatch.setenv("MDE_COMPRESSION_MIN_COUNT", "6")
    monkeypatch.setenv("MDE_METRICS_FLUSH_INTERVAL", "25")
    monkeypatch.setenv("MDE_PERSONALIZATION_MIN_FEEDBACK_EVENTS", "5")
    cfg = EngineConfig.from_env()
    assert cfg.compression_min_count == 6
    assert cfg.metrics_flush_interval == 25
    assert cfg.personalization_min_feedback_events == 5
