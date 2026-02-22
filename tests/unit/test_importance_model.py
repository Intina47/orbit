from __future__ import annotations

import numpy as np
import torch

from decision_engine.importance_model import ImportanceModel


def test_importance_model_learns_separation() -> None:
    torch.manual_seed(42)
    np.random.seed(42)

    model = ImportanceModel(embedding_dim=8, learning_rate=1e-2)

    positive = np.array([1.0, 0.8, 0.7, 0.9, 0.1, 0.2, 0.0, 0.3], dtype=np.float32)
    negative = np.array([0.0, 0.1, 0.2, 0.0, 0.8, 0.7, 0.9, 1.0], dtype=np.float32)

    embeddings = [positive.tolist(), negative.tolist()] * 64
    outcomes = [1.0, -1.0] * 64

    for _ in range(8):
        loss = model.train_batch(embeddings, outcomes)
        assert loss >= 0.0

    pos_score = model.predict(positive.tolist())
    neg_score = model.predict(negative.tolist())

    assert pos_score > neg_score
    assert pos_score > 0.5
    assert neg_score < 0.5
