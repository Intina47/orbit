from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import numpy as np
from numpy.typing import NDArray

from decision_engine.math_utils import cosine_similarity
from decision_engine.models import (
    EncodedEvent,
    MemoryRecord,
    StorageDecision,
    StorageTier,
)
from decision_engine.vector_codec import decode_vector, encode_vector


class SQLiteStorageManager:
    """SQLite-backed memory storage with embedding-based candidate search."""

    def __init__(
        self,
        db_path: str,
        *,
        max_content_chars: int = 4000,
        assistant_max_content_chars: int = 900,
        store_raw_embedding: bool = False,
    ) -> None:
        path = Path(db_path)
        if path.parent and not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._max_content_chars = max_content_chars
        self._assistant_max_content_chars = assistant_max_content_chars
        self._store_raw_embedding = store_raw_embedding
        self._connection = sqlite3.connect(
            db_path,
            check_same_thread=False,
            timeout=30.0,
        )
        self._connection.row_factory = sqlite3.Row
        self._configure_connection()
        self._initialize_schema()

    def _configure_connection(self) -> None:
        try:
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA synchronous=NORMAL")
            self._connection.execute("PRAGMA busy_timeout=30000")
        except sqlite3.DatabaseError:
            return

    def _initialize_schema(self) -> None:
        with self._lock:
            self._connection.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    memory_id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    intent TEXT NOT NULL,
                    entities_json TEXT NOT NULL,
                    relationships_json TEXT NOT NULL,
                    raw_embedding_json TEXT NOT NULL,
                    semantic_embedding_json TEXT NOT NULL,
                    semantic_key TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    retrieval_count INTEGER NOT NULL DEFAULT 0,
                    avg_outcome_signal REAL NOT NULL DEFAULT 0.0,
                    outcome_count INTEGER NOT NULL DEFAULT 0,
                    storage_tier TEXT NOT NULL,
                    latest_importance REAL NOT NULL,
                    is_compressed INTEGER NOT NULL DEFAULT 0,
                    original_count INTEGER NOT NULL DEFAULT 1
                )
                """)
            self._ensure_column("is_compressed", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("original_count", "INTEGER NOT NULL DEFAULT 1")
            self._connection.commit()

    def _ensure_column(self, column_name: str, column_definition: str) -> None:
        with self._lock:
            cursor = self._connection.execute("PRAGMA table_info(memories)")
            existing = {str(row[1]) for row in cursor.fetchall()}
            if column_name in existing:
                return
            self._connection.execute(
                f"ALTER TABLE memories ADD COLUMN {column_name} {column_definition}"
            )

    def store(
        self, encoded_event: EncodedEvent, decision: StorageDecision
    ) -> MemoryRecord:
        memory_id = str(uuid4())
        now = datetime.now(UTC)
        intent = encoded_event.understanding.intent
        content = self._truncate_content(encoded_event.event.content, intent=intent)
        raw_embedding = (
            encoded_event.raw_embedding if self._store_raw_embedding else []
        )
        record = MemoryRecord(
            memory_id=memory_id,
            event_id=encoded_event.event.event_id,
            content=content,
            summary=encoded_event.understanding.summary,
            intent=intent,
            entities=encoded_event.understanding.entities,
            relationships=encoded_event.understanding.relationships,
            raw_embedding=raw_embedding,
            semantic_embedding=encoded_event.semantic_embedding,
            semantic_key=encoded_event.semantic_key,
            created_at=now,
            updated_at=now,
            retrieval_count=0,
            avg_outcome_signal=0.0,
            storage_tier=decision.tier,
            latest_importance=decision.confidence,
            is_compressed=bool(decision.trace.get("is_compressed", False)),
            original_count=int(decision.trace.get("original_count", 1)),
        )
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO memories (
                    memory_id, event_id, content, summary, intent, entities_json,
                    relationships_json, raw_embedding_json, semantic_embedding_json,
                    semantic_key, created_at, updated_at, retrieval_count,
                    avg_outcome_signal, outcome_count, storage_tier, latest_importance,
                    is_compressed, original_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.memory_id,
                    record.event_id,
                    record.content,
                    record.summary,
                    record.intent,
                    self._dumps_compact(record.entities),
                    self._dumps_compact(record.relationships),
                    self._dumps_vector(record.raw_embedding),
                    self._dumps_vector(record.semantic_embedding),
                    record.semantic_key,
                    record.created_at.isoformat(),
                    record.updated_at.isoformat(),
                    record.retrieval_count,
                    record.avg_outcome_signal,
                    0,
                    record.storage_tier.value,
                    record.latest_importance,
                    1 if record.is_compressed else 0,
                    record.original_count,
                ),
            )
            self._connection.commit()
        return record

    def count_memories(self) -> int:
        with self._lock:
            cursor = self._connection.execute("SELECT COUNT(*) FROM memories")
            row = cursor.fetchone()
            if row is None:
                return 0
            return int(row[0])

    def list_memories(self, limit: int | None = None) -> list[MemoryRecord]:
        with self._lock:
            if limit is None:
                cursor = self._connection.execute("SELECT * FROM memories")
            else:
                cursor = self._connection.execute(
                    "SELECT * FROM memories LIMIT ?", (limit,)
                )
            rows = cursor.fetchall()
        return [self._row_to_memory(row) for row in rows]

    def fetch_by_ids(self, memory_ids: list[str]) -> list[MemoryRecord]:
        if not memory_ids:
            return []
        with self._lock:
            placeholders = ", ".join("?" for _ in memory_ids)
            cursor = self._connection.execute(
                f"SELECT * FROM memories WHERE memory_id IN ({placeholders})",
                tuple(memory_ids),
            )
            rows = cursor.fetchall()
        return [self._row_to_memory(row) for row in rows]

    def fetch_by_entity_and_intent(
        self,
        entity_id: str,
        intent: str,
        since_iso: str | None = None,
    ) -> list[MemoryRecord]:
        with self._lock:
            if since_iso is None:
                cursor = self._connection.execute(
                    "SELECT * FROM memories WHERE intent = ?",
                    (intent,),
                )
            else:
                cursor = self._connection.execute(
                    "SELECT * FROM memories WHERE intent = ? AND created_at >= ?",
                    (intent, since_iso),
                )
            rows = cursor.fetchall()
        records = [self._row_to_memory(row) for row in rows]
        return [record for record in records if entity_id in record.entities]

    def search_candidates(
        self, query_embedding: NDArray[np.float32], top_k: int
    ) -> list[MemoryRecord]:
        memories = self.list_memories()
        if not memories:
            return []
        scored = []
        for memory in memories:
            semantic_embedding = np.array(memory.semantic_embedding, dtype=np.float32)
            if semantic_embedding.shape != query_embedding.shape:
                continue
            score = cosine_similarity(query_embedding, semantic_embedding)
            scored.append((memory, score))
        if not scored:
            return []
        scored.sort(key=lambda item: item[1], reverse=True)
        return [memory for memory, _ in scored[:top_k]]

    def update_retrieval(self, memory_id: str) -> None:
        with self._lock:
            self._connection.execute(
                """
                UPDATE memories
                SET retrieval_count = retrieval_count + 1,
                    updated_at = ?
                WHERE memory_id = ?
                """,
                (datetime.now(UTC).isoformat(), memory_id),
            )
            self._connection.commit()

    def update_outcome(self, memory_id: str, outcome_signal: float) -> None:
        with self._lock:
            cursor = self._connection.execute(
                "SELECT avg_outcome_signal, outcome_count FROM memories WHERE memory_id = ?",
                (memory_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return
            avg = float(row["avg_outcome_signal"])
            count = int(row["outcome_count"])
            new_count = count + 1
            new_avg = ((avg * count) + outcome_signal) / new_count
            self._connection.execute(
                """
                UPDATE memories
                SET avg_outcome_signal = ?, outcome_count = ?, updated_at = ?
                WHERE memory_id = ?
                """,
                (new_avg, new_count, datetime.now(UTC).isoformat(), memory_id),
            )
            self._connection.commit()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def delete_memories(self, memory_ids: list[str]) -> None:
        if not memory_ids:
            return
        with self._lock:
            placeholders = ", ".join("?" for _ in memory_ids)
            self._connection.execute(
                f"DELETE FROM memories WHERE memory_id IN ({placeholders})",
                tuple(memory_ids),
            )
            self._connection.commit()

    def _truncate_content(self, content: str, intent: str) -> str:
        normalized_intent = intent.strip().lower()
        limit = (
            self._assistant_max_content_chars
            if normalized_intent.startswith("assistant_")
            else self._max_content_chars
        )
        if len(content) <= limit:
            return content
        if limit <= 64:
            return content[:limit]
        omitted = len(content) - limit
        return (
            content[: limit - 48].rstrip()
            + f"\n\n...[truncated {omitted} chars for storage efficiency]"
        )

    @staticmethod
    def _dumps_compact(value: list[str] | list[float]) -> str:
        return json.dumps(value, ensure_ascii=True, separators=(",", ":"))

    @staticmethod
    def _dumps_vector(values: list[float]) -> str:
        return encode_vector(values)

    @staticmethod
    def _row_to_memory(row: sqlite3.Row) -> MemoryRecord:
        semantic_embedding = decode_vector(str(row["semantic_embedding_json"]))
        raw_embedding = decode_vector(str(row["raw_embedding_json"]))
        if not raw_embedding or len(raw_embedding) != len(semantic_embedding):
            raw_embedding = semantic_embedding.copy()
        return MemoryRecord(
            memory_id=str(row["memory_id"]),
            event_id=str(row["event_id"]),
            content=str(row["content"]),
            summary=str(row["summary"]),
            intent=str(row["intent"]),
            entities=[str(item) for item in json.loads(str(row["entities_json"]))],
            relationships=[
                str(item) for item in json.loads(str(row["relationships_json"]))
            ],
            raw_embedding=raw_embedding,
            semantic_embedding=semantic_embedding,
            semantic_key=str(row["semantic_key"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
            retrieval_count=int(row["retrieval_count"]),
            avg_outcome_signal=float(row["avg_outcome_signal"]),
            storage_tier=StorageTier(str(row["storage_tier"])),
            latest_importance=float(row["latest_importance"]),
            is_compressed=bool(int(row["is_compressed"])),
            original_count=int(row["original_count"]),
        )
