from __future__ import annotations

import math
from collections.abc import Iterable
from datetime import datetime
from typing import Any

import numpy as np
import torch
from numpy.typing import NDArray
from torch import nn

from decision_engine.math_utils import cosine_similarity
from decision_engine.models import MemoryRecord, RetrievedMemory

FloatArray = NDArray[np.floating[Any]]


class RetrievalRanker:
    """Learned retrieval ranker with similarity fallback before warm-up."""

    _FEATURE_DIM = 8
    _INTENT_PRIORS = {
        "preference_stated": 1.28,
        "learning_progress": 1.22,
        "user_profile": 1.30,
        "user_fact": 1.24,
        "user_question": 1.06,
        "inferred_learning_pattern": 1.26,
        "inferred_preference": 1.32,
        "inferred_user_fact": 1.34,
        "inferred_user_fact_conflict": 1.36,
        "assistant_response": 0.50,
        "assistant_message": 0.55,
    }

    def __init__(
        self,
        learning_rate: float = 1e-3,
        min_training_samples: int = 100,
        training_batch_size: int = 64,
    ) -> None:
        self._model: nn.Module = nn.Sequential(
            nn.Linear(self._FEATURE_DIM, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid(),
        )
        self._optimizer = torch.optim.Adam(self._model.parameters(), lr=learning_rate)
        self._loss_fn: nn.Module = nn.BCELoss()
        self._min_training_samples = min_training_samples
        self._training_batch_size = training_batch_size
        self._training_samples = 0
        self._feature_buffer: list[NDArray[np.float32]] = []
        self._label_buffer: list[float] = []

    @property
    def is_trained(self) -> bool:
        return self._training_samples >= self._min_training_samples

    def rank(
        self,
        query_embedding: FloatArray,
        candidates: Iterable[MemoryRecord],
        now: datetime,
    ) -> list[RetrievedMemory]:
        candidate_list = list(candidates)
        if not candidate_list:
            return []

        features = np.stack(
            [
                self._feature_vector(query_embedding, memory, now)
                for memory in candidate_list
            ]
        )
        scores = self._predict_scores(features)
        ranked = sorted(
            (
                RetrievedMemory(memory=memory, rank_score=float(score))
                for memory, score in zip(candidate_list, scores, strict=False)
            ),
            key=lambda item: item.rank_score,
            reverse=True,
        )
        return ranked

    def learn_from_feedback(
        self,
        query_embedding: FloatArray,
        candidates: Iterable[MemoryRecord],
        helpful_memory_ids: set[str],
        now: datetime,
    ) -> float | None:
        candidate_list = list(candidates)
        if not candidate_list:
            return None

        for memory in candidate_list:
            features = self._feature_vector(query_embedding, memory, now)
            label = 1.0 if memory.memory_id in helpful_memory_ids else 0.0
            self._feature_buffer.append(features)
            self._label_buffer.append(label)

        if len(self._feature_buffer) < self._training_batch_size:
            return None
        return self._train_from_buffer()

    def _predict_scores(self, features: FloatArray) -> NDArray[np.float32]:
        heuristic_scores = np.asarray(
            [self._fallback_score(vector) for vector in features],
            dtype=np.float32,
        )
        if not self.is_trained:
            return heuristic_scores
        self._model.eval()
        with torch.no_grad():
            tensor = torch.tensor(features, dtype=torch.float32)
            predictions = self._model(tensor).squeeze(1).detach().cpu().numpy()
        blended = (0.8 * predictions) + (0.2 * heuristic_scores)
        return np.asarray(np.clip(blended, 0.0, 1.0), dtype=np.float32)

    def _feature_vector(
        self, query_embedding: FloatArray, memory: MemoryRecord, now: datetime
    ) -> NDArray[np.float32]:
        semantic_embedding = np.array(memory.semantic_embedding, dtype=np.float32)
        raw_embedding = np.array(memory.raw_embedding, dtype=np.float32)
        semantic_similarity = self._safe_similarity(
            query_embedding, semantic_embedding, fallback=0.0
        )
        raw_similarity = self._safe_similarity(
            query_embedding,
            raw_embedding,
            fallback=semantic_similarity,
        )
        age_days = max((now - memory.created_at).total_seconds() / 86400.0, 0.0)
        summary_words = self._word_count(memory.summary)
        content_words = self._word_count(memory.content)
        return np.array(
            [
                semantic_similarity,
                raw_similarity,
                math.exp(-0.03 * age_days),
                self._clamp01(math.log1p(memory.retrieval_count) / 4.0),
                (memory.avg_outcome_signal + 1.0) / 2.0,
                self._clamp01(memory.latest_importance),
                self._length_penalty(summary_words, content_words),
                self._intent_prior(memory.intent),
            ],
            dtype=np.float32,
        )

    def _fallback_score(self, features: NDArray[np.float32]) -> float:
        semantic_signal = (float(features[0]) + 1.0) / 2.0
        raw_signal = (float(features[1]) + 1.0) / 2.0
        recency_signal = float(features[2])
        retrieval_signal = float(features[3])
        outcome_signal = float(features[4])
        importance_signal = float(features[5])
        length_penalty = float(features[6])
        intent_prior = float(features[7])

        base_score = (
            0.41 * semantic_signal
            + 0.09 * raw_signal
            + 0.05 * recency_signal
            + 0.05 * retrieval_signal
            + 0.09 * outcome_signal
            + 0.31 * importance_signal
        )
        adjusted = base_score * length_penalty * intent_prior
        return self._clamp01(adjusted)

    @staticmethod
    def _word_count(text: str) -> int:
        return len([token for token in text.strip().split() if token])

    @classmethod
    def _intent_prior(cls, intent: str) -> float:
        normalized = intent.strip().lower()
        if not normalized:
            return 1.0
        if normalized.startswith("assistant_"):
            return 0.5
        return cls._INTENT_PRIORS.get(normalized, 1.0)

    @staticmethod
    def _length_penalty(summary_words: int, content_words: int) -> float:
        penalty = 1.0
        if summary_words > 20:
            penalty -= min((summary_words - 20) / 160.0, 0.30)
        if content_words > 96:
            penalty -= min((content_words - 96) / 320.0, 0.35)
        return max(0.35, penalty)

    @staticmethod
    def _clamp01(value: float) -> float:
        return min(max(value, 0.0), 1.0)

    @staticmethod
    def _safe_similarity(
        query_embedding: FloatArray,
        candidate_embedding: FloatArray,
        fallback: float,
    ) -> float:
        if candidate_embedding.size == 0:
            return fallback
        if query_embedding.shape != candidate_embedding.shape:
            return fallback
        return cosine_similarity(query_embedding, candidate_embedding)

    def _train_from_buffer(self) -> float:
        features = np.array(self._feature_buffer, dtype=np.float32)
        labels = np.array(self._label_buffer, dtype=np.float32)

        self._model.train()
        tensor_features = torch.tensor(features, dtype=torch.float32)
        tensor_labels = torch.tensor(labels, dtype=torch.float32).unsqueeze(1)
        predictions = self._model(tensor_features)
        loss = self._loss_fn(predictions, tensor_labels)

        self._optimizer.zero_grad()
        loss.backward()
        self._optimizer.step()

        self._training_samples += len(self._feature_buffer)
        self._feature_buffer.clear()
        self._label_buffer.clear()
        return float(loss.item())
