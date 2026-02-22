from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import torch
from torch import nn


class ImportanceModel:
    """Neural network that predicts storage importance from semantic embeddings."""

    def __init__(self, embedding_dim: int, learning_rate: float = 1e-3) -> None:
        self._model: nn.Module = nn.Sequential(
            nn.Linear(embedding_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(128, 1),
            nn.Sigmoid(),
        )
        self._loss_fn: nn.Module = nn.BCELoss()
        self._optimizer = torch.optim.Adam(self._model.parameters(), lr=learning_rate)

    def predict(self, embedding: Sequence[float]) -> float:
        self._model.eval()
        with torch.no_grad():
            input_tensor = torch.tensor([embedding], dtype=torch.float32)
            prediction = self._model(input_tensor).item()
        return float(prediction)

    def train_batch(
        self, embeddings: Sequence[Sequence[float]], outcomes: Sequence[float]
    ) -> float:
        if not embeddings:
            msg = "embeddings batch must not be empty"
            raise ValueError(msg)
        if len(embeddings) != len(outcomes):
            msg = "embeddings and outcomes must have the same length"
            raise ValueError(msg)

        self._model.train()
        inputs = torch.tensor(np.array(embeddings), dtype=torch.float32)
        # Outcomes are expected in [-1, 1], convert to [0, 1].
        targets = torch.tensor(
            [(value + 1.0) / 2.0 for value in outcomes], dtype=torch.float32
        )
        targets = targets.unsqueeze(1).clamp(0.0, 1.0)

        predictions = self._model(inputs)
        loss = self._loss_fn(predictions, targets)
        self._optimizer.zero_grad()
        loss.backward()
        self._optimizer.step()
        return float(loss.item())
