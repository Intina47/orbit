from __future__ import annotations

from pathlib import Path

import numpy as np

from memory_engine.storage.vector_store import VectorStore


def test_vector_store_numpy_backend_add_search_remove(tmp_path: Path) -> None:
    store = VectorStore(embedding_dim=4, index_path=str(tmp_path / "vectors.idx"))
    store.add("m1", [1.0, 0.0, 0.0, 0.0])
    store.add("m2", [0.9, 0.1, 0.0, 0.0])
    hits = store.search(np.asarray([1.0, 0.0, 0.0, 0.0], dtype=np.float32), top_k=2)
    assert hits
    assert hits[0].memory_id in {"m1", "m2"}

    store.remove_many(["m2"])
    reduced_hits = store.search([1.0, 0.0, 0.0, 0.0], top_k=2)
    assert all(hit.memory_id != "m2" for hit in reduced_hits)


def test_vector_store_save_and_load_numpy_backend(tmp_path: Path) -> None:
    path = tmp_path / "persist.idx"
    first = VectorStore(embedding_dim=3, index_path=str(path))
    first.add("a", [0.5, 0.5, 0.0])
    first.add("b", [0.2, 0.8, 0.0])
    first.save()

    second = VectorStore(embedding_dim=3, index_path=str(path))
    second.load()
    hits = second.search([0.4, 0.6, 0.0], top_k=2)
    assert len(hits) >= 1
