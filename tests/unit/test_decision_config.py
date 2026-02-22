from __future__ import annotations

import pytest

from decision_engine.config import EngineConfig


def test_decision_engine_config_from_env(monkeypatch) -> None:
    monkeypatch.setenv("MDE_EMBEDDING_DIM", "16")
    monkeypatch.setenv("MDE_PERSISTENT_CONFIDENCE_PRIOR", "0.7")
    monkeypatch.setenv("MDE_ENABLE_ADAPTIVE_PERSONALIZATION", "true")
    monkeypatch.setenv("MDE_PERSONALIZATION_REPEAT_THRESHOLD", "4")
    monkeypatch.setenv("MDE_PERSONALIZATION_SIMILARITY_THRESHOLD", "0.9")
    cfg = EngineConfig.from_env()
    assert cfg.embedding_dim == 16
    assert cfg.persistent_confidence_prior == 0.7
    assert cfg.enable_adaptive_personalization is True
    assert cfg.personalization_repeat_threshold == 4
    assert cfg.personalization_similarity_threshold == 0.9


def test_invalid_embedding_dim_rejected() -> None:
    with pytest.raises(ValueError):
        EngineConfig(embedding_dim=0)


def test_invalid_personalization_threshold_rejected() -> None:
    with pytest.raises(ValueError):
        EngineConfig(personalization_repeat_threshold=1)
