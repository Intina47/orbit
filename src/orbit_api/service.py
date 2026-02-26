"""Service layer implementing Orbit API business logic."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from time import perf_counter
from typing import Any, TypeVar
from uuid import uuid4

import httpx
import numpy as np
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from decision_engine.models import MemoryRecord, RetrievedMemory
from memory_engine.config import EngineConfig
from memory_engine.engine import DecisionEngine
from memory_engine.models.event import Event
from memory_engine.storage.db import (
    ApiAccountUsageRow,
    ApiAuditLogRow,
    ApiDashboardUserRow,
    ApiIdempotencyRow,
    ApiKeyRow,
    ApiPilotProRequestRow,
    Base,
)
from orbit.models import (
    AccountQuota,
    AccountUsage,
    ApiKeyIssueResponse,
    ApiKeyListResponse,
    ApiKeyRevokeResponse,
    ApiKeyRotateResponse,
    ApiKeySummary,
    AuthValidationResponse,
    FeedbackRequest,
    FeedbackResponse,
    IngestRequest,
    IngestResponse,
    Memory,
    MetadataSummary,
    PaginatedMemoriesResponse,
    PilotProRequest,
    PilotProRequestResponse,
    RetrieveRequest,
    RetrieveResponse,
    StatusResponse,
    TenantMetricsResponse,
    TenantUsageMetric,
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


@dataclass(frozen=True)
class PlanQuotaPolicy:
    plan: str
    ingest_events_per_month: int
    retrieve_queries_per_month: int
    api_keys_limit: int
    retention_days: int
    warning_threshold_percent: int
    critical_threshold_percent: int


class RateLimitExceededError(RuntimeError):
    """Raised when an API key exceeds quota."""

    def __init__(
        self,
        snapshot: RateLimitSnapshot,
        retry_after_seconds: int,
        *,
        error_code: str,
        detail: str,
    ) -> None:
        super().__init__(detail)
        self.snapshot = snapshot
        self.retry_after_seconds = retry_after_seconds
        self.error_code = error_code
        self.detail = detail


class PlanQuotaExceededError(RuntimeError):
    """Raised when a plan-level non-request quota is exceeded."""

    def __init__(self, *, error_code: str, detail: str) -> None:
        super().__init__(detail)
        self.error_code = error_code
        self.detail = detail


class IdempotencyConflictError(RuntimeError):
    """Raised when an idempotency key is reused with a different payload."""


class ApiKeyAuthenticationError(RuntimeError):
    """Raised when an API key cannot be authenticated."""


class AccountMappingError(RuntimeError):
    """Raised when dashboard account mapping cannot be resolved safely."""


ResponseT = TypeVar("ResponseT")

_API_KEY_PREFIX = "orbit_pk_"
_API_KEY_PATTERN = re.compile(r"^orbit_pk_([a-z0-9]{12})_([A-Za-z0-9_-]{16,})$")
_API_KEY_HASH_ALGORITHM = "sha256"
_API_KEY_HASH_ITERATIONS = 310_000
_DEFAULT_KEY_SCOPES = ["read", "write", "feedback"]


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
            "dashboard_auth_failures_total": 0.0,
            "dashboard_key_rotation_failures_total": 0.0,
        }
        self._http_status_counts: dict[int, float] = {}
        self._pilot_pro_accounts = {
            self._normalize_account_key(account_key)
            for account_key in self._config.pilot_pro_account_keys
        }

    @property
    def config(self) -> ApiConfig:
        return self._config

    def close(self) -> None:
        self._state_engine.dispose()
        self._engine.close()

    def resolve_account_context(self, auth: AuthContext) -> AuthContext:
        claims = dict(auth.claims)
        if str(claims.get("auth_type", "")).strip().lower() == "api_key":
            return auth
        issuer = self._normalize_auth_issuer(claims.get("iss"))
        subject = self._normalize_auth_subject(auth.subject)
        account_key = self._account_key_from_claims(claims)
        email = self._email_from_claims(claims)
        display_name = self._display_name_from_claims(claims)
        auth_provider = self._auth_provider_from_claims(claims)
        avatar_url = self._avatar_url_from_claims(claims)

        if account_key is None:
            mapped = self._lookup_dashboard_account_mapping(
                auth_issuer=issuer,
                auth_subject=subject,
            )
            if mapped is not None:
                account_key = mapped
            elif self._config.dashboard_auto_provision_accounts:
                account_key = self._provision_dashboard_account_key(
                    issuer=issuer,
                    subject=subject,
                )
            else:
                account_key = self._normalize_account_key(subject)
        self._upsert_dashboard_account_mapping(
            account_key=account_key,
            auth_issuer=issuer,
            auth_subject=subject,
            email=email,
            auth_provider=auth_provider,
            display_name=display_name,
            avatar_url=avatar_url,
            last_login_at=datetime.now(UTC),
        )
        claims["account_key"] = account_key
        claims["auth_subject"] = subject
        claims["auth_issuer"] = issuer
        if auth_provider:
            claims["auth_provider"] = auth_provider
        return AuthContext(
            subject=account_key,
            scopes=auth.scopes,
            token=auth.token,
            claims=claims,
        )

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
            execute=lambda: self.ingest(request, account_key=account_key),
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
            execute=lambda: self.feedback(request, account_key=account_key),
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
            execute=lambda: self.ingest_batch(events, account_key=account_key),
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
            execute=lambda: self.feedback_batch(feedback, account_key=account_key),
            serialize=lambda responses: {
                "items": [item.model_dump(mode="json") for item in responses]
            },
            deserialize=lambda data: [
                FeedbackResponse.model_validate(item)
                for item in data.get("items", [])
            ],
            status_code=200,
        )

    def issue_api_key(
        self,
        *,
        account_key: str,
        name: str,
        scopes: list[str] | None = None,
        actor_subject: str | None = None,
        actor_type: str = "dashboard_user",
    ) -> ApiKeyIssueResponse:
        normalized_account_key = self._normalize_account_key(account_key)
        normalized_name = self._normalize_api_key_name(name)
        normalized_scopes = self._normalize_scopes(scopes)
        policy = self._plan_policy(normalized_account_key)
        scopes_json = json.dumps(
            normalized_scopes,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )

        for _ in range(5):
            now = datetime.now(UTC)
            key_id = str(uuid4())
            key_prefix, key_secret, plaintext_key = self._generate_api_key_material()
            salt = secrets.token_bytes(16)
            secret_hash = self._hash_api_key_secret(
                secret=key_secret,
                salt=salt,
                iterations=_API_KEY_HASH_ITERATIONS,
            )

            try:
                with self._state_session_factory() as session, session.begin():
                    active_key_count = self._active_api_key_count_with_session(
                        session=session,
                        account_key=normalized_account_key,
                    )
                    if active_key_count >= policy.api_keys_limit:
                        raise PlanQuotaExceededError(
                            error_code="quota_api_keys_exceeded",
                            detail=(
                                f"API key limit reached for plan '{policy.plan}' "
                                f"({policy.api_keys_limit} max active keys)."
                            ),
                        )
                    session.add(
                        ApiKeyRow(
                            key_id=key_id,
                            account_key=normalized_account_key,
                            name=normalized_name,
                            key_prefix=key_prefix,
                            secret_salt=salt.hex(),
                            secret_hash=secret_hash,
                            hash_iterations=_API_KEY_HASH_ITERATIONS,
                            scopes_json=scopes_json,
                            status="active",
                            created_at=now,
                            last_used_at=None,
                            last_used_source=None,
                            revoked_at=None,
                        )
                    )
                    self._insert_audit_row(
                        session=session,
                        account_key=normalized_account_key,
                        actor_subject=actor_subject or normalized_account_key,
                        actor_type=actor_type,
                        action="api_key_issued",
                        target_type="api_key",
                        target_id=key_id,
                        metadata={
                            "key_prefix": key_prefix,
                            "name": normalized_name,
                            "scopes": normalized_scopes,
                        },
                    )
                    session.flush()
            except IntegrityError:
                continue

            return ApiKeyIssueResponse(
                key_id=key_id,
                name=normalized_name,
                key_prefix=key_prefix,
                scopes=normalized_scopes,
                status="active",
                created_at=now,
                last_used_at=None,
                last_used_source=None,
                revoked_at=None,
                key=plaintext_key,
            )

        msg = "Failed to issue API key. Please retry."
        raise RuntimeError(msg)

    def list_api_keys(
        self,
        *,
        account_key: str,
        limit: int = 50,
        cursor: str | None = None,
    ) -> ApiKeyListResponse:
        normalized_account_key = self._normalize_account_key(account_key)
        normalized_limit = self._normalize_list_limit(limit)
        offset = self._cursor_to_offset(cursor)
        with self._state_session_factory() as session:
            stmt = (
                select(ApiKeyRow)
                .where(ApiKeyRow.account_key == normalized_account_key)
                .order_by(ApiKeyRow.created_at.desc())
                .offset(offset)
                .limit(normalized_limit + 1)
            )
            rows = list(session.execute(stmt).scalars())
        has_more = len(rows) > normalized_limit
        selected = rows[:normalized_limit]
        next_cursor = str(offset + normalized_limit) if has_more else None
        return ApiKeyListResponse(
            data=[self._as_api_key_summary(row) for row in selected],
            cursor=next_cursor,
            has_more=has_more,
        )

    def revoke_api_key(
        self,
        *,
        account_key: str,
        key_id: str,
        actor_subject: str | None = None,
        actor_type: str = "dashboard_user",
    ) -> ApiKeyRevokeResponse:
        normalized_account_key = self._normalize_account_key(account_key)
        normalized_key_id = self._normalize_key_id(key_id)
        revoked_at: datetime | None = None
        with self._state_session_factory() as session, session.begin():
            stmt = (
                select(ApiKeyRow)
                .where(ApiKeyRow.account_key == normalized_account_key)
                .where(ApiKeyRow.key_id == normalized_key_id)
                .with_for_update()
            )
            row = session.execute(stmt).scalar_one_or_none()
            if row is None:
                msg = f"API key not found: {normalized_key_id}"
                raise KeyError(msg)
            if row.status != "revoked":
                row.status = "revoked"
                row.revoked_at = datetime.now(UTC)
            revoked_at = row.revoked_at
            self._insert_audit_row(
                session=session,
                account_key=normalized_account_key,
                actor_subject=actor_subject or normalized_account_key,
                actor_type=actor_type,
                action="api_key_revoked",
                target_type="api_key",
                target_id=normalized_key_id,
                metadata={"revoked_at": revoked_at.isoformat() if revoked_at else None},
            )
        return ApiKeyRevokeResponse(
            key_id=normalized_key_id,
            revoked=True,
            revoked_at=revoked_at,
        )

    def rotate_api_key(
        self,
        *,
        account_key: str,
        key_id: str,
        name: str | None = None,
        scopes: list[str] | None = None,
        actor_subject: str | None = None,
        actor_type: str = "dashboard_user",
    ) -> ApiKeyRotateResponse:
        normalized_account_key = self._normalize_account_key(account_key)
        normalized_key_id = self._normalize_key_id(key_id)
        new_name = self._normalize_api_key_name(name) if name is not None else None
        requested_scopes = self._normalize_scopes(scopes) if scopes is not None else None

        for _ in range(5):
            now = datetime.now(UTC)
            new_key_id = str(uuid4())
            key_prefix, key_secret, plaintext_key = self._generate_api_key_material()
            salt = secrets.token_bytes(16)
            secret_hash = self._hash_api_key_secret(
                secret=key_secret,
                salt=salt,
                iterations=_API_KEY_HASH_ITERATIONS,
            )
            resolved_name = ""
            resolved_scopes: list[str] = []
            try:
                with self._state_session_factory() as session, session.begin():
                    existing = self._select_api_key_for_update(
                        session=session,
                        account_key=normalized_account_key,
                        key_id=normalized_key_id,
                    )
                    if existing is None:
                        msg = f"API key not found: {normalized_key_id}"
                        raise KeyError(msg)
                    if existing.status == "revoked":
                        msg = f"API key already revoked: {normalized_key_id}"
                        raise ValueError(msg)

                    resolved_name = new_name or existing.name
                    resolved_scopes = (
                        requested_scopes
                        if requested_scopes is not None
                        else self._deserialize_scopes(existing.scopes_json)
                    )
                    if not resolved_scopes:
                        resolved_scopes = list(_DEFAULT_KEY_SCOPES)
                    scopes_json = json.dumps(
                        resolved_scopes,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=True,
                    )
                    session.add(
                        ApiKeyRow(
                            key_id=new_key_id,
                            account_key=normalized_account_key,
                            name=resolved_name,
                            key_prefix=key_prefix,
                            secret_salt=salt.hex(),
                            secret_hash=secret_hash,
                            hash_iterations=_API_KEY_HASH_ITERATIONS,
                            scopes_json=scopes_json,
                            status="active",
                            created_at=now,
                            last_used_at=None,
                            last_used_source=None,
                            revoked_at=None,
                        )
                    )
                    existing.status = "revoked"
                    existing.revoked_at = now

                    self._insert_audit_row(
                        session=session,
                        account_key=normalized_account_key,
                        actor_subject=actor_subject or normalized_account_key,
                        actor_type=actor_type,
                        action="api_key_rotated",
                        target_type="api_key",
                        target_id=normalized_key_id,
                        metadata={
                            "new_key_id": new_key_id,
                            "new_key_prefix": key_prefix,
                            "name": resolved_name,
                            "scopes": resolved_scopes,
                        },
                    )
                    session.flush()
            except IntegrityError:
                continue

            return ApiKeyRotateResponse(
                revoked_key_id=normalized_key_id,
                new_key=ApiKeyIssueResponse(
                    key_id=new_key_id,
                    name=resolved_name,
                    key_prefix=key_prefix,
                    scopes=resolved_scopes,
                    status="active",
                    created_at=now,
                    last_used_at=None,
                    last_used_source=None,
                    revoked_at=None,
                    key=plaintext_key,
                ),
            )

        msg = "Failed to rotate API key. Please retry."
        raise RuntimeError(msg)

    def authenticate_api_key(self, token: str, *, source: str | None = None) -> AuthContext:
        key_prefix, key_secret = self._parse_api_key_token(token)
        with self._state_session_factory() as session, session.begin():
            stmt = (
                select(ApiKeyRow)
                .where(ApiKeyRow.key_prefix == key_prefix)
                .with_for_update()
            )
            row = session.execute(stmt).scalar_one_or_none()
            if row is None:
                msg = "API key not found."
                raise ApiKeyAuthenticationError(msg)
            if row.status != "active" or row.revoked_at is not None:
                msg = "API key revoked."
                raise ApiKeyAuthenticationError(msg)
            try:
                salt = bytes.fromhex(row.secret_salt)
            except ValueError as exc:
                msg = "Stored API key salt is malformed."
                raise ApiKeyAuthenticationError(msg) from exc
            expected_hash = self._hash_api_key_secret(
                secret=key_secret,
                salt=salt,
                iterations=max(int(row.hash_iterations), 1),
            )
            if not hmac.compare_digest(expected_hash, row.secret_hash):
                msg = "API key secret mismatch."
                raise ApiKeyAuthenticationError(msg)
            row.last_used_at = datetime.now(UTC)
            row.last_used_source = self._normalize_optional_source(source)
            scopes = self._deserialize_scopes(row.scopes_json)
            if not scopes:
                scopes = list(_DEFAULT_KEY_SCOPES)
            resolved_source = row.last_used_source or "unknown"
            self._insert_audit_row(
                session=session,
                account_key=row.account_key,
                actor_subject=row.key_id,
                actor_type="api_key",
                action="api_key_authenticated",
                target_type="api_key",
                target_id=row.key_id,
                metadata={"source": resolved_source},
            )
            claims = {
                "auth_type": "api_key",
                "key_id": row.key_id,
                "key_prefix": row.key_prefix,
                "account_key": row.account_key,
            }
            return AuthContext(
                subject=row.account_key,
                scopes=scopes,
                token=token,
                claims=claims,
            )

    def ingest(
        self,
        request: IngestRequest,
        *,
        account_key: str | None = None,
    ) -> IngestResponse:
        start = perf_counter()
        normalized_account_key = self._normalize_account_key(account_key)
        event = Event(
            entity_id=request.entity_id or self._config.default_entity_id,
            event_type=request.event_type or self._config.default_event_type,
            description=request.content,
            metadata=request.metadata or {},
        )
        processed = self._engine.process_input(event)
        decision = self._engine.make_storage_decision(
            processed,
            account_key=normalized_account_key,
        )
        stored = self._engine.store_memory(
            processed,
            decision,
            account_key=normalized_account_key,
        )
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

    def ingest_batch(
        self,
        events: list[IngestRequest],
        *,
        account_key: str | None = None,
    ) -> list[IngestResponse]:
        return [self.ingest(item, account_key=account_key) for item in events]

    def retrieve(
        self,
        request: RetrieveRequest,
        *,
        account_key: str | None = None,
    ) -> RetrieveResponse:
        start = perf_counter()
        normalized_account_key = self._normalize_account_key(account_key)
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
                entity_ids_fn(
                    request.entity_id,
                    account_key=normalized_account_key,
                )
                if callable(entity_ids_fn)
                else []
            )
            preselected = self._engine.storage.fetch_by_ids(
                entity_ids,
                account_key=normalized_account_key,
            )
            if not preselected:
                vector_store = getattr(self._engine, "vector_store", None)
                if vector_store is None:
                    preselected = self._engine.storage.search_candidates(
                        query_embedding,
                        top_k=pool_size,
                        account_key=normalized_account_key,
                    )
                else:
                    hits = vector_store.search(query_embedding, top_k=pool_size)
                    preselected = self._engine.storage.fetch_by_ids(
                        [hit.memory_id for hit in hits],
                        account_key=normalized_account_key,
                    )
        else:
            vector_store = getattr(self._engine, "vector_store", None)
            if vector_store is not None:
                hits = vector_store.search(query_embedding, top_k=pool_size)
                preselected = self._engine.storage.fetch_by_ids(
                    [hit.memory_id for hit in hits],
                    account_key=normalized_account_key,
                )
            else:
                preselected = self._engine.storage.search_candidates(
                    query_embedding,
                    top_k=pool_size,
                    account_key=normalized_account_key,
                )
        if len(preselected) < request.limit:
            fallback = self._engine.storage.search_candidates(
                query_embedding,
                top_k=max(pool_size, request.limit * 4),
                account_key=normalized_account_key,
            )
            seen_ids = {item.memory_id for item in preselected}
            preselected.extend(
                item for item in fallback if item.memory_id not in seen_ids
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
            account_key=normalized_account_key,
        )
        ranked = self._engine.ranker.rank(query_embedding, candidates, now=now)
        ranked = self._diversity_aware_rerank(ranked)
        ranked = self._reweight_ranked_by_query(
            query=request.query,
            ranked=ranked,
            candidates=candidates,
        )
        ranked = self._promote_primary_candidate_for_query(
            query=request.query,
            ranked=ranked,
        )
        selected = self._select_with_intent_caps(
            ranked,
            top_k=request.limit,
            query=request.query,
        )
        memories: list[Memory] = []
        for index, ranked_item in enumerate(selected, start=1):
            self._engine.storage.update_retrieval(
                ranked_item.memory.memory_id,
                account_key=normalized_account_key,
            )
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

    def feedback(
        self,
        request: FeedbackRequest,
        *,
        account_key: str | None = None,
    ) -> FeedbackResponse:
        start = perf_counter()
        normalized_account_key = self._normalize_account_key(account_key)
        existing = self._engine.storage.fetch_by_ids(
            [request.memory_id],
            account_key=normalized_account_key,
        )
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
            account_key=normalized_account_key,
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

    def feedback_batch(
        self,
        feedback: list[FeedbackRequest],
        *,
        account_key: str | None = None,
    ) -> list[FeedbackResponse]:
        return [self.feedback(item, account_key=account_key) for item in feedback]

    def status(self, account_key: str) -> StatusResponse:
        now = datetime.now(UTC)
        normalized_account_key = self._normalize_account_key(account_key)
        policy = self._plan_policy(normalized_account_key)
        with self._state_lock:
            latest_ingestion = self._latest_ingestion
        usage = self._read_usage_row(normalized_account_key)
        pilot_pro_request_row = self._read_pilot_pro_request(normalized_account_key)
        storage_mb = self._storage_usage_mb(account_key=normalized_account_key)
        active_api_keys = self._count_active_api_keys(normalized_account_key)
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
        pilot_pro_request = self._as_pilot_pro_request(
            row=pilot_pro_request_row,
            policy=policy,
        )
        metadata_summary = self._metadata_summary(normalized_account_key)

        return StatusResponse(
            connected=True,
            api_version=self._config.api_version,
            account_usage=AccountUsage(
                events_ingested_this_month=events_month,
                queries_this_month=queries_month,
                storage_usage_mb=storage_mb,
                active_api_keys=active_api_keys,
                quota=AccountQuota(
                    events_per_day=max(policy.ingest_events_per_month // 30, 1),
                    queries_per_day=max(policy.retrieve_queries_per_month // 30, 1),
                    events_per_month=policy.ingest_events_per_month,
                    queries_per_month=policy.retrieve_queries_per_month,
                    api_keys=policy.api_keys_limit,
                    retention_days=policy.retention_days,
                    plan=policy.plan,
                    reset_at=datetime.fromtimestamp(
                        self._next_month_reset_epoch(now),
                        tz=UTC,
                    ),
                    warning_threshold_percent=policy.warning_threshold_percent,
                    critical_threshold_percent=policy.critical_threshold_percent,
                ),
            ),
            pilot_pro_request=pilot_pro_request,
            latest_ingestion=latest_ingestion,
            uptime_percent=self._config.uptime_percent,
            metadata_summary=metadata_summary,
        )

    def tenant_metrics(self, account_key: str) -> TenantMetricsResponse:
        now = datetime.now(UTC)
        normalized_account_key = self._normalize_account_key(account_key)
        policy = self._plan_policy(normalized_account_key)
        usage = self._read_usage_row(normalized_account_key)
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
        active_api_keys = self._count_active_api_keys(normalized_account_key)
        storage_mb = self._storage_usage_mb(account_key=normalized_account_key)
        pilot_pro_request_row = self._read_pilot_pro_request(normalized_account_key)
        pilot_pro_requested_at = (
            pilot_pro_request_row.requested_at if pilot_pro_request_row else None
        )
        pilot_pro_requested = (
            pilot_pro_request_row is not None
            and self._normalize_pilot_pro_status(pilot_pro_request_row.status)
            == "requested"
        )
        return TenantMetricsResponse(
            generated_at=now,
            plan=policy.plan,
            reset_at=datetime.fromtimestamp(
                self._next_month_reset_epoch(now),
                tz=UTC,
            ),
            warning_threshold_percent=policy.warning_threshold_percent,
            critical_threshold_percent=policy.critical_threshold_percent,
            ingest=self._usage_metric(
                used=events_month,
                limit=policy.ingest_events_per_month,
                warning_threshold_percent=policy.warning_threshold_percent,
                critical_threshold_percent=policy.critical_threshold_percent,
            ),
            retrieve=self._usage_metric(
                used=queries_month,
                limit=policy.retrieve_queries_per_month,
                warning_threshold_percent=policy.warning_threshold_percent,
                critical_threshold_percent=policy.critical_threshold_percent,
            ),
            api_keys=self._usage_metric(
                used=active_api_keys,
                limit=policy.api_keys_limit,
                warning_threshold_percent=policy.warning_threshold_percent,
                critical_threshold_percent=policy.critical_threshold_percent,
            ),
            storage_usage_mb=storage_mb,
            pilot_pro_requested=pilot_pro_requested,
            pilot_pro_requested_at=pilot_pro_requested_at,
        )

    def _metadata_summary(self, account_key: str) -> MetadataSummary:
        limit = max(1, self._config.metadata_summary_window)
        records = self._engine.storage.list_recent_memories(
            limit=limit,
            account_key=account_key,
        )
        now = datetime.now(UTC)
        total = 0
        contested = 0
        conflict_guards = 0
        confirmed = 0
        fact_conflict_count = 0
        superseded_fact_references = 0
        mutable_numeric_facts = 0
        fact_family_counts: Counter[str] = Counter()
        total_age_days = 0.0
        for record in records:
            relationships = [str(item).strip() for item in record.relationships]
            inference_type = self._memory_inference_type(record)
            if not self._is_inferred_memory_record(
                record=record,
                relationships=relationships,
                inference_type=inference_type,
            ):
                continue
            intent = record.intent.strip().lower()
            if intent not in {"inferred_user_fact", "inferred_user_fact_conflict"}:
                continue
            total += 1
            age_days = max((now - record.created_at).total_seconds() / 86400.0, 0.0)
            total_age_days += age_days
            if intent == "inferred_user_fact_conflict":
                conflict_guards += 1
                contested += 1
                fact_conflict_count += 1
                fact_key = self._relationship_value(relationships, prefix="fact_key:")
                if fact_key:
                    family = self._fact_family(fact_key)
                    fact_family_counts[family] += 1
                continue
            fact_key = self._relationship_value(relationships, prefix="fact_key:")
            if fact_key:
                family = self._fact_family(fact_key)
                fact_family_counts[family] += 1
                if family in {"weight_current", "weight_target"}:
                    mutable_numeric_facts += 1
            fact_status = self._relationship_value(relationships, prefix="fact_status:") or ""
            clarification_required = (
                self._relationship_value(relationships, prefix="clarification_required:") == "true"
            )
            superseded_fact_references += len(
                self._relationship_values(relationships, prefix="supersedes:")
            )
            if fact_status == "contested" or clarification_required:
                contested += 1
                fact_conflict_count += 1
            else:
                confirmed += 1
        average_age = (total_age_days / total) if total else 0.0
        contested_ratio = (contested / total) if total else 0.0
        conflict_guard_ratio = (conflict_guards / total) if total else 0.0
        return MetadataSummary(
            total_inferred_facts=total,
            confirmed_facts=confirmed,
            contested_facts=contested,
            conflict_guards=conflict_guards,
            contested_ratio=contested_ratio,
            conflict_guard_ratio=conflict_guard_ratio,
            average_fact_age_days=average_age,
            fact_family_coverage=len(fact_family_counts),
            fact_family_counts=dict(sorted(fact_family_counts.items())),
            fact_conflict_count=fact_conflict_count,
            superseded_fact_references=superseded_fact_references,
            mutable_numeric_facts=mutable_numeric_facts,
        )

    @staticmethod
    def _fact_family(fact_key: str) -> str:
        normalized = fact_key.strip().lower()
        if ":" not in normalized:
            return normalized
        return normalized.split(":", 1)[0]

    @staticmethod
    def _usage_metric(
        *,
        used: int,
        limit: int | None,
        warning_threshold_percent: int,
        critical_threshold_percent: int,
    ) -> TenantUsageMetric:
        if limit is None or limit <= 0:
            return TenantUsageMetric(
                used=max(0, int(used)),
                limit=None,
                remaining=None,
                utilization_percent=0.0,
                status="ok",
            )
        normalized_used = max(0, int(used))
        normalized_limit = int(limit)
        remaining = max(normalized_limit - normalized_used, 0)
        utilization_percent = min(
            100.0,
            max(0.0, (float(normalized_used) / float(normalized_limit)) * 100.0),
        )
        status = "ok"
        if normalized_used >= normalized_limit:
            status = "limit"
        elif utilization_percent >= float(critical_threshold_percent):
            status = "critical"
        elif utilization_percent >= float(warning_threshold_percent):
            status = "warning"
        return TenantUsageMetric(
            used=normalized_used,
            limit=normalized_limit,
            remaining=remaining,
            utilization_percent=utilization_percent,
            status=status,
        )

    def request_pilot_pro(
        self,
        *,
        account_key: str,
        actor_subject: str | None,
        actor_email: str | None = None,
        actor_name: str | None = None,
    ) -> PilotProRequestResponse:
        normalized_account_key = self._normalize_account_key(account_key)
        normalized_actor_subject = (
            self._normalize_optional_actor_subject(actor_subject)
            or normalized_account_key
        )
        normalized_actor_email = self._normalize_optional_email(actor_email)
        normalized_actor_name = self._normalize_optional_display_name(actor_name)
        created = False
        should_send_email = False

        with self._state_session_factory() as session, session.begin():
            row = self._select_pilot_pro_request_for_update(
                session=session,
                account_key=normalized_account_key,
            )
            now = datetime.now(UTC)
            if row is None:
                row = ApiPilotProRequestRow(
                    account_key=normalized_account_key,
                    status="requested",
                    requested_by_subject=normalized_actor_subject,
                    requested_by_email=normalized_actor_email,
                    requested_by_name=normalized_actor_name,
                    requested_at=now,
                    email_sent_at=None,
                    email_last_attempt_at=None,
                    email_delivery_error=None,
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
                created = True
                should_send_email = True
            else:
                prior_status = self._normalize_pilot_pro_status(row.status)
                if prior_status != "requested":
                    row.status = "requested"
                    row.requested_at = now
                    row.email_sent_at = None
                    row.email_last_attempt_at = None
                    row.email_delivery_error = None
                    should_send_email = True
                row.requested_by_subject = normalized_actor_subject
                row.requested_by_email = normalized_actor_email or row.requested_by_email
                row.requested_by_name = normalized_actor_name or row.requested_by_name
                row.updated_at = now

            self._insert_audit_row(
                session=session,
                account_key=normalized_account_key,
                actor_subject=normalized_actor_subject,
                actor_type="dashboard_user",
                action="pilot_pro_requested",
                target_type="account",
                target_id=normalized_account_key,
                metadata={
                    "created": created,
                    "requested_by_email": normalized_actor_email,
                    "requested_by_name": normalized_actor_name,
                },
            )
            session.flush()

        email_sent = False
        if should_send_email:
            email_sent, delivery_error, attempted_at = self._send_pilot_pro_request_email(
                account_key=normalized_account_key,
                actor_subject=normalized_actor_subject,
                actor_email=normalized_actor_email,
                actor_name=normalized_actor_name,
            )
            with self._state_session_factory() as session, session.begin():
                row = self._select_pilot_pro_request_for_update(
                    session=session,
                    account_key=normalized_account_key,
                )
                if row is not None:
                    row.email_last_attempt_at = attempted_at
                    row.email_delivery_error = delivery_error
                    if email_sent:
                        row.email_sent_at = attempted_at
                    row.updated_at = datetime.now(UTC)
                    self._insert_audit_row(
                        session=session,
                        account_key=normalized_account_key,
                        actor_subject=normalized_actor_subject,
                        actor_type="system",
                        action=(
                            "pilot_pro_request_email_sent"
                            if email_sent
                            else "pilot_pro_request_email_failed"
                        ),
                        target_type="account",
                        target_id=normalized_account_key,
                        metadata={
                            "delivery_error": delivery_error,
                        },
                    )
        else:
            existing = self._read_pilot_pro_request(normalized_account_key)
            email_sent = bool(existing and existing.email_sent_at is not None)

        row = self._read_pilot_pro_request(normalized_account_key)
        return PilotProRequestResponse(
            request=self._as_pilot_pro_request(
                row=row,
                policy=self._plan_policy(normalized_account_key),
            ),
            created=created,
            email_sent=email_sent,
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

    def record_http_response(self, status_code: int) -> None:
        with self._state_lock:
            self._http_status_counts[status_code] = (
                self._http_status_counts.get(status_code, 0.0) + 1.0
            )

    def record_dashboard_auth_failure(self) -> None:
        with self._state_lock:
            self._metrics["dashboard_auth_failures_total"] += 1

    def record_dashboard_key_rotation_failure(self) -> None:
        with self._state_lock:
            self._metrics["dashboard_key_rotation_failures_total"] += 1

    def metrics_text(self) -> str:
        with self._state_lock:
            ingest_total = self._metrics["ingest_requests_total"]
            retrieve_total = self._metrics["retrieve_requests_total"]
            feedback_total = self._metrics["feedback_requests_total"]
            dashboard_auth_failures = self._metrics["dashboard_auth_failures_total"]
            key_rotation_failures = self._metrics[
                "dashboard_key_rotation_failures_total"
            ]
            status_counts = dict(self._http_status_counts)
        flash_metrics = self._engine.flash_metrics_snapshot()
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
            "# HELP orbit_dashboard_auth_failures_total Dashboard auth failures observed by API.",
            "# TYPE orbit_dashboard_auth_failures_total counter",
            f"orbit_dashboard_auth_failures_total {dashboard_auth_failures:.0f}",
            "# HELP orbit_dashboard_key_rotation_failures_total Dashboard key-rotation failures.",
            "# TYPE orbit_dashboard_key_rotation_failures_total counter",
            f"orbit_dashboard_key_rotation_failures_total {key_rotation_failures:.0f}",
            "# HELP orbit_uptime_seconds Process uptime in seconds.",
            "# TYPE orbit_uptime_seconds gauge",
            f"orbit_uptime_seconds {self._uptime_seconds():.3f}",
            "# HELP orbit_flash_pipeline_mode_async Flash pipeline mode (1 async, 0 sync).",
            "# TYPE orbit_flash_pipeline_mode_async gauge",
            f"orbit_flash_pipeline_mode_async {flash_metrics['mode_async']:.0f}",
            "# HELP orbit_flash_pipeline_workers Number of flash pipeline workers.",
            "# TYPE orbit_flash_pipeline_workers gauge",
            f"orbit_flash_pipeline_workers {flash_metrics['workers']:.0f}",
            "# HELP orbit_flash_pipeline_queue_depth Pending flash pipeline tasks.",
            "# TYPE orbit_flash_pipeline_queue_depth gauge",
            f"orbit_flash_pipeline_queue_depth {flash_metrics['queue_depth']:.0f}",
            "# HELP orbit_flash_pipeline_queue_capacity Flash pipeline queue capacity.",
            "# TYPE orbit_flash_pipeline_queue_capacity gauge",
            f"orbit_flash_pipeline_queue_capacity {flash_metrics['queue_capacity']:.0f}",
            "# HELP orbit_flash_pipeline_enqueued_total Total flash tasks enqueued.",
            "# TYPE orbit_flash_pipeline_enqueued_total counter",
            f"orbit_flash_pipeline_enqueued_total {flash_metrics['enqueued_total']:.0f}",
            "# HELP orbit_flash_pipeline_dropped_total Total flash tasks dropped due to queue pressure.",
            "# TYPE orbit_flash_pipeline_dropped_total counter",
            f"orbit_flash_pipeline_dropped_total {flash_metrics['dropped_total']:.0f}",
            "# HELP orbit_flash_pipeline_runs_total Total flash tasks executed.",
            "# TYPE orbit_flash_pipeline_runs_total counter",
            f"orbit_flash_pipeline_runs_total {flash_metrics['runs_total']:.0f}",
            "# HELP orbit_flash_pipeline_maintenance_total Total flash maintenance cycles.",
            "# TYPE orbit_flash_pipeline_maintenance_total counter",
            f"orbit_flash_pipeline_maintenance_total {flash_metrics['maintenance_total']:.0f}",
            "# HELP orbit_flash_pipeline_failures_total Total flash pipeline task failures.",
            "# TYPE orbit_flash_pipeline_failures_total counter",
            f"orbit_flash_pipeline_failures_total {flash_metrics['failures_total']:.0f}",
        ]
        lines.extend(
            [
                "# HELP orbit_http_responses_total API responses by status code.",
                "# TYPE orbit_http_responses_total counter",
            ]
        )
        for status_code in sorted(status_counts):
            lines.append(
                f'orbit_http_responses_total{{status_code="{status_code}"}} '
                f"{status_counts[status_code]:.0f}"
            )
        return "\n".join(lines) + "\n"

    def list_memories(
        self,
        limit: int,
        cursor: str | None,
        *,
        account_key: str | None = None,
    ) -> PaginatedMemoriesResponse:
        offset = 0
        if cursor:
            try:
                offset = max(0, int(cursor))
            except ValueError:
                offset = 0

        records = sorted(
            self._engine.storage.list_memories(
                account_key=self._normalize_account_key(account_key)
            ),
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
        inference_provenance = self._inference_provenance(record)
        fact_inference = self._fact_inference_metadata(record)
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
                "inference_provenance": inference_provenance,
                "fact_inference": fact_inference,
            },
            relevance_explanation=(
                "Ranked by semantic similarity + learned relevance model."
            ),
        )

    @classmethod
    def _inference_provenance(cls, record: MemoryRecord) -> dict[str, Any]:
        relationships = [str(item).strip() for item in record.relationships]
        inference_type = cls._relationship_value(
            relationships,
            prefix="inference_type:",
        )
        signature = cls._relationship_value(relationships, prefix="signature:")
        derived_from_ids = cls._relationship_values(relationships, prefix="derived_from:")
        supersedes_ids = cls._relationship_values(relationships, prefix="supersedes:")
        conflicts_with_ids = cls._relationship_values(
            relationships,
            prefix="conflicts_with:",
        )
        clarification_required = (
            cls._relationship_value(
                relationships,
                prefix="clarification_required:",
            )
            == "true"
        )

        is_inferred = cls._is_inferred_memory_record(
            record=record,
            relationships=relationships,
            inference_type=inference_type,
        )
        why = cls._inference_reason(
            record=record,
            is_inferred=is_inferred,
            inference_type=inference_type,
        )
        return {
            "is_inferred": is_inferred,
            "why": why,
            "when": record.created_at.isoformat() if is_inferred else None,
            "inference_type": inference_type,
            "signature": signature,
            "derived_from_memory_ids": derived_from_ids,
            "supersedes_memory_ids": supersedes_ids,
            "conflicts_with_memory_ids": conflicts_with_ids,
            "clarification_required": clarification_required,
        }

    @classmethod
    def _fact_inference_metadata(cls, record: MemoryRecord) -> dict[str, Any] | None:
        relationships = [str(item).strip() for item in record.relationships]
        fact_key = cls._relationship_value(relationships, prefix="fact_key:")
        if fact_key is None:
            return None
        return {
            "subject": cls._relationship_value(relationships, prefix="fact_subject:"),
            "fact_key": fact_key,
            "fact_type": cls._relationship_value(relationships, prefix="fact_type:"),
            "polarity": cls._relationship_value(relationships, prefix="fact_polarity:"),
            "status": cls._relationship_value(relationships, prefix="fact_status:"),
            "critical_fact": (
                cls._relationship_value(relationships, prefix="critical_fact:")
                == "true"
            ),
            "clarification_required": (
                cls._relationship_value(
                    relationships,
                    prefix="clarification_required:",
                )
                == "true"
            ),
            "conflicts_with_memory_ids": cls._relationship_values(
                relationships,
                prefix="conflicts_with:",
            ),
        }

    def _filter_candidates(
        self,
        entity_id: str | None,
        event_type: str | None,
        start_time: datetime | None,
        end_time: datetime | None,
        account_key: str | None = None,
    ) -> list[MemoryRecord]:
        if account_key is None:
            records = self._engine.storage.list_memories()
        else:
            records = self._engine.storage.list_memories(
                account_key=self._normalize_account_key(account_key)
            )
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

    def _reweight_ranked_by_query(
        self,
        *,
        query: str,
        ranked: list[Any],
        candidates: list[MemoryRecord],
    ) -> list[Any]:
        if not ranked:
            return ranked
        normalized_query = query.strip().lower()
        query_focus = self._query_focus(normalized_query)
        style_focused = query_focus == "style"
        mistake_focused = query_focus == "mistake"
        progress_focused = query_focus == "progress"
        fact_focused = query_focus == "fact"
        recency_focused = self._is_recency_or_progress_query(normalized_query)
        latest_progress = self._latest_progress_candidate(candidates)
        has_advancement_signal = (
            latest_progress is not None
            and self._has_advancement_signal(latest_progress)
        )
        fact_query_terms = _tokenize_query(normalized_query)

        reweighted: list[Any] = []
        for item in ranked:
            memory = item.memory
            intent = memory.intent.strip().lower()
            inference_type = self._memory_inference_type(memory)
            text = self._memory_text(memory)
            multiplier = 1.0

            if style_focused:
                if self._is_style_candidate(memory):
                    multiplier *= 2.25
                elif intent == "learning_progress":
                    multiplier *= 0.72
                elif intent == "inferred_learning_pattern":
                    multiplier *= 0.58
                elif intent.startswith("assistant_"):
                    multiplier *= 0.62

            if mistake_focused:
                if intent == "inferred_learning_pattern":
                    if inference_type == "recurring_failure_pattern":
                        multiplier *= 2.7
                    elif self._contains_failure_signal(text):
                        multiplier *= 1.7
                    else:
                        multiplier *= 0.42
                elif intent == "user_attempt":
                    multiplier *= 1.55 if self._contains_failure_signal(text) else 1.1
                elif intent == "learning_progress":
                    multiplier *= 0.74
                elif self._intent_bucket(intent) == "profile":
                    multiplier *= 0.55
                elif intent.startswith("assistant_"):
                    multiplier *= 0.62

            if progress_focused:
                if intent == "learning_progress":
                    if inference_type == "progress_accumulation":
                        multiplier *= 2.55
                    else:
                        multiplier *= 2.25
                elif self._intent_bucket(intent) == "profile":
                    multiplier *= 0.48
                elif intent == "inferred_learning_pattern":
                    multiplier *= 0.56
                elif intent.startswith("assistant_"):
                    multiplier *= 0.67

            if fact_focused:
                if intent == "inferred_user_fact_conflict":
                    multiplier *= 4.2
                elif intent == "inferred_user_fact":
                    multiplier *= 1.9
                    multiplier *= self._fact_query_alignment_multiplier(
                        memory=memory,
                        query_terms=fact_query_terms,
                    )
                elif self._intent_bucket(intent) == "profile":
                    multiplier *= 0.84
                elif intent.startswith("assistant_"):
                    multiplier *= 0.6

            if (
                has_advancement_signal
                and latest_progress is not None
                and self._is_stale_profile_memory(item.memory, latest_progress)
            ):
                multiplier *= 0.45 if recency_focused else 0.62

            adjusted_score = max(0.0, min(item.rank_score * multiplier, 2.0))
            reweighted.append(item.model_copy(update={"rank_score": adjusted_score}))

        reweighted.sort(key=lambda item: item.rank_score, reverse=True)
        return reweighted

    def _diversity_aware_rerank(
        self,
        ranked: list[RetrievedMemory],
    ) -> list[RetrievedMemory]:
        if not ranked:
            return ranked
        bucket_counts: dict[str, int] = {}
        reranked: list[RetrievedMemory] = []
        for item in ranked:
            bucket = self._intent_bucket(item.memory.intent)
            existing = bucket_counts.get(bucket, 0)
            repetition_penalty = 1.0 / (1.0 + 0.35 * existing)
            assistant_penalty = self._assistant_length_penalty(item.memory)
            novelty_bonus = 1.06 if existing == 0 and bucket != "assistant" else 1.0
            adjusted_score = max(
                0.0,
                min(
                    item.rank_score
                    * repetition_penalty
                    * assistant_penalty
                    * novelty_bonus,
                    2.0,
                ),
            )
            reranked.append(item.model_copy(update={"rank_score": adjusted_score}))
            bucket_counts[bucket] = existing + 1
        reranked.sort(key=lambda item: item.rank_score, reverse=True)
        return reranked

    def _query_focus(self, query: str) -> str:
        normalized_query = query.strip().lower()
        if self._is_style_or_format_query(normalized_query):
            return "style"
        if self._is_mistake_pattern_query(normalized_query):
            return "mistake"
        if self._is_fact_query(normalized_query):
            return "fact"
        if (
            self._is_architecture_or_progress_query(normalized_query)
            or self._is_recency_or_progress_query(normalized_query)
        ):
            return "progress"
        return "generic"

    def _promote_primary_candidate_for_query(
        self,
        *,
        query: str,
        ranked: list[Any],
    ) -> list[Any]:
        if len(ranked) < 2:
            return ranked
        query_focus = self._query_focus(query)
        if query_focus == "generic":
            return ranked

        preferred_index: int | None = None
        for idx, item in enumerate(ranked):
            memory = item.memory
            if query_focus == "style" and self._is_style_candidate(memory):
                preferred_index = idx
                break
            if query_focus == "mistake" and self._is_mistake_candidate(memory):
                preferred_index = idx
                break
            if query_focus == "progress" and self._is_progress_candidate(memory):
                preferred_index = idx
                break
        if preferred_index is None or preferred_index == 0:
            return ranked

        promoted = list(ranked)
        promoted_item = promoted.pop(preferred_index)
        promoted.insert(0, promoted_item)
        if len(promoted) > 1 and promoted[0].rank_score <= promoted[1].rank_score:
            bumped = promoted[1].rank_score + 1e-6
            promoted[0] = promoted[0].model_copy(update={"rank_score": bumped})
        return promoted

    def _memory_inference_type(self, memory: MemoryRecord) -> str | None:
        return self._relationship_value(memory.relationships, prefix="inference_type:")

    @staticmethod
    def _memory_text(memory: MemoryRecord) -> str:
        return f"{memory.summary} {memory.content}".strip().lower()

    @staticmethod
    def _contains_failure_signal(text: str) -> bool:
        failure_terms = {
            "error",
            "errors",
            "exception",
            "failed",
            "failing",
            "failure",
            "wrong",
            "mistake",
            "mistakes",
            "struggle",
            "struggles",
            "confuse",
            "confused",
            "confuses",
            "confusing",
            "bug",
            "bugs",
            "typeerror",
        }
        text_terms = set(re.findall(r"[a-z0-9]+", text.lower()))
        return bool(text_terms.intersection(failure_terms))

    def _is_style_candidate(self, memory: MemoryRecord) -> bool:
        intent = memory.intent.strip().lower()
        if intent not in {"preference_stated", "inferred_preference"}:
            return False
        text = self._memory_text(memory)
        style_markers = (
            "concise",
            "short",
            "detailed",
            "step-by-step",
            "style",
            "format",
        )
        return any(marker in text for marker in style_markers)

    def _is_mistake_candidate(self, memory: MemoryRecord) -> bool:
        intent = memory.intent.strip().lower()
        text = self._memory_text(memory)
        if intent == "user_attempt":
            return self._contains_failure_signal(text)
        if intent != "inferred_learning_pattern":
            return False
        inference_type = self._memory_inference_type(memory)
        if inference_type == "recurring_failure_pattern":
            return True
        return self._contains_failure_signal(text)

    def _is_progress_candidate(self, memory: MemoryRecord) -> bool:
        if memory.intent.strip().lower() != "learning_progress":
            return False
        text = self._memory_text(memory)
        stale_markers = (
            "profile_old",
            "absolute beginner",
            "beginner",
            "novice",
            "new to coding",
            "newbie",
        )
        return not any(marker in text for marker in stale_markers)

    def _is_inferred_progress_memory(self, memory: MemoryRecord) -> bool:
        if memory.intent.strip().lower() != "learning_progress":
            return False
        inference_type = self._memory_inference_type(memory)
        if inference_type == "progress_accumulation":
            return True
        relationships = [str(item).strip() for item in memory.relationships]
        if self._is_inferred_memory_record(
            record=memory,
            relationships=relationships,
            inference_type=inference_type,
        ):
            return memory.content.strip().lower().startswith("inferred progress:")
        return False

    @staticmethod
    def _is_mistake_pattern_query(query: str) -> bool:
        terms = _tokenize_query(query)
        if not terms:
            return False
        triggers = {
            "mistake",
            "mistakes",
            "error",
            "errors",
            "wrong",
            "repeat",
            "repeating",
            "repeatedly",
            "struggle",
            "struggles",
            "bug",
            "bugs",
            "confuse",
            "confused",
            "confuses",
            "confusing",
            "failing",
            "fails",
        }
        if terms.intersection(triggers):
            return True
        return "keep" in terms and ("repeating" in terms or "repeat" in terms)

    @staticmethod
    def _is_recency_or_progress_query(query: str) -> bool:
        terms = _tokenize_query(query)
        if not terms:
            return False
        triggers = {
            "now",
            "current",
            "latest",
            "today",
            "currently",
            "progress",
            "level",
            "stage",
            "right",
            "recent",
        }
        return bool(terms.intersection(triggers))

    @staticmethod
    def _latest_progress_candidate(
        candidates: list[MemoryRecord],
    ) -> MemoryRecord | None:
        progress_candidates = [
            memory
            for memory in candidates
            if memory.intent.strip().lower() == "learning_progress"
        ]
        if not progress_candidates:
            return None
        return max(progress_candidates, key=lambda memory: memory.created_at)

    @staticmethod
    def _has_advancement_signal(memory: MemoryRecord) -> bool:
        text = f"{memory.summary} {memory.content}".lower()
        triggers = (
            "completed",
            "understands",
            "intermediate",
            "advanced",
            "improving",
            "progressed",
            "now",
            "mastered",
            "comfortable",
        )
        return any(token in text for token in triggers)

    @staticmethod
    def _is_stale_profile_memory(
        candidate: MemoryRecord,
        latest_progress: MemoryRecord,
    ) -> bool:
        if candidate.created_at >= latest_progress.created_at:
            return False
        intent = candidate.intent.strip().lower()
        if intent not in {
            "preference_stated",
            "user_profile",
            "user_fact",
            "inferred_preference",
            "learning_progress",
        }:
            return False
        text = f"{candidate.summary} {candidate.content}".lower()
        stale_markers = (
            "profile_old",
            "absolute beginner",
            "beginner",
            "novice",
            "new to coding",
            "starting out",
            "entry level",
            "newbie",
        )
        return any(marker in text for marker in stale_markers)

    def _select_with_intent_caps(
        self,
        ranked: list[Any],
        top_k: int,
        query: str = "",
    ) -> list[Any]:
        if top_k <= 0:
            return []
        max_share = float(
            getattr(self._engine.config, "assistant_response_max_share", 0.25)
        )
        max_share = min(max(max_share, 0.0), 1.0)
        assistant_cap = self._assistant_cap(top_k, max_share=max_share)
        bucket_caps = self._intent_bucket_caps(
            top_k=top_k,
            query=query.strip().lower(),
            assistant_cap=assistant_cap,
        )
        selected: list[Any] = []
        bucket_counts: dict[str, int] = {}
        deferred: list[Any] = []
        for item in ranked:
            bucket = self._intent_bucket(item.memory.intent)
            cap = bucket_caps.get(bucket, top_k)
            current_count = bucket_counts.get(bucket, 0)
            if current_count >= cap:
                deferred.append(item)
                continue
            selected.append(item)
            bucket_counts[bucket] = current_count + 1
            if len(selected) >= top_k:
                break
        for item in deferred:
            if len(selected) >= top_k:
                break
            selected.append(item)
        return self._ensure_inferred_probe_coverage(
            query=query,
            ranked=ranked,
            selected=selected,
            top_k=top_k,
        )

    def _intent_bucket_caps(
        self,
        *,
        top_k: int,
        query: str,
        assistant_cap: int,
    ) -> dict[str, int]:
        query_focus = self._query_focus(query)
        profile_cap = min(top_k, max(2, int(top_k * 0.6)))
        pattern_cap = 1
        progress_cap = top_k
        attempt_cap = 1
        if query_focus == "style":
            profile_cap = top_k
            pattern_cap = 0
            progress_cap = 1
            attempt_cap = 0
        elif query_focus == "mistake":
            profile_cap = 1
            pattern_cap = top_k
            progress_cap = 1
            attempt_cap = min(2, top_k)
        elif query_focus == "progress":
            profile_cap = 0
            pattern_cap = 0
            progress_cap = top_k
            attempt_cap = 0
        elif self._is_architecture_or_progress_query(query):
            profile_cap = 1
            progress_cap = top_k
        elif self._is_mistake_pattern_query(query):
            pattern_cap = min(2, top_k)
            attempt_cap = 1
        return {
            "assistant": assistant_cap,
            "profile": profile_cap,
            "pattern": min(pattern_cap, top_k),
            "progress": min(progress_cap, top_k),
            "attempt": min(attempt_cap, top_k),
        }

    def _ensure_inferred_probe_coverage(
        self,
        *,
        query: str,
        ranked: list[Any],
        selected: list[Any],
        top_k: int,
    ) -> list[Any]:
        if not selected:
            return selected
        query_focus = self._query_focus(query.strip().lower())
        if query_focus == "progress":
            return self._ensure_inferred_progress_slot(
                ranked=ranked,
                selected=selected,
                top_k=top_k,
            )
        if query_focus == "style":
            return self._ensure_inferred_preference_slot(
                ranked=ranked,
                selected=selected,
                top_k=top_k,
            )
        return selected

    def _ensure_inferred_progress_slot(
        self,
        *,
        ranked: list[Any],
        selected: list[Any],
        top_k: int,
    ) -> list[Any]:
        if any(self._is_inferred_progress_memory(item.memory) for item in selected):
            return selected
        replacement = self._first_ranked_not_selected(
            ranked=ranked,
            selected=selected,
            predicate=lambda item: self._is_inferred_progress_memory(item.memory),
        )
        if replacement is None:
            return selected
        return self._replace_selected_tail(
            selected=selected,
            replacement=replacement,
            top_k=top_k,
            preferred_predicate=lambda item: item.memory.intent.strip().lower()
            == "learning_progress",
        )

    def _ensure_inferred_preference_slot(
        self,
        *,
        ranked: list[Any],
        selected: list[Any],
        top_k: int,
    ) -> list[Any]:
        if any(
            item.memory.intent.strip().lower() == "inferred_preference"
            for item in selected
        ):
            return selected
        replacement = self._first_ranked_not_selected(
            ranked=ranked,
            selected=selected,
            predicate=lambda item: item.memory.intent.strip().lower()
            == "inferred_preference",
        )
        if replacement is None:
            return selected
        return self._replace_selected_tail(
            selected=selected,
            replacement=replacement,
            top_k=top_k,
            preferred_predicate=lambda item: item.memory.intent.strip().lower()
            in {"preference_stated", "user_profile", "user_fact"},
        )

    @staticmethod
    def _replace_selected_tail(
        *,
        selected: list[Any],
        replacement: Any,
        top_k: int,
        preferred_predicate: Callable[[Any], bool],
    ) -> list[Any]:
        updated = list(selected)
        replace_index = len(updated) - 1
        for index in range(len(updated) - 1, -1, -1):
            if preferred_predicate(updated[index]):
                replace_index = index
                break
        updated[replace_index] = replacement
        return updated[:top_k]

    @staticmethod
    def _first_ranked_not_selected(
        *,
        ranked: list[Any],
        selected: list[Any],
        predicate: Callable[[Any], bool],
    ) -> Any | None:
        selected_ids = {item.memory.memory_id for item in selected}
        for item in ranked:
            if item.memory.memory_id in selected_ids:
                continue
            if predicate(item):
                return item
        return None

    @staticmethod
    def _is_architecture_or_progress_query(query: str) -> bool:
        terms = _tokenize_query(query)
        if not terms:
            return False
        architecture_terms = {
            "architecture",
            "project",
            "projects",
            "structuring",
            "structure",
            "module",
            "modules",
            "scaling",
            "scale",
            "advanced",
            "intermediate",
            "roadmap",
        }
        return bool(terms.intersection(architecture_terms))

    @staticmethod
    def _is_style_or_format_query(query: str) -> bool:
        terms = _tokenize_query(query)
        if not terms:
            return False
        style_terms = {
            "format",
            "formatted",
            "style",
            "tone",
            "wording",
            "template",
            "concise",
        }
        return bool(terms.intersection(style_terms))

    @staticmethod
    def _is_fact_query(query: str) -> bool:
        terms = _tokenize_query(query)
        if not terms:
            return False
        fact_terms = {
            "allergy",
            "allergic",
            "avoid",
            "constraint",
            "restrictions",
            "pineapple",
            "weight",
            "target",
            "goal",
            "goals",
            "currently",
            "weigh",
            "reason",
            "medical",
        }
        return bool(terms.intersection(fact_terms))

    @staticmethod
    def _fact_query_alignment_multiplier(
        *,
        memory: MemoryRecord,
        query_terms: set[str],
    ) -> float:
        relationships = [str(item).strip() for item in memory.relationships]
        fact_key = OrbitApiService._relationship_value(relationships, "fact_key:") or ""
        if not fact_key:
            return 1.0
        key_terms = set(re.findall(r"[a-z0-9]+", fact_key.lower()))
        if not key_terms:
            return 1.0
        overlap = len(key_terms.intersection(query_terms))
        if overlap <= 0:
            return 1.0
        return min(1.55, 1.0 + (0.15 * float(overlap)))

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
        account_key: str | None = None,
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
            records=(
                self._engine.storage.list_memories(limit=max(pool_size, top_k * 8))
                if account_key is None
                else self._engine.storage.list_memories(
                    limit=max(pool_size, top_k * 8),
                    account_key=self._normalize_account_key(account_key),
                )
            ),
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

    @classmethod
    def _intent_bucket(cls, intent: str) -> str:
        normalized = intent.strip().lower()
        if cls._is_assistant_intent(normalized):
            return "assistant"
        if normalized == "learning_progress":
            return "progress"
        if normalized == "user_attempt":
            return "attempt"
        if normalized == "inferred_learning_pattern":
            return "pattern"
        if normalized in {
            "preference_stated",
            "user_profile",
            "user_fact",
            "inferred_preference",
            "inferred_user_fact",
            "inferred_user_fact_conflict",
        }:
            return "profile"
        return "other"

    def _assistant_length_penalty(self, memory: MemoryRecord) -> float:
        if not self._is_assistant_intent(memory.intent):
            return 1.0
        word_count = len(memory.content.split())
        if word_count > 220:
            return 0.55
        if word_count > 150:
            return 0.72
        if word_count > 90:
            return 0.85
        return 0.94

    @staticmethod
    def _is_assistant_intent(intent: str) -> bool:
        return intent.strip().lower().startswith("assistant_")

    @staticmethod
    def _relationship_value(relationships: list[str], prefix: str) -> str | None:
        for relation in relationships:
            if relation.startswith(prefix):
                value = relation.removeprefix(prefix).strip()
                if value:
                    return value
        return None

    @staticmethod
    def _relationship_values(relationships: list[str], prefix: str) -> list[str]:
        values: list[str] = []
        seen: set[str] = set()
        for relation in relationships:
            if not relation.startswith(prefix):
                continue
            value = relation.removeprefix(prefix).strip()
            if not value or value in seen:
                continue
            seen.add(value)
            values.append(value)
        return values

    @staticmethod
    def _is_inferred_memory_record(
        *,
        record: MemoryRecord,
        relationships: list[str],
        inference_type: str | None,
    ) -> bool:
        normalized_intent = record.intent.strip().lower()
        if normalized_intent.startswith("inferred_"):
            return True
        if inference_type:
            return True
        if any(relation.strip().lower() == "inferred:true" for relation in relationships):
            return True
        return record.content.strip().lower().startswith("inferred ")

    @staticmethod
    def _inference_reason(
        *,
        record: MemoryRecord,
        is_inferred: bool,
        inference_type: str | None,
    ) -> str | None:
        if not is_inferred:
            return None
        reasons = {
            "repeat_question_cluster": (
                "Repeated semantically similar questions/attempts were clustered."
            ),
            "recurring_failure_pattern": (
                "Repeated failure/error signals were detected across related attempts."
            ),
            "progress_accumulation": (
                "Repeated positive progress/assessment signals indicated skill advancement."
            ),
            "feedback_preference_shift": (
                "Feedback trends indicated a stable response-style preference."
            ),
            "fact_extraction_v1": (
                "Structured user facts were inferred from explicit natural-language statements."
            ),
            "fact_conflict_guard_v1": (
                "Conflicting critical facts were detected; clarification is required before relying on them."
            ),
        }
        if inference_type in reasons:
            return reasons[inference_type]
        intent = record.intent.strip().lower()
        if intent == "inferred_preference":
            return reasons["feedback_preference_shift"]
        if intent == "inferred_learning_pattern":
            return "Adaptive personalization inferred a recurring learning pattern."
        if intent == "inferred_user_fact":
            return reasons["fact_extraction_v1"]
        if intent == "inferred_user_fact_conflict":
            return reasons["fact_conflict_guard_v1"]
        if intent == "learning_progress" and record.content.strip().lower().startswith(
            "inferred progress:"
        ):
            return reasons["progress_accumulation"]
        return "Derived by adaptive personalization from prior memory signals."

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
        policy = self._plan_policy(account_key)

        if kind == "event":
            limit = policy.ingest_events_per_month
            used = usage.events_month
            error_code = "quota_ingest_monthly_exceeded"
            quota_label = "ingest"
        elif kind == "query":
            limit = policy.retrieve_queries_per_month
            used = usage.queries_month
            error_code = "quota_retrieve_monthly_exceeded"
            quota_label = "retrieve"
        else:
            msg = f"Unsupported quota kind: {kind}"
            raise ValueError(msg)

        if used + amount > limit:
            snapshot = RateLimitSnapshot(
                limit=limit,
                remaining=max(limit - used, 0),
                reset_epoch=self._next_month_reset_epoch(now),
            )
            retry_after = max(snapshot.reset_epoch - int(now.timestamp()), 1)
            raise RateLimitExceededError(
                snapshot=snapshot,
                retry_after_seconds=retry_after,
                error_code=error_code,
                detail=(
                    f"Monthly {quota_label} quota reached for plan '{policy.plan}'. "
                    "Request Pilot Pro for higher limits or wait for monthly reset."
                ),
            )

        if kind == "event":
            usage.events_today += amount
            usage.events_month += amount
            remaining = max(limit - usage.events_month, 0)
        else:
            usage.queries_today += amount
            usage.queries_month += amount
            remaining = max(limit - usage.queries_month, 0)
        usage.updated_at = now

        return RateLimitSnapshot(
            limit=limit,
            remaining=remaining,
            reset_epoch=self._next_month_reset_epoch(now),
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
    def _next_month_reset_epoch(now: datetime) -> int:
        if now.month == 12:
            next_month = datetime(year=now.year + 1, month=1, day=1, tzinfo=UTC)
        else:
            next_month = datetime(
                year=now.year,
                month=now.month + 1,
                day=1,
                tzinfo=UTC,
            )
        return int(next_month.timestamp())

    def _read_usage_row(self, account_key: str) -> ApiAccountUsageRow | None:
        with self._state_session_factory() as session:
            stmt = select(ApiAccountUsageRow).where(
                ApiAccountUsageRow.account_key == account_key
            )
            return session.execute(stmt).scalar_one_or_none()

    def _read_pilot_pro_request(self, account_key: str) -> ApiPilotProRequestRow | None:
        with self._state_session_factory() as session:
            stmt = select(ApiPilotProRequestRow).where(
                ApiPilotProRequestRow.account_key == account_key
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

    def _select_pilot_pro_request_for_update(
        self,
        *,
        session: Session,
        account_key: str,
    ) -> ApiPilotProRequestRow | None:
        stmt = (
            select(ApiPilotProRequestRow)
            .where(ApiPilotProRequestRow.account_key == account_key)
            .with_for_update()
        )
        return session.execute(stmt).scalar_one_or_none()

    def _select_api_key_for_update(
        self,
        *,
        session: Session,
        account_key: str,
        key_id: str,
    ) -> ApiKeyRow | None:
        stmt = (
            select(ApiKeyRow)
            .where(ApiKeyRow.account_key == account_key)
            .where(ApiKeyRow.key_id == key_id)
            .with_for_update()
        )
        return session.execute(stmt).scalar_one_or_none()

    def _count_active_api_keys(self, account_key: str) -> int:
        normalized_account_key = self._normalize_account_key(account_key)
        with self._state_session_factory() as session:
            stmt = (
                select(func.count())
                .select_from(ApiKeyRow)
                .where(ApiKeyRow.account_key == normalized_account_key)
                .where(ApiKeyRow.status == "active")
                .where(ApiKeyRow.revoked_at.is_(None))
            )
            count = session.execute(stmt).scalar_one()
            return int(count or 0)

    def _active_api_key_count_with_session(
        self,
        *,
        session: Session,
        account_key: str,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(ApiKeyRow)
            .where(ApiKeyRow.account_key == account_key)
            .where(ApiKeyRow.status == "active")
            .where(ApiKeyRow.revoked_at.is_(None))
        )
        count = session.execute(stmt).scalar_one()
        return int(count or 0)

    def _plan_policy(self, account_key: str) -> PlanQuotaPolicy:
        normalized_account_key = self._normalize_account_key(account_key)
        if normalized_account_key in self._pilot_pro_accounts:
            return PlanQuotaPolicy(
                plan="pilot_pro",
                ingest_events_per_month=self._config.pilot_pro_events_per_month,
                retrieve_queries_per_month=self._config.pilot_pro_queries_per_month,
                api_keys_limit=self._config.pilot_pro_api_keys,
                retention_days=self._config.pilot_pro_retention_days,
                warning_threshold_percent=self._config.usage_warning_threshold_percent,
                critical_threshold_percent=self._config.usage_critical_threshold_percent,
            )
        return PlanQuotaPolicy(
            plan="free",
            ingest_events_per_month=self._config.free_events_per_month,
            retrieve_queries_per_month=self._config.free_queries_per_month,
            api_keys_limit=self._config.free_api_keys,
            retention_days=self._config.free_retention_days,
            warning_threshold_percent=self._config.usage_warning_threshold_percent,
            critical_threshold_percent=self._config.usage_critical_threshold_percent,
        )

    def _send_pilot_pro_request_email(
        self,
        *,
        account_key: str,
        actor_subject: str,
        actor_email: str | None,
        actor_name: str | None,
    ) -> tuple[bool, str | None, datetime]:
        attempted_at = datetime.now(UTC)
        api_key = (self._config.pilot_pro_resend_api_key or "").strip()
        admin_email = (self._config.pilot_pro_request_admin_email or "").strip()
        from_email = self._config.pilot_pro_request_from_email.strip()

        if not api_key or not admin_email or not from_email:
            return (
                False,
                "resend_not_configured: set ORBIT_PILOT_PRO_RESEND_API_KEY, "
                "ORBIT_PILOT_PRO_REQUEST_ADMIN_EMAIL, ORBIT_PILOT_PRO_REQUEST_FROM_EMAIL",
                attempted_at,
            )

        subject = f"Orbit Pilot Pro request - {account_key}"
        text_lines = [
            "New Pilot Pro request received.",
            "",
            f"Account key: {account_key}",
            f"Requested at (UTC): {attempted_at.isoformat()}",
            f"Requester subject: {actor_subject}",
            f"Requester email: {actor_email or 'not_provided'}",
            f"Requester name: {actor_name or 'not_provided'}",
        ]
        text_body = "\n".join(text_lines)

        payload = {
            "from": from_email,
            "to": [admin_email],
            "subject": subject,
            "text": text_body,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=self._config.pilot_pro_email_timeout_seconds) as client:
                response = client.post(
                    "https://api.resend.com/emails",
                    headers=headers,
                    json=payload,
                )
        except httpx.HTTPError as exc:
            message = str(exc).strip() or "unknown_http_error"
            return False, f"resend_transport_error: {message[:512]}", attempted_at

        if response.status_code >= 300:
            error_text = response.text.strip() or f"status={response.status_code}"
            return False, f"resend_http_error: {error_text[:1024]}", attempted_at

        return True, None, attempted_at

    def _as_pilot_pro_request(
        self,
        *,
        row: ApiPilotProRequestRow | None,
        policy: PlanQuotaPolicy,
    ) -> PilotProRequest:
        if row is None:
            default_status = "approved" if policy.plan == "pilot_pro" else "not_requested"
            return PilotProRequest(
                requested=False,
                status=default_status,
                requested_at=None,
                requested_by_email=None,
                requested_by_name=None,
                email_sent_at=None,
            )

        status = self._normalize_pilot_pro_status(row.status)
        if policy.plan == "pilot_pro":
            status = "approved"
        return PilotProRequest(
            requested=status == "requested",
            status=status,
            requested_at=row.requested_at,
            requested_by_email=row.requested_by_email,
            requested_by_name=row.requested_by_name,
            email_sent_at=row.email_sent_at,
        )

    def _lookup_dashboard_account_mapping(
        self,
        *,
        auth_issuer: str,
        auth_subject: str,
    ) -> str | None:
        with self._state_session_factory() as session:
            stmt = (
                select(ApiDashboardUserRow.account_key)
                .where(ApiDashboardUserRow.auth_issuer == auth_issuer)
                .where(ApiDashboardUserRow.auth_subject == auth_subject)
                .limit(1)
            )
            row = session.execute(stmt).one_or_none()
            if row is None:
                return None
            return self._normalize_account_key(str(row[0]))

    def _upsert_dashboard_account_mapping(
        self,
        *,
        account_key: str,
        auth_issuer: str,
        auth_subject: str,
        email: str | None,
        auth_provider: str | None,
        display_name: str | None,
        avatar_url: str | None,
        last_login_at: datetime,
    ) -> None:
        normalized_account_key = self._normalize_account_key(account_key)
        with self._state_session_factory() as session, session.begin():
            stmt = (
                select(ApiDashboardUserRow)
                .where(ApiDashboardUserRow.auth_issuer == auth_issuer)
                .where(ApiDashboardUserRow.auth_subject == auth_subject)
                .with_for_update()
            )
            row = session.execute(stmt).scalar_one_or_none()
            now = datetime.now(UTC)
            if row is None:
                session.add(
                    ApiDashboardUserRow(
                        account_key=normalized_account_key,
                        auth_issuer=auth_issuer,
                        auth_subject=auth_subject,
                        auth_provider=auth_provider,
                        email=email,
                        display_name=display_name,
                        avatar_url=avatar_url,
                        last_login_at=last_login_at,
                        created_at=now,
                        updated_at=now,
                    )
                )
                return
            existing_account_key = self._normalize_account_key(row.account_key)
            if existing_account_key != normalized_account_key:
                msg = (
                    "Auth identity is already bound to a different account. "
                    "Refusing unsafe reassignment."
                )
                raise AccountMappingError(msg)
            row.email = email or row.email
            row.auth_provider = auth_provider or row.auth_provider
            row.display_name = display_name or row.display_name
            row.avatar_url = avatar_url or row.avatar_url
            row.last_login_at = last_login_at
            row.updated_at = now

    @staticmethod
    def _insert_audit_row(
        *,
        session: Session,
        account_key: str,
        actor_subject: str,
        actor_type: str,
        action: str,
        target_type: str,
        target_id: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        payload = metadata or {}
        session.add(
            ApiAuditLogRow(
                account_key=account_key,
                actor_subject=actor_subject,
                actor_type=actor_type,
                action=action,
                target_type=target_type,
                target_id=target_id,
                metadata_json=json.dumps(
                    payload,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                ),
                created_at=datetime.now(UTC),
            )
        )

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

    @staticmethod
    def _as_api_key_summary(row: ApiKeyRow) -> ApiKeySummary:
        return ApiKeySummary(
            key_id=row.key_id,
            name=row.name,
            key_prefix=row.key_prefix,
            scopes=OrbitApiService._deserialize_scopes(row.scopes_json),
            status=row.status,
            created_at=row.created_at,
            last_used_at=row.last_used_at,
            last_used_source=row.last_used_source,
            revoked_at=row.revoked_at,
        )

    @staticmethod
    def _generate_api_key_material() -> tuple[str, str, str]:
        public_part = secrets.token_hex(6)
        secret_part = secrets.token_urlsafe(32).rstrip("=")
        key_prefix = f"{_API_KEY_PREFIX}{public_part}"
        key = f"{key_prefix}_{secret_part}"
        return key_prefix, secret_part, key

    @staticmethod
    def _parse_api_key_token(token: str) -> tuple[str, str]:
        normalized = token.strip()
        match = _API_KEY_PATTERN.fullmatch(normalized)
        if match is None:
            msg = "API key format is invalid."
            raise ApiKeyAuthenticationError(msg)
        public_part = match.group(1)
        secret_part = match.group(2)
        return f"{_API_KEY_PREFIX}{public_part}", secret_part

    @staticmethod
    def _hash_api_key_secret(*, secret: str, salt: bytes, iterations: int) -> str:
        derived = hashlib.pbkdf2_hmac(
            _API_KEY_HASH_ALGORITHM,
            secret.encode("utf-8"),
            salt,
            max(iterations, 1),
        )
        return derived.hex()

    @staticmethod
    def _deserialize_scopes(raw_scopes: str) -> list[str]:
        try:
            parsed = json.loads(raw_scopes)
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []
        normalized: list[str] = []
        seen: set[str] = set()
        for item in parsed:
            value = str(item).strip()
            if not value or value in seen:
                continue
            seen.add(value)
            normalized.append(value)
        return normalized

    @staticmethod
    def _normalize_api_key_name(value: str) -> str:
        normalized = value.strip()
        if not normalized:
            msg = "API key name cannot be empty"
            raise ValueError(msg)
        if len(normalized) > 128:
            msg = "API key name cannot exceed 128 characters"
            raise ValueError(msg)
        return normalized

    @staticmethod
    def _normalize_scopes(scopes: list[str] | None) -> list[str]:
        if scopes is None:
            return list(_DEFAULT_KEY_SCOPES)
        normalized: list[str] = []
        seen: set[str] = set()
        for scope in scopes:
            value = scope.strip()
            if not value or value in seen:
                continue
            seen.add(value)
            normalized.append(value)
        if not normalized:
            return list(_DEFAULT_KEY_SCOPES)
        return normalized

    @staticmethod
    def _normalize_key_id(value: str) -> str:
        normalized = value.strip()
        if not normalized:
            msg = "key_id cannot be empty"
            raise ValueError(msg)
        if len(normalized) > 36:
            msg = "key_id cannot exceed 36 characters"
            raise ValueError(msg)
        return normalized

    @staticmethod
    def _normalize_list_limit(value: int) -> int:
        if value <= 0:
            msg = "limit must be a positive integer"
            raise ValueError(msg)
        return min(value, 100)

    @staticmethod
    def _cursor_to_offset(cursor: str | None) -> int:
        if cursor is None:
            return 0
        normalized = cursor.strip()
        if not normalized:
            return 0
        try:
            value = int(normalized)
        except ValueError:
            return 0
        return max(value, 0)

    @staticmethod
    def _normalize_optional_source(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if len(normalized) > 128:
            return normalized[:128]
        return normalized

    @staticmethod
    def _normalize_optional_actor_subject(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if len(normalized) > 255:
            return normalized[:255]
        return normalized

    @staticmethod
    def _normalize_optional_email(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not normalized:
            return None
        if len(normalized) > 320:
            return normalized[:320]
        return normalized

    @staticmethod
    def _normalize_optional_display_name(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if len(normalized) > 255:
            return normalized[:255]
        return normalized

    @staticmethod
    def _normalize_pilot_pro_status(value: str | None) -> str:
        normalized = str(value or "").strip().lower()
        if normalized in {"requested", "approved", "rejected", "not_requested"}:
            return normalized
        if normalized:
            return normalized
        return "requested"

    @staticmethod
    def _normalize_auth_subject(value: str) -> str:
        normalized = value.strip()
        if not normalized:
            msg = "Auth subject cannot be empty"
            raise AccountMappingError(msg)
        if len(normalized) > 255:
            return normalized[:255]
        return normalized

    def _normalize_auth_issuer(self, value: Any) -> str:
        raw = str(value or "").strip()
        normalized = raw or self._config.jwt_issuer.strip() or "orbit"
        if len(normalized) > 255:
            return normalized[:255]
        return normalized

    def _account_key_from_claims(self, claims: dict[str, Any]) -> str | None:
        candidates = (
            claims.get("account_key"),
            claims.get("acct"),
            claims.get("tenant"),
            claims.get("org"),
            claims.get("organization"),
        )
        for candidate in candidates:
            if candidate is None:
                continue
            normalized = self._normalize_account_key(str(candidate))
            if normalized != "default":
                return normalized
        return None

    @staticmethod
    def _email_from_claims(claims: dict[str, Any]) -> str | None:
        raw_email = claims.get("email")
        if raw_email is None:
            return None
        normalized = str(raw_email).strip().lower()
        if not normalized:
            return None
        if len(normalized) > 320:
            return normalized[:320]
        return normalized

    @staticmethod
    def _display_name_from_claims(claims: dict[str, Any]) -> str | None:
        candidates = (
            claims.get("name"),
            claims.get("preferred_username"),
            claims.get("login"),
        )
        for candidate in candidates:
            if candidate is None:
                continue
            normalized = str(candidate).strip()
            if not normalized:
                continue
            if len(normalized) > 255:
                return normalized[:255]
            return normalized
        return None

    @staticmethod
    def _auth_provider_from_claims(claims: dict[str, Any]) -> str | None:
        candidates = (
            claims.get("auth_provider"),
            claims.get("idp"),
            claims.get("provider"),
        )
        for candidate in candidates:
            if candidate is None:
                continue
            normalized = str(candidate).strip().lower()
            if not normalized:
                continue
            if len(normalized) > 64:
                return normalized[:64]
            return normalized
        return None

    @staticmethod
    def _avatar_url_from_claims(claims: dict[str, Any]) -> str | None:
        candidates = (
            claims.get("picture"),
            claims.get("avatar_url"),
        )
        for candidate in candidates:
            if candidate is None:
                continue
            normalized = str(candidate).strip()
            if not normalized:
                continue
            lowered = normalized.lower()
            if not (lowered.startswith("http://") or lowered.startswith("https://")):
                continue
            if len(normalized) > 1024:
                return normalized[:1024]
            return normalized
        return None

    @staticmethod
    def _provision_dashboard_account_key(*, issuer: str, subject: str) -> str:
        digest = hashlib.sha256(f"{issuer}:{subject}".encode()).hexdigest()
        return f"acct_{digest[:24]}"

    def _storage_usage_mb(self, account_key: str | None = None) -> float:
        if account_key is not None:
            normalized_account_key = self._normalize_account_key(account_key)
            account_records = self._engine.storage.list_memories(
                account_key=normalized_account_key
            )
            if not account_records:
                return 0.0
            approx_bytes = 0
            for record in account_records:
                approx_bytes += len(record.content.encode("utf-8"))
                approx_bytes += len(record.summary.encode("utf-8"))
                approx_bytes += len(record.intent.encode("utf-8"))
                approx_bytes += sum(len(item.encode("utf-8")) for item in record.entities)
                approx_bytes += sum(
                    len(item.encode("utf-8")) for item in record.relationships
                )
                approx_bytes += len(record.semantic_embedding) * 4
                approx_bytes += len(record.raw_embedding) * 4
            return float(approx_bytes) / (1024.0 * 1024.0)

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

    @staticmethod
    def _normalize_account_key(account_key: str | None) -> str:
        if account_key is None:
            return "default"
        normalized = account_key.strip()
        return normalized or "default"


def _tokenize_query(query: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", query.lower()))
