from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar
from uuid import uuid4

import numpy as np
from numpy.typing import NDArray
from sqlalchemy import create_engine, delete, func, inspect, select, text, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from decision_engine.math_utils import cosine_similarity
from decision_engine.models import EncodedEvent, MemoryRecord, StorageDecision, StorageTier
from decision_engine.vector_codec import decode_vector, encode_vector
from memory_engine.storage.db import Base, MemoryRow

T = TypeVar("T")


class SQLAlchemyStorageManager:
    """SQLAlchemy-backed storage manager compatible with SQLite/PostgreSQL."""

    def __init__(
        self,
        database_url: str,
        *,
        max_content_chars: int = 4000,
        assistant_max_content_chars: int = 900,
        store_raw_embedding: bool = False,
        write_retry_attempts: int = 5,
    ) -> None:
        self._database_url = database_url
        self._max_content_chars = max_content_chars
        self._assistant_max_content_chars = assistant_max_content_chars
        self._store_raw_embedding = store_raw_embedding
        self._write_retry_attempts = max(write_retry_attempts, 1)
        connect_args = (
            {"check_same_thread": False, "timeout": 30.0}
            if database_url.startswith("sqlite")
            else {}
        )
        self._engine: Engine = create_engine(
            database_url,
            future=True,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
        Base.metadata.create_all(self._engine)
        self._ensure_account_key_column()
        self._session_factory = sessionmaker(
            bind=self._engine,
            autoflush=False,
            autocommit=False,
            future=True,
        )

    def store(
        self,
        encoded_event: EncodedEvent,
        decision: StorageDecision,
        account_key: str = "default",
    ) -> MemoryRecord:
        normalized_account_key = self._normalize_account_key(account_key)
        memory_id = str(uuid4())
        now = datetime.now(UTC)
        intent = encoded_event.understanding.intent
        content = self._truncate_content(encoded_event.event.content, intent=intent)
        raw_embedding = (
            encoded_event.raw_embedding if self._store_raw_embedding else []
        )
        record = MemoryRecord(
            account_key=normalized_account_key,
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
        row_payload = {
            "account_key": record.account_key,
            "memory_id": record.memory_id,
            "event_id": record.event_id,
            "content": record.content,
            "summary": record.summary,
            "intent": record.intent,
            "entities_json": self._dumps_compact(record.entities),
            "relationships_json": self._dumps_compact(record.relationships),
            "raw_embedding_json": self._dumps_vector(record.raw_embedding),
            "semantic_embedding_json": self._dumps_vector(record.semantic_embedding),
            "semantic_key": record.semantic_key,
            "retrieval_count": record.retrieval_count,
            "avg_outcome_signal": record.avg_outcome_signal,
            "outcome_count": 0,
            "storage_tier": record.storage_tier.value,
            "latest_importance": record.latest_importance,
            "is_compressed": record.is_compressed,
            "original_count": record.original_count,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }

        def _insert(session: Session) -> None:
            session.add(MemoryRow(**row_payload))

        self._execute_write(_insert)
        return record

    def count_memories(self, account_key: str | None = None) -> int:
        with self._session_factory() as session:
            if account_key is None:
                result = session.execute(text("SELECT COUNT(*) FROM memories"))
            else:
                normalized_account_key = self._normalize_account_key(account_key)
                result = session.execute(
                    text("SELECT COUNT(*) FROM memories WHERE account_key = :account_key"),
                    {"account_key": normalized_account_key},
                )
            value = result.scalar_one_or_none()
            return int(value or 0)

    def list_memories(
        self,
        limit: int | None = None,
        account_key: str | None = None,
    ) -> list[MemoryRecord]:
        with self._session_factory() as session:
            stmt = select(MemoryRow)
            if account_key is not None:
                normalized_account_key = self._normalize_account_key(account_key)
                stmt = stmt.where(MemoryRow.account_key == normalized_account_key)
            if limit is not None:
                stmt = stmt.limit(limit)
            rows = session.scalars(stmt).all()
        return [self._row_to_memory(row) for row in rows]

    def fetch_by_ids(
        self,
        memory_ids: list[str],
        account_key: str | None = None,
    ) -> list[MemoryRecord]:
        if not memory_ids:
            return []
        with self._session_factory() as session:
            stmt = select(MemoryRow).where(MemoryRow.memory_id.in_(memory_ids))
            if account_key is not None:
                normalized_account_key = self._normalize_account_key(account_key)
                stmt = stmt.where(MemoryRow.account_key == normalized_account_key)
            rows = session.scalars(stmt).all()
        return [self._row_to_memory(row) for row in rows]

    def fetch_by_entity_and_intent(
        self,
        entity_id: str,
        intent: str,
        since_iso: str | None = None,
        account_key: str | None = None,
    ) -> list[MemoryRecord]:
        with self._session_factory() as session:
            stmt = select(MemoryRow).where(MemoryRow.intent == intent)
            if account_key is not None:
                normalized_account_key = self._normalize_account_key(account_key)
                stmt = stmt.where(MemoryRow.account_key == normalized_account_key)
            if since_iso is not None:
                since = datetime.fromisoformat(since_iso)
                stmt = stmt.where(MemoryRow.created_at >= since)
            rows = session.scalars(stmt).all()
        records = [self._row_to_memory(row) for row in rows]
        return [record for record in records if entity_id in record.entities]

    def search_candidates(
        self,
        query_embedding: NDArray[np.float32],
        top_k: int,
        account_key: str | None = None,
    ) -> list[MemoryRecord]:
        memories = self.list_memories(account_key=account_key)
        if not memories:
            return []
        scored: list[tuple[MemoryRecord, float]] = []
        for memory in memories:
            semantic_embedding = np.asarray(memory.semantic_embedding, dtype=np.float32)
            if semantic_embedding.shape != query_embedding.shape:
                continue
            score = cosine_similarity(query_embedding, semantic_embedding)
            scored.append((memory, score))
        if not scored:
            return []
        scored.sort(key=lambda item: item[1], reverse=True)
        return [memory for memory, _score in scored[:top_k]]

    def update_retrieval(self, memory_id: str, account_key: str | None = None) -> None:
        def _update(session: Session) -> None:
            stmt = update(MemoryRow).where(MemoryRow.memory_id == memory_id)
            if account_key is not None:
                normalized_account_key = self._normalize_account_key(account_key)
                stmt = stmt.where(MemoryRow.account_key == normalized_account_key)
            session.execute(
                stmt.values(
                    retrieval_count=MemoryRow.retrieval_count + 1,
                    updated_at=datetime.now(UTC),
                )
            )

        self._execute_write(_update)

    def update_outcome(
        self,
        memory_id: str,
        outcome_signal: float,
        account_key: str | None = None,
    ) -> None:
        def _update(session: Session) -> None:
            stmt = select(MemoryRow).where(MemoryRow.memory_id == memory_id)
            if account_key is not None:
                normalized_account_key = self._normalize_account_key(account_key)
                stmt = stmt.where(MemoryRow.account_key == normalized_account_key)
            row = session.execute(stmt).scalar_one_or_none()
            if row is None:
                return
            count = int(row.outcome_count)
            avg = float(row.avg_outcome_signal)
            new_count = count + 1
            new_avg = ((avg * count) + outcome_signal) / new_count
            row.avg_outcome_signal = new_avg
            row.outcome_count = new_count
            row.updated_at = datetime.now(UTC)

        self._execute_write(_update)

    def delete_memories(
        self,
        memory_ids: list[str],
        account_key: str | None = None,
    ) -> None:
        if not memory_ids:
            return

        def _delete(session: Session) -> None:
            stmt = delete(MemoryRow).where(MemoryRow.memory_id.in_(memory_ids))
            if account_key is not None:
                normalized_account_key = self._normalize_account_key(account_key)
                stmt = stmt.where(MemoryRow.account_key == normalized_account_key)
            session.execute(stmt)

        self._execute_write(_delete)

    def close(self) -> None:
        self._engine.dispose()

    def storage_usage_mb(self) -> float:
        if self._database_url.startswith("sqlite:///"):
            path = Path(self._database_url.removeprefix("sqlite:///"))
            if not path.exists():
                return 0.0
            return float(path.stat().st_size) / (1024.0 * 1024.0)

        if self._database_url.startswith("postgresql"):
            with self._engine.connect() as conn:
                result = conn.execute(
                    select(func.pg_database_size(func.current_database()))
                )
                value = result.scalar_one_or_none()
                if value is None:
                    return 0.0
                return float(value) / (1024.0 * 1024.0)
        return 0.0

    @staticmethod
    def _row_to_memory(row: MemoryRow) -> MemoryRecord:
        semantic_embedding = decode_vector(str(row.semantic_embedding_json))
        raw_embedding = decode_vector(str(row.raw_embedding_json))
        if not raw_embedding or len(raw_embedding) != len(semantic_embedding):
            raw_embedding = semantic_embedding.copy()
        return MemoryRecord(
            account_key=str(row.account_key),
            memory_id=str(row.memory_id),
            event_id=str(row.event_id),
            content=str(row.content),
            summary=str(row.summary),
            intent=str(row.intent),
            entities=[str(item) for item in json.loads(str(row.entities_json))],
            relationships=[
                str(item) for item in json.loads(str(row.relationships_json))
            ],
            raw_embedding=raw_embedding,
            semantic_embedding=semantic_embedding,
            semantic_key=str(row.semantic_key),
            created_at=_to_utc_datetime(row.created_at),
            updated_at=_to_utc_datetime(row.updated_at),
            retrieval_count=int(row.retrieval_count),
            avg_outcome_signal=float(row.avg_outcome_signal),
            storage_tier=StorageTier(str(row.storage_tier)),
            latest_importance=float(row.latest_importance),
            is_compressed=bool(row.is_compressed),
            original_count=int(row.original_count),
        )

    def _execute_write(self, operation: Callable[[Session], T]) -> T:
        for attempt in range(self._write_retry_attempts):
            with self._session_factory() as session:
                try:
                    result = operation(session)
                    session.commit()
                    return result
                except OperationalError as exc:
                    session.rollback()
                    if self._is_retryable_lock_error(exc) and (
                        attempt + 1 < self._write_retry_attempts
                    ):
                        time.sleep(0.01 * (2**attempt))
                        continue
                    raise
        msg = "write retry loop exited unexpectedly"
        raise RuntimeError(msg)

    def _truncate_content(self, content: str, intent: str) -> str:
        normalized_intent = intent.strip().lower()
        normalized_content = content
        if normalized_intent.startswith("assistant_"):
            normalized_content = self._compact_assistant_content(content)
        limit = (
            self._assistant_max_content_chars
            if normalized_intent.startswith("assistant_")
            else self._max_content_chars
        )
        if len(normalized_content) <= limit:
            return normalized_content
        if limit <= 64:
            return normalized_content[:limit]
        omitted = len(normalized_content) - limit
        return (
            normalized_content[: limit - 48].rstrip()
            + f"\n\n...[truncated {omitted} chars for storage efficiency]"
        )

    def _compact_assistant_content(self, content: str) -> str:
        normalized = " ".join(content.split())
        if not normalized:
            return normalized

        sentences = [
            item.strip()
            for item in re.split(r"(?<=[.!?])\s+", normalized)
            if item.strip()
        ]
        if len(sentences) <= 1:
            return normalized

        unique_sentences: list[str] = []
        seen: set[str] = set()
        duplicate_count = 0
        for sentence in sentences:
            key = sentence.lower()
            if key in seen:
                duplicate_count += 1
                continue
            seen.add(key)
            unique_sentences.append(sentence)

        if duplicate_count == 0:
            return normalized

        compacted = " ".join(unique_sentences)
        removed_chars = len(normalized) - len(compacted)
        if removed_chars < 80 and duplicate_count < 2:
            return normalized
        return (
            compacted
            + f" [assistant content compacted: removed {duplicate_count} repeated segments]"
        )

    @staticmethod
    def _dumps_compact(value: list[str] | list[float]) -> str:
        return json.dumps(value, ensure_ascii=True, separators=(",", ":"))

    @staticmethod
    def _dumps_vector(values: list[float]) -> str:
        return encode_vector(values)

    @staticmethod
    def _is_retryable_lock_error(exc: OperationalError) -> bool:
        text = str(exc).lower()
        return "database is locked" in text or "cannot start a transaction" in text

    def _ensure_account_key_column(self) -> None:
        inspector = inspect(self._engine)
        columns = {column["name"] for column in inspector.get_columns("memories")}
        if "account_key" in columns:
            return
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE memories "
                    "ADD COLUMN account_key VARCHAR(128) NOT NULL DEFAULT 'default'"
                )
            )
            conn.execute(
                text(
                    "UPDATE memories SET account_key = 'default' "
                    "WHERE account_key IS NULL OR account_key = ''"
                )
            )

    @staticmethod
    def _normalize_account_key(account_key: str) -> str:
        normalized = account_key.strip()
        return normalized or "default"


def _to_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
