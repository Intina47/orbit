"""Service layer implementing Orbit API business logic."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from time import perf_counter
from typing import Any, TypeVar

import numpy as np
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from decision_engine.models import MemoryRecord
from memory_engine.config import EngineConfig
from memory_engine.engine import DecisionEngine
from memory_engine.models.event import Event
from memory_engine.storage.db import ApiAccountUsageRow, ApiIdempotencyRow, Base
from orbit.models import (
    AccountQuota,
    AccountUsage,
    AuthValidationResponse,
    FeedbackRequest,
    FeedbackResponse,
    IngestRequest,
    IngestResponse,
    Memory,
    PaginatedMemoriesResponse,
    RetrieveRequest,
    RetrieveResponse,
    StatusResponse,
)
from orbit_api.auth import AuthContext
from orbit_api.config import ApiConfig


@dataclass
class RateLimitSnapshot:
    limit: int
    remaining: int
    reset_epoch: int

    def as_headers(self) -> dict[str, str]:
        return {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(self.remaining),
            "X-RateLimit-Reset": str(self.reset_epoch),
        }


class RateLimitExceededError(RuntimeError):
    """Raised when an API key exceeds quota."""

    def __init__(self, snapshot: RateLimitSnapshot, retry_after_seconds: int) -> None:
        super().__init__("Rate limit exceeded")
        self.snapshot = snapshot
        self.retry_after_seconds = retry_after_seconds


class IdempotencyConflictError(RuntimeError):
    """Raised when an idempotency key is reused with a different payload."""


ResponseT = TypeVar("ResponseT")


@dataclass
class _StoredReplay:
    response_payload: dict[str, Any]
    snapshot: RateLimitSnapshot
    status_code: int


class OrbitApiService:
    """Maps API contract objects to core memory engine operations."""

    def __init__(
        self,
        api_config: ApiConfig | None = None,
        engine: DecisionEngine | None = None,
        engine_config: EngineConfig | None = None,
    ) -> None:
        self._config = api_config or ApiConfig.from_env()
        resolved_engine_config = self._resolve_engine_config(engine_config)
        self._engine = engine or DecisionEngine(
            config=resolved_engine_config,
        )
        connect_args = (
            {"check_same_thread": False}
            if self._config.database_url.startswith("sqlite")
            else {}
        )
        self._state_engine = create_engine(
            self._config.database_url,
            future=True,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
        Base.metadata.create_all(self._state_engine)
        self._state_session_factory = sessionmaker(
            bind=self._state_engine,
            autoflush=False,
            autocommit=False,
            future=True,
        )
        self._state_lock = RLock()
        self._latest_ingestion: datetime | None = None
        self._started_at = datetime.now(UTC)
        self._metrics: dict[str, float] = {
            "ingest_requests_total": 0.0,
            "retrieve_requests_total": 0.0,
            "feedback_requests_total": 0.0,
            "ingest_latency_ms_sum": 0.0,
            "retrieve_latency_ms_sum": 0.0,
            "feedback_latency_ms_sum": 0.0,
        }

    @property
    def config(self) -> ApiConfig:
        return self._config

    def close(self) -> None:
        self._state_engine.dispose()
        self._engine.close()

    def consume_event_quota(
        self, account_key: str, amount: int = 1
    ) -> RateLimitSnapshot:
        return self._consume_quota(account_key, kind="event", amount=amount)

    def consume_query_quota(
        self, account_key: str, amount: int = 1
    ) -> RateLimitSnapshot:
        return self._consume_quota(account_key, kind="query", amount=amount)

    def ingest_with_quota(
        self,
        *,
        account_key: str,
        request: IngestRequest,
        idempotency_key: str | None,
    ) -> tuple[IngestResponse, RateLimitSnapshot, bool]:
        return self._execute_write_operation(
            account_key=account_key,
            operation="ingest",
            idempotency_key=idempotency_key,
            payload=request.model_dump(mode="json"),
            quota_kind="event",
            quota_amount=1,
            execute=lambda: self.ingest(request),
            serialize=lambda response: response.model_dump(mode="json"),
            deserialize=IngestResponse.model_validate,
            status_code=201,
        )

    def feedback_with_quota(
        self,
        *,
        account_key: str,
        request: FeedbackRequest,
        idempotency_key: str | None,
    ) -> tuple[FeedbackResponse, RateLimitSnapshot, bool]:
        return self._execute_write_operation(
            account_key=account_key,
            operation="feedback",
            idempotency_key=idempotency_key,
            payload=request.model_dump(mode="json"),
            quota_kind="event",
            quota_amount=1,
            execute=lambda: self.feedback(request),
            serialize=lambda response: response.model_dump(mode="json"),
            deserialize=FeedbackResponse.model_validate,
            status_code=200,
        )

    def ingest_batch_with_quota(
        self,
        *,
        account_key: str,
        events: list[IngestRequest],
        idempotency_key: str | None,
    ) -> tuple[list[IngestResponse], RateLimitSnapshot, bool]:
        payload = [item.model_dump(mode="json") for item in events]
        return self._execute_write_operation(
            account_key=account_key,
            operation="ingest_batch",
            idempotency_key=idempotency_key,
            payload=payload,
            quota_kind="event",
            quota_amount=len(events),
            execute=lambda: self.ingest_batch(events),
            serialize=lambda responses: {
                "items": [item.model_dump(mode="json") for item in responses]
            },
            deserialize=lambda data: [
                IngestResponse.model_validate(item) for item in data.get("items", [])
            ],
            status_code=200,
        )

    def feedback_batch_with_quota(
        self,
        *,
        account_key: str,
        feedback: list[FeedbackRequest],
        idempotency_key: str | None,
    ) -> tuple[list[FeedbackResponse], RateLimitSnapshot, bool]:
        payload = [item.model_dump(mode="json") for item in feedback]
        return self._execute_write_operation(
            account_key=account_key,
            operation="feedback_batch",
            idempotency_key=idempotency_key,
            payload=payload,
            quota_kind="event",
            quota_amount=len(feedback),
            execute=lambda: self.feedback_batch(feedback),
            serialize=lambda responses: {
                "items": [item.model_dump(mode="json") for item in responses]
            },
            deserialize=lambda data: [
                FeedbackResponse.model_validate(item)
                for item in data.get("items", [])
            ],
            status_code=200,
        )

    def ingest(self, request: IngestRequest) -> IngestResponse:
        start = perf_counter()
        event = Event(
            entity_id=request.entity_id or self._config.default_entity_id,
            event_type=request.event_type or self._config.default_event_type,
            description=request.content,
            metadata=request.metadata or {},
        )
        processed = self._engine.process_input(event)
        decision = self._engine.make_storage_decision(processed)
        stored = self._engine.store_memory(processed, decision)
        latency_ms = (perf_counter() - start) * 1000.0

        memory_id = (
            stored.memory_id
            if stored is not None
            else f"mem_{processed.event_id.replace('-', '')}"
        )
        decision_reason = (
            decision.rationale
            if decision.store
            else f"Discarded by policy: {decision.rationale}"
        )

        with self._state_lock:
            self._latest_ingestion = datetime.now(UTC)
            self._metrics["ingest_requests_total"] += 1
            self._metrics["ingest_latency_ms_sum"] += latency_ms

        return IngestResponse(
            memory_id=memory_id,
            stored=decision.store,
            importance_score=float(max(0.0, min(1.0, decision.confidence))),
            decision_reason=decision_reason,
            encoded_at=processed.timestamp,
            latency_ms=latency_ms,
        )

    def ingest_batch(self, events: list[IngestRequest]) -> list[IngestResponse]:
        return [self.ingest(item) for item in events]

    def retrieve(self, request: RetrieveRequest) -> RetrieveResponse:
        start = perf_counter()
        query_embedding = np.asarray(
            self._engine.input_processor.encoder.encode_query(request.query),
            dtype=np.float32,
        )
        now = datetime.now(UTC)
        pool_size = max(120, request.limit * 20)
        preselected: list[MemoryRecord]
        if request.entity_id:
            entity_ids_fn = getattr(self._engine, "memory_ids_for_entity", None)
            entity_ids = (
                entity_ids_fn(request.entity_id)
                if callable(entity_ids_fn)
                else []
            )
            preselected = self._engine.storage.fetch_by_ids(entity_ids)
            if not preselected:
                vector_store = getattr(self._engine, "vector_store", None)
                if vector_store is None:
                    preselected = self._engine.storage.search_candidates(
                        query_embedding, top_k=pool_size
                    )
                else:
                    hits = vector_store.search(query_embedding, top_k=pool_size)
                    preselected = self._engine.storage.fetch_by_ids(
                        [hit.memory_id for hit in hits]
                    )
        else:
            vector_store = getattr(self._engine, "vector_store", None)
            if vector_store is not None:
                hits = vector_store.search(query_embedding, top_k=pool_size)
                preselected = self._engine.storage.fetch_by_ids(
                    [hit.memory_id for hit in hits]
                )
            else:
                preselected = self._engine.storage.search_candidates(
                    query_embedding, top_k=pool_size
                )
        candidates = self._apply_filters(
            records=preselected,
            entity_id=request.entity_id,
            event_type=request.event_type,
            start_time=request.time_range.start if request.time_range else None,
            end_time=request.time_range.end if request.time_range else None,
        )
        candidates = self._ensure_non_assistant_candidates(
            candidates=candidates,
            top_k=request.limit,
            pool_size=pool_size,
            entity_id=request.entity_id,
            event_type=request.event_type,
            start_time=request.time_range.start if request.time_range else None,
            end_time=request.time_range.end if request.time_range else None,
        )
        ranked = self._engine.ranker.rank(query_embedding, candidates, now=now)
        selected = self._select_with_intent_caps(ranked, top_k=request.limit)
        memories: list[Memory] = []
        for index, ranked_item in enumerate(selected, start=1):
            self._engine.storage.update_retrieval(ranked_item.memory.memory_id)
            memories.append(
                self._as_memory(
                    ranked_item.memory,
                    rank_position=index,
                    rank_score=float(ranked_item.rank_score),
                )
            )

        query_execution_time_ms = (perf_counter() - start) * 1000.0
        with self._state_lock:
            self._metrics["retrieve_requests_total"] += 1
            self._metrics["retrieve_latency_ms_sum"] += query_execution_time_ms

        applied_filters: dict[str, str] = {}
        if request.entity_id:
            applied_filters["entity_id"] = request.entity_id
        if request.event_type:
            applied_filters["event_type"] = request.event_type
        if request.time_range:
            applied_filters["start_time"] = request.time_range.start.isoformat()
            applied_filters["end_time"] = request.time_range.end.isoformat()

        return RetrieveResponse(
            memories=memories,
            total_candidates=len(candidates),
            query_execution_time_ms=query_execution_time_ms,
            applied_filters=applied_filters,
        )

    def feedback(self, request: FeedbackRequest) -> FeedbackResponse:
        start = perf_counter()
        existing = self._engine.storage.fetch_by_ids([request.memory_id])
        if not existing:
            msg = f"memory_id {request.memory_id} was not found"
            raise KeyError(msg)

        outcome_signal = (
            request.outcome_value
            if request.outcome_value is not None
            else (1.0 if request.helpful else -1.0)
        )
        helpful_ids = [request.memory_id] if request.helpful else []
        self._engine.record_feedback(
            query=f"memory:{request.memory_id}",
            ranked_memory_ids=[request.memory_id],
            helpful_memory_ids=helpful_ids,
            outcome_signal=outcome_signal,
        )

        latency_ms = (perf_counter() - start) * 1000.0
        with self._state_lock:
            self._metrics["feedback_requests_total"] += 1
            self._metrics["feedback_latency_ms_sum"] += latency_ms

        impact = (
            "Positive signal recorded. This will improve ranking for similar queries."
            if request.helpful
            else "Negative signal recorded. This helps suppress low-value memories."
        )
        return FeedbackResponse(
            recorded=True,
            memory_id=request.memory_id,
            learning_impact=impact,
            updated_at=datetime.now(UTC),
        )

    def feedback_batch(self, feedback: list[FeedbackRequest]) -> list[FeedbackResponse]:
        return [self.feedback(item) for item in feedback]

    def status(self, account_key: str) -> StatusResponse:
        now = datetime.now(UTC)
        with self._state_lock:
            latest_ingestion = self._latest_ingestion
        usage = self._read_usage_row(account_key)
        storage_mb = self._storage_usage_mb()
        events_month = (
            usage.events_month
            if usage
            and usage.month_year == now.year
            and usage.month_value == now.month
            else 0
        )
        queries_month = (
            usage.queries_month
            if usage
            and usage.month_year == now.year
            and usage.month_value == now.month
            else 0
        )
        return StatusResponse(
            connected=True,
            api_version=self._config.api_version,
            account_usage=AccountUsage(
                events_ingested_this_month=events_month,
                queries_this_month=queries_month,
                storage_usage_mb=storage_mb,
                quota=AccountQuota(
                    events_per_day=self._config.free_events_per_day,
                    queries_per_day=self._config.free_queries_per_day,
                ),
            ),
            latest_ingestion=latest_ingestion,
            uptime_percent=self._config.uptime_percent,
        )

    def health(self) -> dict[str, str]:
        try:
            self._engine.memory_count()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            return {
                "status": "degraded",
                "version": self._config.api_version,
                "storage": "error",
                "detail": str(exc),
            }
        return {
            "status": "ok",
            "version": self._config.api_version,
            "storage": "ok",
        }

    def validate_token(self, auth: AuthContext) -> AuthValidationResponse:
        return AuthValidationResponse(valid=True, scopes=auth.scopes)

    def metrics_text(self) -> str:
        with self._state_lock:
            ingest_total = self._metrics["ingest_requests_total"]
            retrieve_total = self._metrics["retrieve_requests_total"]
            feedback_total = self._metrics["feedback_requests_total"]
        lines = [
            "# HELP orbit_ingest_requests_total Total ingest requests.",
            "# TYPE orbit_ingest_requests_total counter",
            f"orbit_ingest_requests_total {ingest_total:.0f}",
            "# HELP orbit_retrieve_requests_total Total retrieve requests.",
            "# TYPE orbit_retrieve_requests_total counter",
            f"orbit_retrieve_requests_total {retrieve_total:.0f}",
            "# HELP orbit_feedback_requests_total Total feedback requests.",
            "# TYPE orbit_feedback_requests_total counter",
            f"orbit_feedback_requests_total {feedback_total:.0f}",
            "# HELP orbit_uptime_seconds Process uptime in seconds.",
            "# TYPE orbit_uptime_seconds gauge",
            f"orbit_uptime_seconds {self._uptime_seconds():.3f}",
        ]
        return "\n".join(lines) + "\n"

    def list_memories(
        self, limit: int, cursor: str | None
    ) -> PaginatedMemoriesResponse:
        offset = 0
        if cursor:
            try:
                offset = max(0, int(cursor))
            except ValueError:
                offset = 0

        records = sorted(
            self._engine.storage.list_memories(),
            key=lambda item: item.created_at,
            reverse=True,
        )
        selected = records[offset : offset + limit]
        data = [
            self._as_memory(
                record,
                rank_position=offset + idx + 1,
                rank_score=float(record.latest_importance),
            )
            for idx, record in enumerate(selected)
        ]
        next_offset = offset + limit
        has_more = next_offset < len(records)
        return PaginatedMemoriesResponse(
            data=data,
            cursor=str(next_offset) if has_more else None,
            has_more=has_more,
        )

    def _as_memory(
        self,
        record: MemoryRecord,
        rank_position: int,
        rank_score: float,
    ) -> Memory:
        return Memory(
            memory_id=record.memory_id,
            content=record.content,
            rank_position=rank_position,
            rank_score=float(max(0.0, min(1.0, rank_score))),
            importance_score=float(max(0.0, min(1.0, record.latest_importance))),
            timestamp=record.created_at,
            metadata={
                "summary": record.summary,
                "intent": record.intent,
                "entities": record.entities,
                "relationships": record.relationships,
                "storage_tier": record.storage_tier.value,
            },
            relevance_explanation=(
                "Ranked by semantic similarity + learned relevance model."
            ),
        )

    def _filter_candidates(
        self,
        entity_id: str | None,
        event_type: str | None,
        start_time: datetime | None,
        end_time: datetime | None,
    ) -> list[MemoryRecord]:
        records = self._engine.storage.list_memories()
        return self._apply_filters(records, entity_id, event_type, start_time, end_time)

    def _apply_filters(
        self,
        records: list[MemoryRecord],
        entity_id: str | None,
        event_type: str | None,
        start_time: datetime | None,
        end_time: datetime | None,
    ) -> list[MemoryRecord]:
        output: list[MemoryRecord] = []
        for record in records:
            if entity_id and entity_id not in record.entities:
                continue
            if event_type and record.intent != event_type:
                continue
            if start_time and record.created_at < start_time:
                continue
            if end_time and record.created_at > end_time:
                continue
            output.append(record)
        return output

    def _select_with_intent_caps(
        self,
        ranked: list[Any],
        top_k: int,
    ) -> list[Any]:
        if top_k <= 0:
            return []
        max_share = float(
            getattr(self._engine.config, "assistant_response_max_share", 0.25)
        )
        max_share = min(max(max_share, 0.0), 1.0)
        assistant_cap = self._assistant_cap(top_k, max_share=max_share)
        selected: list[Any] = []
        assistant_count = 0
        deferred: list[Any] = []
        for item in ranked:
            is_assistant = self._is_assistant_intent(item.memory.intent)
            if is_assistant and assistant_count >= assistant_cap:
                deferred.append(item)
                continue
            selected.append(item)
            if is_assistant:
                assistant_count += 1
            if len(selected) >= top_k:
                return selected
        for item in deferred:
            if len(selected) >= top_k:
                break
            selected.append(item)
        return selected

    def _ensure_non_assistant_candidates(
        self,
        candidates: list[MemoryRecord],
        *,
        top_k: int,
        pool_size: int,
        entity_id: str | None,
        event_type: str | None,
        start_time: datetime | None,
        end_time: datetime | None,
    ) -> list[MemoryRecord]:
        if top_k <= 0:
            return candidates
        max_share = float(
            getattr(self._engine.config, "assistant_response_max_share", 0.25)
        )
        max_share = min(max(max_share, 0.0), 1.0)
        required_non_assistant = max(top_k - self._assistant_cap(top_k, max_share), 0)
        current_non_assistant = sum(
            1 for item in candidates if not self._is_assistant_intent(item.intent)
        )
        if current_non_assistant >= required_non_assistant:
            return candidates

        fallback_pool = self._apply_filters(
            records=self._engine.storage.list_memories(limit=max(pool_size, top_k * 8)),
            entity_id=entity_id,
            event_type=event_type,
            start_time=start_time,
            end_time=end_time,
        )
        seen_ids = {item.memory_id for item in candidates}
        enriched = list(candidates)
        for memory in fallback_pool:
            if memory.memory_id in seen_ids:
                continue
            if self._is_assistant_intent(memory.intent):
                continue
            enriched.append(memory)
            seen_ids.add(memory.memory_id)
            current_non_assistant += 1
            if current_non_assistant >= required_non_assistant:
                break
        return enriched

    @staticmethod
    def _assistant_cap(top_k: int, max_share: float) -> int:
        return min(top_k, max(0, int(top_k * max_share)))

    @staticmethod
    def _is_assistant_intent(intent: str) -> bool:
        return intent.strip().lower().startswith("assistant_")

    def _consume_quota(
        self, account_key: str, kind: str, amount: int
    ) -> RateLimitSnapshot:
        with self._state_session_factory() as session, session.begin():
            return self._consume_quota_with_session(
                session=session,
                account_key=account_key,
                kind=kind,
                amount=amount,
                now=datetime.now(UTC),
            )

    def _consume_quota_with_session(
        self,
        *,
        session: Session,
        account_key: str,
        kind: str,
        amount: int,
        now: datetime,
    ) -> RateLimitSnapshot:
        if amount <= 0:
            msg = "amount must be > 0"
            raise ValueError(msg)
        usage = self._select_usage_row_for_update(session=session, account_key=account_key)
        if usage is None:
            usage = ApiAccountUsageRow(
                account_key=account_key,
                day_bucket=now.date(),
                month_year=now.year,
                month_value=now.month,
                events_today=0,
                queries_today=0,
                events_month=0,
                queries_month=0,
                updated_at=now,
            )
            session.add(usage)
        self._roll_usage_window(usage=usage, now=now)

        if kind == "event":
            limit = self._config.free_events_per_day
            used = usage.events_today
        else:
            limit = self._config.free_queries_per_day
            used = usage.queries_today

        if used + amount > limit:
            snapshot = RateLimitSnapshot(
                limit=limit,
                remaining=max(limit - used, 0),
                reset_epoch=self._next_day_reset_epoch(now),
            )
            retry_after = max(snapshot.reset_epoch - int(now.timestamp()), 1)
            raise RateLimitExceededError(
                snapshot=snapshot,
                retry_after_seconds=retry_after,
            )

        if kind == "event":
            usage.events_today += amount
            usage.events_month += amount
            remaining = max(limit - usage.events_today, 0)
        else:
            usage.queries_today += amount
            usage.queries_month += amount
            remaining = max(limit - usage.queries_today, 0)
        usage.updated_at = now

        return RateLimitSnapshot(
            limit=limit,
            remaining=remaining,
            reset_epoch=self._next_day_reset_epoch(now),
        )

    @staticmethod
    def _roll_usage_window(usage: ApiAccountUsageRow, now: datetime) -> None:
        if usage.day_bucket != now.date():
            usage.day_bucket = now.date()
            usage.events_today = 0
            usage.queries_today = 0
        if usage.month_year != now.year or usage.month_value != now.month:
            usage.month_year = now.year
            usage.month_value = now.month
            usage.events_month = 0
            usage.queries_month = 0

    @staticmethod
    def _next_day_reset_epoch(now: datetime) -> int:
        next_day = datetime(
            year=now.year,
            month=now.month,
            day=now.day,
            tzinfo=UTC,
        )
        next_day = next_day.replace(hour=0, minute=0, second=0, microsecond=0)
        return int(next_day.timestamp()) + 86400

    def _read_usage_row(self, account_key: str) -> ApiAccountUsageRow | None:
        with self._state_session_factory() as session:
            stmt = select(ApiAccountUsageRow).where(
                ApiAccountUsageRow.account_key == account_key
            )
            return session.execute(stmt).scalar_one_or_none()

    def _select_usage_row_for_update(
        self,
        *,
        session: Session,
        account_key: str,
    ) -> ApiAccountUsageRow | None:
        stmt = (
            select(ApiAccountUsageRow)
            .where(ApiAccountUsageRow.account_key == account_key)
            .with_for_update()
        )
        return session.execute(stmt).scalar_one_or_none()

    def _execute_write_operation(
        self,
        *,
        account_key: str,
        operation: str,
        idempotency_key: str | None,
        payload: Any,
        quota_kind: str,
        quota_amount: int,
        execute: Callable[[], ResponseT],
        serialize: Callable[[ResponseT], dict[str, Any]],
        deserialize: Callable[[dict[str, Any]], ResponseT],
        status_code: int,
    ) -> tuple[ResponseT, RateLimitSnapshot, bool]:
        if idempotency_key is None:
            snapshot = self._consume_quota(
                account_key=account_key,
                kind=quota_kind,
                amount=quota_amount,
            )
            return execute(), snapshot, False

        normalized_key = self._normalize_idempotency_key(idempotency_key)
        request_hash = self._payload_hash(payload)
        snapshot, replay = self._reserve_idempotency_slot(
            account_key=account_key,
            operation=operation,
            idempotency_key=normalized_key,
            request_hash=request_hash,
            quota_kind=quota_kind,
            quota_amount=quota_amount,
        )
        if replay is not None:
            return deserialize(replay.response_payload), replay.snapshot, True

        try:
            result = execute()
        except Exception:
            self._release_pending_idempotency(
                account_key=account_key,
                operation=operation,
                idempotency_key=normalized_key,
                request_hash=request_hash,
            )
            raise

        self._persist_idempotent_response(
            account_key=account_key,
            operation=operation,
            idempotency_key=normalized_key,
            request_hash=request_hash,
            response_payload=serialize(result),
            status_code=status_code,
            snapshot=snapshot,
        )
        return result, snapshot, False

    def _reserve_idempotency_slot(
        self,
        *,
        account_key: str,
        operation: str,
        idempotency_key: str,
        request_hash: str,
        quota_kind: str,
        quota_amount: int,
    ) -> tuple[RateLimitSnapshot, _StoredReplay | None]:
        for _ in range(3):
            try:
                with self._state_session_factory() as session, session.begin():
                    replay = self._lookup_existing_replay(
                        session=session,
                        account_key=account_key,
                        operation=operation,
                        idempotency_key=idempotency_key,
                        request_hash=request_hash,
                    )
                    if replay is not None:
                        return replay.snapshot, replay
                    now = datetime.now(UTC)
                    session.add(
                        ApiIdempotencyRow(
                            account_key=account_key,
                            operation=operation,
                            idempotency_key=idempotency_key,
                            request_hash=request_hash,
                            response_json=None,
                            status_code=None,
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    session.flush()
                    snapshot = self._consume_quota_with_session(
                        session=session,
                        account_key=account_key,
                        kind=quota_kind,
                        amount=quota_amount,
                        now=now,
                    )
                    return snapshot, None
            except IntegrityError:
                continue
        msg = "Unable to reserve idempotency key due to concurrent writes"
        raise RuntimeError(msg)

    def _lookup_existing_replay(
        self,
        *,
        session: Session,
        account_key: str,
        operation: str,
        idempotency_key: str,
        request_hash: str,
    ) -> _StoredReplay | None:
        row = self._select_idempotency_row_for_update(
            session=session,
            account_key=account_key,
            operation=operation,
            idempotency_key=idempotency_key,
        )
        if row is None:
            return None
        if row.request_hash != request_hash:
            msg = "Idempotency key reused with a different payload"
            raise IdempotencyConflictError(msg)
        if row.response_json is None or row.status_code is None:
            msg = "Request with this idempotency key is still in progress"
            raise IdempotencyConflictError(msg)
        return self._deserialize_replay_payload(
            response_json=row.response_json,
            status_code=row.status_code,
        )

    def _persist_idempotent_response(
        self,
        *,
        account_key: str,
        operation: str,
        idempotency_key: str,
        request_hash: str,
        response_payload: dict[str, Any],
        status_code: int,
        snapshot: RateLimitSnapshot,
    ) -> None:
        with self._state_session_factory() as session, session.begin():
            row = self._select_idempotency_row_for_update(
                session=session,
                account_key=account_key,
                operation=operation,
                idempotency_key=idempotency_key,
            )
            if row is None:
                return
            if row.request_hash != request_hash:
                msg = "Idempotency key reused with a different payload"
                raise IdempotencyConflictError(msg)
            if row.response_json is not None:
                return
            row.response_json = self._serialize_replay_payload(
                response_payload=response_payload,
                snapshot=snapshot,
            )
            row.status_code = status_code
            row.updated_at = datetime.now(UTC)

    def _release_pending_idempotency(
        self,
        *,
        account_key: str,
        operation: str,
        idempotency_key: str,
        request_hash: str,
    ) -> None:
        with self._state_session_factory() as session, session.begin():
            row = self._select_idempotency_row_for_update(
                session=session,
                account_key=account_key,
                operation=operation,
                idempotency_key=idempotency_key,
            )
            if row is None:
                return
            if row.request_hash != request_hash:
                return
            if row.response_json is not None:
                return
            session.delete(row)

    def _select_idempotency_row_for_update(
        self,
        *,
        session: Session,
        account_key: str,
        operation: str,
        idempotency_key: str,
    ) -> ApiIdempotencyRow | None:
        stmt = (
            select(ApiIdempotencyRow)
            .where(ApiIdempotencyRow.account_key == account_key)
            .where(ApiIdempotencyRow.operation == operation)
            .where(ApiIdempotencyRow.idempotency_key == idempotency_key)
            .with_for_update()
        )
        return session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def _serialize_replay_payload(
        *,
        response_payload: dict[str, Any],
        snapshot: RateLimitSnapshot,
    ) -> str:
        payload = {
            "response": response_payload,
            "rate_limit": {
                "limit": snapshot.limit,
                "remaining": snapshot.remaining,
                "reset_epoch": snapshot.reset_epoch,
            },
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    @staticmethod
    def _deserialize_replay_payload(
        *,
        response_json: str,
        status_code: int,
    ) -> _StoredReplay:
        parsed = json.loads(response_json)
        if not isinstance(parsed, dict):
            msg = "Stored idempotency payload is malformed"
            raise RuntimeError(msg)
        response = parsed.get("response")
        if not isinstance(response, dict):
            msg = "Stored idempotency response is malformed"
            raise RuntimeError(msg)
        raw_snapshot = parsed.get("rate_limit")
        if not isinstance(raw_snapshot, dict):
            snapshot = RateLimitSnapshot(limit=0, remaining=0, reset_epoch=0)
        else:
            snapshot = RateLimitSnapshot(
                limit=max(int(raw_snapshot.get("limit", 0)), 0),
                remaining=max(int(raw_snapshot.get("remaining", 0)), 0),
                reset_epoch=max(int(raw_snapshot.get("reset_epoch", 0)), 0),
            )
        return _StoredReplay(
            response_payload=response,
            snapshot=snapshot,
            status_code=status_code,
        )

    @staticmethod
    def _normalize_idempotency_key(value: str) -> str:
        normalized = value.strip()
        if not normalized:
            msg = "Idempotency-Key header cannot be empty"
            raise ValueError(msg)
        if len(normalized) > 128:
            msg = "Idempotency-Key header cannot exceed 128 characters"
            raise ValueError(msg)
        return normalized

    @staticmethod
    def _payload_hash(payload: Any) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        digest = hashlib.sha256(canonical.encode("utf-8"))
        return digest.hexdigest()

    def _storage_usage_mb(self) -> float:
        storage = self._engine.storage
        size_method = getattr(storage, "storage_usage_mb", None)
        if callable(size_method):
            size_value = size_method()
            return float(size_value)
        if self._config.database_url.startswith("sqlite:///"):
            path = Path(self._config.database_url.removeprefix("sqlite:///"))
            if not path.exists():
                return 0.0
            return float(path.stat().st_size) / (1024.0 * 1024.0)
        return 0.0

    def _uptime_seconds(self) -> float:
        return (datetime.now(UTC) - self._started_at).total_seconds()

    def _resolve_engine_config(
        self,
        provided: EngineConfig | None,
    ) -> EngineConfig:
        base = provided or EngineConfig.from_env()
        updates: dict[str, Any] = {}
        if base.database_url is None:
            updates["database_url"] = self._config.database_url
        if not base.sqlite_path:
            updates["sqlite_path"] = self._config.sqlite_fallback_path
        if not updates:
            return base
        return base.model_copy(update=updates)
