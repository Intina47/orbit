from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from decision_engine.math_utils import to_unit_vector

try:
    import faiss
except ImportError:  # pragma: no cover - optional dependency
    faiss = None


@dataclass(frozen=True)
class VectorHit:
    memory_id: str
    score: float


class VectorStore:
    """Optional FAISS vector store with a numpy fallback backend."""

    def __init__(self, embedding_dim: int, index_path: str = "faiss_index.idx") -> None:
        self._embedding_dim = embedding_dim
        self._index_path = Path(index_path)
        self._use_faiss = faiss is not None
        self._lock = threading.RLock()
        self._memory_ids: list[str] = []
        self._vectors: dict[str, np.ndarray[Any, np.dtype[np.float32]]] = {}
        self._cache_dirty = True
        self._cached_ids: list[str] = []
        self._cached_matrix: np.ndarray[Any, np.dtype[np.float32]] | None = None

        if self._use_faiss:  # pragma: no cover - optional dependency path
            self._index: Any = faiss.IndexFlatIP(embedding_dim)
        else:
            self._index = None

    @property
    def backend(self) -> str:
        return "faiss" if self._use_faiss else "numpy"

    def add(self, memory_id: str, vector: list[float]) -> None:
        with self._lock:
            embedding = to_unit_vector(np.asarray(vector, dtype=np.float32))
            self._vectors[memory_id] = embedding
            self._cache_dirty = True
            if self._use_faiss:  # pragma: no cover - optional dependency path
                self._memory_ids.append(memory_id)
                self._index.add(np.asarray([embedding], dtype=np.float32))

    def remove_many(self, memory_ids: list[str]) -> None:
        with self._lock:
            for memory_id in memory_ids:
                self._vectors.pop(memory_id, None)
            self._cache_dirty = True
            if self._use_faiss:  # pragma: no cover - optional dependency path
                self._rebuild_faiss_index()

    def search(
        self,
        query_vector: list[float] | np.ndarray[Any, np.dtype[np.float32]],
        top_k: int,
    ) -> list[VectorHit]:
        with self._lock:
            if top_k <= 0:
                return []
            query = to_unit_vector(np.asarray(query_vector, dtype=np.float32))
            if (
                self._use_faiss and self._memory_ids
            ):  # pragma: no cover - optional dependency path
                distances, indices = self._index.search(
                    np.asarray([query], dtype=np.float32), top_k
                )
                hits: list[VectorHit] = []
                for score, idx in zip(distances[0], indices[0], strict=False):
                    if idx < 0 or idx >= len(self._memory_ids):
                        continue
                    hits.append(
                        VectorHit(memory_id=self._memory_ids[idx], score=float(score))
                    )
                return hits

            ids, matrix = self._numpy_cache()
            if matrix.size == 0:
                return []
            scores = matrix @ query
            candidate_count = min(top_k, scores.shape[0])
            if candidate_count <= 0:
                return []
            if candidate_count == scores.shape[0]:
                top_indices = np.argsort(scores)[::-1]
            else:
                partial = np.argpartition(-scores, candidate_count - 1)[:candidate_count]
                top_indices = partial[np.argsort(scores[partial])[::-1]]
            return [
                VectorHit(memory_id=ids[int(index)], score=float(scores[int(index)]))
                for index in top_indices
            ]

    def save(self) -> None:
        with self._lock:
            if self._use_faiss:  # pragma: no cover - optional dependency path
                faiss.write_index(self._index, str(self._index_path))
                ids_path = self._index_path.with_suffix(".ids.npy")
                np.save(str(ids_path), np.asarray(self._memory_ids, dtype=object))
                return
            np.savez(
                str(self._index_path.with_suffix(".npz")),
                memory_ids=np.asarray(list(self._vectors.keys()), dtype=object),
                vectors=np.asarray(list(self._vectors.values()), dtype=np.float32),
            )

    def load(self) -> None:
        with self._lock:
            if (
                self._use_faiss and self._index_path.exists()
            ):  # pragma: no cover - optional dependency path
                self._index = faiss.read_index(str(self._index_path))
                ids_path = self._index_path.with_suffix(".ids.npy")
                if ids_path.exists():
                    loaded_ids = np.load(str(ids_path), allow_pickle=True)
                    self._memory_ids = [str(value) for value in loaded_ids.tolist()]
                return
            npz_path = self._index_path.with_suffix(".npz")
            if not npz_path.exists():
                return
            data = np.load(str(npz_path), allow_pickle=True)
            ids = [str(value) for value in data["memory_ids"].tolist()]
            vectors = np.asarray(data["vectors"], dtype=np.float32)
            self._vectors = {
                memory_id: vectors[idx] for idx, memory_id in enumerate(ids)
            }
            self._cache_dirty = True

    def _rebuild_faiss_index(self) -> None:
        if not self._use_faiss:  # pragma: no cover - optional dependency path
            return
        self._index = faiss.IndexFlatIP(self._embedding_dim)
        self._memory_ids = list(self._vectors.keys())
        if self._memory_ids:
            vectors = np.asarray(
                [self._vectors[memory_id] for memory_id in self._memory_ids],
                dtype=np.float32,
            )
            self._index.add(vectors)

    def _numpy_cache(
        self,
    ) -> tuple[list[str], np.ndarray[Any, np.dtype[np.float32]]]:
        if not self._cache_dirty and self._cached_matrix is not None:
            return self._cached_ids, self._cached_matrix
        if not self._vectors:
            self._cached_ids = []
            self._cached_matrix = np.asarray([], dtype=np.float32)
            self._cache_dirty = False
            return self._cached_ids, self._cached_matrix
        self._cached_ids = list(self._vectors.keys())
        self._cached_matrix = np.asarray(
            [self._vectors[memory_id] for memory_id in self._cached_ids],
            dtype=np.float32,
        )
        self._cache_dirty = False
        return self._cached_ids, self._cached_matrix
