from __future__ import annotations

from pathlib import Path

import pytest

from memory_engine.config import EngineConfig
from memory_engine.engine import DecisionEngine


@pytest.fixture
def engine(tmp_path: Path) -> DecisionEngine:
    config = EngineConfig(
        sqlite_path=str(tmp_path / "memory.db"),
        metrics_path=str(tmp_path / "metrics.json"),
        embedding_dim=64,
        persistent_confidence_prior=0.0,
        ephemeral_confidence_prior=0.0,
        ranker_min_training_samples=2,
        ranker_training_batch_size=2,
    )
    instance = DecisionEngine(config=config)
    try:
        yield instance
    finally:
        instance.close()
