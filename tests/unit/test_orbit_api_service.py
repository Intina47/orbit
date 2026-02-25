from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from decision_engine.models import MemoryRecord, RetrievedMemory, StorageTier
from memory_engine.config import EngineConfig
from memory_engine.storage.db import ApiDashboardUserRow
from orbit.models import FeedbackRequest, IngestRequest, RetrieveRequest
from orbit_api.auth import AuthContext
from orbit_api.config import ApiConfig
from orbit_api.service import (
    AccountMappingError,
    ApiKeyAuthenticationError,
    IdempotencyConflictError,
    OrbitApiService,
    RateLimitExceededError,
)


def _service(tmp_path: Path) -> OrbitApiService:
    db_path = tmp_path / "service.db"
    api_config = ApiConfig(
        database_url=f"sqlite:///{db_path}",
        sqlite_fallback_path=str(db_path),
        free_events_per_day=2,
        free_queries_per_day=2,
    )
    engine_config = EngineConfig(
        sqlite_path=str(db_path),
        database_url=f"sqlite:///{db_path}",
        embedding_dim=16,
        persistent_confidence_prior=0.0,
        ephemeral_confidence_prior=0.0,
        ranker_min_training_samples=2,
        ranker_training_batch_size=2,
    )
    return OrbitApiService(api_config=api_config, engine_config=engine_config)


def _retrieved(
    memory_id: str,
    *,
    intent: str,
    content: str,
    score: float,
    age_days: float = 0.0,
    relationships: list[str] | None = None,
) -> RetrievedMemory:
    now = datetime.now(UTC)
    created_at = now - timedelta(days=age_days)
    memory = MemoryRecord(
        memory_id=memory_id,
        event_id=f"event-{memory_id}",
        content=content,
        summary=content,
        intent=intent,
        entities=["alice"],
        relationships=list(relationships or []),
        raw_embedding=[0.1, 0.2],
        semantic_embedding=[0.1, 0.2],
        semantic_key=f"key-{memory_id}",
        created_at=created_at,
        updated_at=now,
        retrieval_count=1,
        avg_outcome_signal=0.0,
        storage_tier=StorageTier.PERSISTENT,
        latest_importance=0.8,
    )
    return RetrievedMemory(memory=memory, rank_score=score)


def test_service_quota_enforcement(tmp_path: Path) -> None:
    service = _service(tmp_path)
    try:
        snapshot = service.consume_event_quota("acct_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        assert snapshot.limit == 2
        assert snapshot.remaining == 1
        service.consume_event_quota("acct_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        with pytest.raises(RateLimitExceededError):
            service.consume_event_quota("acct_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    finally:
        service.close()


def test_service_ingest_retrieve_feedback_and_status(tmp_path: Path) -> None:
    service = _service(tmp_path)
    api_key = "acct_yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy"
    try:
        ingest = service.ingest(
            IngestRequest(
                content="Alice prefers short explanations",
                event_type="user_question",
                entity_id="alice",
            )
        )
        assert ingest.stored is True

        retrieve = service.retrieve(
            RetrieveRequest(query="What should I know about Alice?", limit=5)
        )
        assert retrieve.total_candidates >= 1
        assert retrieve.memories

        feedback = service.feedback(
            FeedbackRequest(memory_id=ingest.memory_id, helpful=True, outcome_value=1.0)
        )
        assert feedback.recorded is True

        status = service.status(api_key)
        assert status.connected is True
        assert status.account_usage.storage_usage_mb >= 0.0

        paged = service.list_memories(limit=10, cursor=None)
        assert paged.data
        assert paged.has_more in {True, False}

        metrics = service.metrics_text()
        assert "orbit_ingest_requests_total" in metrics
    finally:
        service.close()


def test_service_metrics_include_http_status_and_dashboard_failures(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    try:
        service.record_http_response(200)
        service.record_http_response(401)
        service.record_http_response(401)
        service.record_dashboard_auth_failure()
        service.record_dashboard_key_rotation_failure()

        metrics = service.metrics_text()
        assert 'orbit_http_responses_total{status_code="200"} 1' in metrics
        assert 'orbit_http_responses_total{status_code="401"} 2' in metrics
        assert "orbit_dashboard_auth_failures_total 1" in metrics
        assert "orbit_dashboard_key_rotation_failures_total 1" in metrics
    finally:
        service.close()


def test_service_feedback_missing_memory(tmp_path: Path) -> None:
    service = _service(tmp_path)
    try:
        with pytest.raises(KeyError):
            service.feedback(FeedbackRequest(memory_id="missing", helpful=False))
    finally:
        service.close()


def test_service_isolates_memories_by_account_key(tmp_path: Path) -> None:
    service = _service(tmp_path)
    try:
        ingest_a = service.ingest(
            IngestRequest(
                content="Tenant A private profile memory",
                event_type="user_profile",
                entity_id="shared",
            ),
            account_key="acct_a",
        )
        ingest_b = service.ingest(
            IngestRequest(
                content="Tenant B private profile memory",
                event_type="user_profile",
                entity_id="shared",
            ),
            account_key="acct_b",
        )

        retrieve_a = service.retrieve(
            RetrieveRequest(
                query="What do I know about shared?",
                entity_id="shared",
                limit=10,
            ),
            account_key="acct_a",
        )
        ids_a = {item.memory_id for item in retrieve_a.memories}
        assert ingest_a.memory_id in ids_a
        assert ingest_b.memory_id not in ids_a

        listed_b = service.list_memories(limit=10, cursor=None, account_key="acct_b")
        ids_b = {item.memory_id for item in listed_b.data}
        assert ingest_b.memory_id in ids_b
        assert ingest_a.memory_id not in ids_b

        with pytest.raises(KeyError):
            service.feedback(
                FeedbackRequest(
                    memory_id=ingest_a.memory_id,
                    helpful=True,
                    outcome_value=1.0,
                ),
                account_key="acct_b",
            )
    finally:
        service.close()


def test_service_quota_persists_across_restart(tmp_path: Path) -> None:
    service = _service(tmp_path)
    try:
        first = service.consume_event_quota("acct_persist")
        assert first.remaining == 1
    finally:
        service.close()

    restarted = _service(tmp_path)
    try:
        second = restarted.consume_event_quota("acct_persist")
        assert second.remaining == 0
        with pytest.raises(RateLimitExceededError):
            restarted.consume_event_quota("acct_persist")
    finally:
        restarted.close()


def test_service_idempotent_ingest_replay_and_conflict(tmp_path: Path) -> None:
    service = _service(tmp_path)
    request = IngestRequest(
        content="Alice prefers short explanations",
        event_type="user_question",
        entity_id="alice",
    )
    try:
        first, first_snapshot, first_replayed = service.ingest_with_quota(
            account_key="acct_idempotent",
            request=request,
            idempotency_key="ingest-1",
        )
        assert first_replayed is False
        assert first_snapshot.remaining == 1

        replay, replay_snapshot, replayed = service.ingest_with_quota(
            account_key="acct_idempotent",
            request=request,
            idempotency_key="ingest-1",
        )
        assert replayed is True
        assert replay.memory_id == first.memory_id
        assert replay_snapshot.remaining == 1

        with pytest.raises(IdempotencyConflictError):
            service.ingest_with_quota(
                account_key="acct_idempotent",
                request=IngestRequest(
                    content="Different payload",
                    event_type="user_question",
                    entity_id="alice",
                ),
                idempotency_key="ingest-1",
            )

        final_snapshot = service.consume_event_quota("acct_idempotent")
        assert final_snapshot.remaining == 0
    finally:
        service.close()


def test_service_idempotency_persists_across_restart(tmp_path: Path) -> None:
    request = IngestRequest(
        content="Persist idempotent response",
        event_type="user_question",
        entity_id="alice",
    )
    first_memory_id = ""
    service = _service(tmp_path)
    try:
        first, _, _ = service.ingest_with_quota(
            account_key="acct_replay",
            request=request,
            idempotency_key="persist-key",
        )
        first_memory_id = first.memory_id
    finally:
        service.close()

    restarted = _service(tmp_path)
    try:
        replay, snapshot, replayed = restarted.ingest_with_quota(
            account_key="acct_replay",
            request=request,
            idempotency_key="persist-key",
        )
        assert replayed is True
        assert replay.memory_id == first_memory_id
        assert snapshot.remaining == 1
    finally:
        restarted.close()


def test_service_idempotent_ingest_batch_replay(tmp_path: Path) -> None:
    service = _service(tmp_path)
    events = [
        IngestRequest(
            content="batch event 1",
            event_type="user_question",
            entity_id="alice",
        ),
        IngestRequest(
            content="batch event 2",
            event_type="user_question",
            entity_id="alice",
        ),
    ]
    try:
        first, first_snapshot, first_replayed = service.ingest_batch_with_quota(
            account_key="acct_batch",
            events=events,
            idempotency_key="batch-1",
        )
        assert first_replayed is False
        assert len(first) == 2
        assert first_snapshot.remaining == 0

        replay, replay_snapshot, replayed = service.ingest_batch_with_quota(
            account_key="acct_batch",
            events=events,
            idempotency_key="batch-1",
        )
        assert replayed is True
        assert len(replay) == 2
        assert replay_snapshot.remaining == 0
    finally:
        service.close()


def test_service_issue_list_and_authenticate_api_key(tmp_path: Path) -> None:
    service = _service(tmp_path)
    try:
        issued = service.issue_api_key(
            account_key="acct_dash",
            name="prod-key",
            scopes=["read", "write", "read"],
        )
        assert issued.key.startswith("orbit_pk_")
        assert issued.key_prefix.startswith("orbit_pk_")
        assert issued.scopes == ["read", "write"]

        listed_before = service.list_api_keys(account_key="acct_dash")
        assert len(listed_before.data) == 1
        assert listed_before.data[0].last_used_at is None

        auth_context = service.authenticate_api_key(issued.key)
        assert auth_context.subject == "acct_dash"
        assert auth_context.claims["auth_type"] == "api_key"
        assert auth_context.claims["key_id"] == issued.key_id
        assert "read" in auth_context.scopes

        listed_after = service.list_api_keys(account_key="acct_dash")
        assert listed_after.data[0].last_used_at is not None
    finally:
        service.close()


def test_service_revoked_api_key_cannot_authenticate(tmp_path: Path) -> None:
    service = _service(tmp_path)
    try:
        issued = service.issue_api_key(
            account_key="acct_revoke",
            name="revoke-me",
            scopes=["write"],
        )
        revoked = service.revoke_api_key(
            account_key="acct_revoke",
            key_id=issued.key_id,
        )
        assert revoked.revoked is True
        assert revoked.revoked_at is not None

        with pytest.raises(ApiKeyAuthenticationError):
            service.authenticate_api_key(issued.key)
    finally:
        service.close()


def test_service_api_key_revoke_is_account_scoped(tmp_path: Path) -> None:
    service = _service(tmp_path)
    try:
        issued = service.issue_api_key(
            account_key="acct_a",
            name="tenant-a-key",
            scopes=[],
        )
        with pytest.raises(KeyError):
            service.revoke_api_key(account_key="acct_b", key_id=issued.key_id)
    finally:
        service.close()


def test_service_rotate_api_key_replaces_old_key(tmp_path: Path) -> None:
    service = _service(tmp_path)
    try:
        issued = service.issue_api_key(
            account_key="acct_rotate",
            name="rotate-me",
            scopes=["read", "write", "feedback"],
        )
        rotated = service.rotate_api_key(
            account_key="acct_rotate",
            key_id=issued.key_id,
            name="rotate-me-v2",
            scopes=["read", "write", "feedback"],
        )
        assert rotated.revoked_key_id == issued.key_id
        assert rotated.new_key.name == "rotate-me-v2"
        assert rotated.new_key.key.startswith("orbit_pk_")

        with pytest.raises(ApiKeyAuthenticationError):
            service.authenticate_api_key(issued.key)
        authenticated_new = service.authenticate_api_key(rotated.new_key.key)
        assert authenticated_new.subject == "acct_rotate"
    finally:
        service.close()


def test_service_list_api_keys_paginates(tmp_path: Path) -> None:
    service = _service(tmp_path)
    try:
        for idx in range(3):
            service.issue_api_key(
                account_key="acct_page",
                name=f"page-{idx}",
                scopes=["read", "write"],
            )

        first = service.list_api_keys(account_key="acct_page", limit=2, cursor=None)
        assert len(first.data) == 2
        assert first.has_more is True
        assert first.cursor is not None

        second = service.list_api_keys(
            account_key="acct_page",
            limit=2,
            cursor=first.cursor,
        )
        assert len(second.data) == 1
        assert second.has_more is False
        assert second.cursor is None
    finally:
        service.close()


def test_service_resolve_account_context_with_claim_mapping(tmp_path: Path) -> None:
    service = _service(tmp_path)
    try:
        auth = AuthContext(
            subject="oidc-user-1",
            scopes=["read", "write"],
            token="jwt-token",
            claims={"iss": "issuer-a", "account_key": "acct_shared"},
        )
        resolved = service.resolve_account_context(auth)
        assert resolved.subject == "acct_shared"
        assert resolved.claims["auth_subject"] == "oidc-user-1"

        same_identity_different_account = AuthContext(
            subject="oidc-user-1",
            scopes=["read"],
            token="jwt-token",
            claims={"iss": "issuer-a", "account_key": "acct_other"},
        )
        with pytest.raises(AccountMappingError):
            service.resolve_account_context(same_identity_different_account)
    finally:
        service.close()


def test_service_resolve_account_context_persists_dashboard_identity_profile(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    try:
        auth = AuthContext(
            subject="github:12345",
            scopes=["read", "write"],
            token="jwt-token",
            claims={
                "iss": "https://github.com",
                "email": "DevUser@Example.com",
                "name": "Dev User",
                "picture": "https://avatars.githubusercontent.com/u/12345",
                "auth_provider": "github",
            },
        )
        resolved = service.resolve_account_context(auth)
        assert resolved.subject.startswith("acct_")
        assert resolved.claims["auth_provider"] == "github"

        engine = create_engine(service.config.database_url, future=True)
        try:
            with Session(engine) as session:
                stmt = (
                    select(ApiDashboardUserRow)
                    .where(ApiDashboardUserRow.auth_issuer == "https://github.com")
                    .where(ApiDashboardUserRow.auth_subject == "github:12345")
                )
                row = session.execute(stmt).scalar_one()
                assert row.account_key == resolved.subject
                assert row.email == "devuser@example.com"
                assert row.auth_provider == "github"
                assert row.display_name == "Dev User"
                assert row.avatar_url == "https://avatars.githubusercontent.com/u/12345"
                assert row.last_login_at is not None
        finally:
            engine.dispose()
    finally:
        service.close()


def test_service_boosts_inferred_pattern_for_mistake_queries(tmp_path: Path) -> None:
    service = _service(tmp_path)
    try:
        assistant = _retrieved(
            "assistant",
            intent="assistant_response",
            content="Long generic answer about python.",
            score=0.72,
        )
        profile = _retrieved(
            "profile",
            intent="preference_stated",
            content="Alice prefers short explanations.",
            score=0.70,
        )
        pattern = _retrieved(
            "pattern",
            intent="inferred_learning_pattern",
            content="PATTERN: Alice repeatedly confuses list mutation and reassignment.",
            score=0.55,
        )
        reweighted = service._reweight_ranked_by_query(
            query="What mistake does Alice keep repeating in Python?",
            ranked=[assistant, profile, pattern],
            candidates=[assistant.memory, profile.memory, pattern.memory],
        )
        assert reweighted[0].memory.intent == "inferred_learning_pattern"
        assert reweighted[0].rank_score > reweighted[1].rank_score
    finally:
        service.close()


def test_service_prefers_failure_pattern_over_generic_topic_cluster(tmp_path: Path) -> None:
    service = _service(tmp_path)
    try:
        generic_pattern = _retrieved(
            "pattern_generic",
            intent="inferred_learning_pattern",
            content=(
                "Inferred learning pattern: alice repeatedly asks about project architecture."
            ),
            score=0.91,
            relationships=["inference_type:repeat_question_cluster"],
        )
        failure_pattern = _retrieved(
            "pattern_failure",
            intent="inferred_learning_pattern",
            content=(
                "Inferred learning pattern: alice repeatedly struggles with TypeError on list indexing."
            ),
            score=0.66,
            relationships=["inference_type:recurring_failure_pattern"],
        )
        progress = _retrieved(
            "progress",
            intent="learning_progress",
            content="PROGRESS: Alice now understands modular architecture.",
            score=0.84,
        )
        reweighted = service._reweight_ranked_by_query(
            query="What mistake does Alice keep repeating in Python?",
            ranked=[generic_pattern, progress, failure_pattern],
            candidates=[generic_pattern.memory, progress.memory, failure_pattern.memory],
        )
        promoted = service._promote_primary_candidate_for_query(
            query="What mistake does Alice keep repeating in Python?",
            ranked=reweighted,
        )
        assert promoted[0].memory.memory_id == "pattern_failure"
    finally:
        service.close()


def test_service_promotes_learning_progress_for_architecture_queries(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    try:
        profile = _retrieved(
            "profile",
            intent="inferred_preference",
            content="Inferred preference: Alice responds better to concise explanations.",
            score=0.93,
            relationships=["inference_type:feedback_preference_shift"],
        )
        progress = _retrieved(
            "progress",
            intent="learning_progress",
            content="PROGRESS: Alice now understands module architecture and service boundaries.",
            score=0.72,
            relationships=["inference_type:progress_accumulation"],
        )
        reweighted = service._reweight_ranked_by_query(
            query="What is Alice's current level for project architecture and what is next?",
            ranked=[profile, progress],
            candidates=[profile.memory, progress.memory],
        )
        promoted = service._promote_primary_candidate_for_query(
            query="What is Alice's current level for project architecture and what is next?",
            ranked=reweighted,
        )
        assert promoted[0].memory.intent == "learning_progress"
    finally:
        service.close()


def test_service_suppresses_stale_profile_when_newer_progress_exists(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    try:
        stale_profile = _retrieved(
            "stale_profile",
            intent="preference_stated",
            content="PROFILE_OLD: Alice is an absolute beginner in Python.",
            score=0.78,
            age_days=14.0,
        )
        fresh_progress = _retrieved(
            "fresh_progress",
            intent="learning_progress",
            content="PROGRESS: Alice now understands classes and intermediate architecture.",
            score=0.66,
            age_days=0.1,
        )
        reweighted = service._reweight_ranked_by_query(
            query="How should I help Alice now with project architecture?",
            ranked=[stale_profile, fresh_progress],
            candidates=[stale_profile.memory, fresh_progress.memory],
        )
        assert reweighted[0].memory.intent == "learning_progress"
        assert reweighted[0].rank_score > reweighted[1].rank_score
    finally:
        service.close()


def test_service_diversifies_profiles_for_architecture_queries(tmp_path: Path) -> None:
    service = _service(tmp_path)
    try:
        profile_1 = _retrieved(
            "profile_1",
            intent="preference_stated",
            content="PROFILE: Alice prefers short explanations.",
            score=0.95,
        )
        profile_2 = _retrieved(
            "profile_2",
            intent="preference_stated",
            content="PROFILE: Alice learns with analogies.",
            score=0.94,
        )
        progress_1 = _retrieved(
            "progress_1",
            intent="learning_progress",
            content="PROGRESS: Alice completed loops and functions lessons.",
            score=0.93,
        )
        pattern = _retrieved(
            "pattern_1",
            intent="inferred_learning_pattern",
            content="PATTERN: Alice confuses list mutation and reassignment.",
            score=0.92,
        )
        progress_2 = _retrieved(
            "progress_2",
            intent="learning_progress",
            content="PROGRESS: Alice now understands classes and basic OOP.",
            score=0.91,
        )

        selected = service._select_with_intent_caps(
            [profile_1, profile_2, progress_1, pattern, progress_2],
            top_k=4,
            query="Alice now asks about structuring larger projects and architecture.",
        )
        selected_intents = [item.memory.intent for item in selected]
        assert selected_intents[:2] == ["learning_progress", "learning_progress"]
        assert selected_intents.count("learning_progress") >= 2
        assert selected_intents.count("preference_stated") <= 2
        assert "inferred_learning_pattern" not in selected_intents
    finally:
        service.close()


def test_service_preserves_profile_density_for_style_queries(tmp_path: Path) -> None:
    service = _service(tmp_path)
    try:
        profile_1 = _retrieved(
            "profile_a",
            intent="preference_stated",
            content="PROFILE: Alice prefers short explanations.",
            score=0.95,
        )
        profile_2 = _retrieved(
            "profile_b",
            intent="preference_stated",
            content="PROFILE: Alice learns with analogies.",
            score=0.94,
        )
        profile_3 = _retrieved(
            "profile_c",
            intent="preference_stated",
            content="PROFILE: Alice likes compact code snippets.",
            score=0.93,
        )
        progress_1 = _retrieved(
            "progress_a",
            intent="learning_progress",
            content="PROGRESS: Alice completed loops and functions lessons.",
            score=0.92,
        )

        selected = service._select_with_intent_caps(
            [profile_1, profile_2, profile_3, progress_1],
            top_k=3,
            query="How should tutoring responses be formatted for Alice?",
        )
        selected_intents = [item.memory.intent for item in selected]
        assert selected_intents == [
            "preference_stated",
            "preference_stated",
            "preference_stated",
        ]
    finally:
        service.close()


def test_service_progress_queries_cap_non_progress_buckets(tmp_path: Path) -> None:
    service = _service(tmp_path)
    try:
        ranked = [
            _retrieved(
                "profile_1",
                intent="preference_stated",
                content="PROFILE: Alice prefers concise answers.",
                score=0.99,
            ),
            _retrieved(
                "pattern_1",
                intent="inferred_learning_pattern",
                content="PATTERN: Alice repeats loop syntax questions.",
                score=0.98,
            ),
            _retrieved(
                "progress_1",
                intent="learning_progress",
                content="PROGRESS: Alice understands loops and functions.",
                score=0.97,
            ),
            _retrieved(
                "progress_2",
                intent="learning_progress",
                content="PROGRESS: Alice understands classes.",
                score=0.96,
            ),
            _retrieved(
                "progress_3",
                intent="learning_progress",
                content="PROGRESS: Alice understands project modules.",
                score=0.95,
            ),
            _retrieved(
                "progress_4",
                intent="learning_progress",
                content="PROGRESS: Alice understands dependency injection.",
                score=0.94,
            ),
            _retrieved(
                "progress_5",
                intent="learning_progress",
                content="PROGRESS: Alice understands testing strategy.",
                score=0.93,
            ),
        ]
        selected = service._select_with_intent_caps(
            ranked,
            top_k=5,
            query="What is Alice's current level for project architecture and what is next?",
        )
        assert len(selected) == 5
        assert all(item.memory.intent == "learning_progress" for item in selected)
    finally:
        service.close()


def test_service_progress_queries_surface_inferred_progress_when_available(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    try:
        ranked = [
            _retrieved(
                "progress_1",
                intent="learning_progress",
                content="PROGRESS: Alice understands loops and functions.",
                score=0.99,
            ),
            _retrieved(
                "progress_2",
                intent="learning_progress",
                content="PROGRESS: Alice understands classes.",
                score=0.98,
            ),
            _retrieved(
                "progress_3",
                intent="learning_progress",
                content="PROGRESS: Alice understands project modules.",
                score=0.97,
            ),
            _retrieved(
                "progress_4",
                intent="learning_progress",
                content="PROGRESS: Alice understands dependency injection.",
                score=0.96,
            ),
            _retrieved(
                "progress_5",
                intent="learning_progress",
                content="PROGRESS: Alice understands testing strategy.",
                score=0.95,
            ),
            _retrieved(
                "progress_inferred",
                intent="learning_progress",
                content="Inferred progress: Alice has progressed in project structure.",
                score=0.70,
                relationships=["inference_type:progress_accumulation", "inferred:true"],
            ),
        ]
        selected = service._select_with_intent_caps(
            ranked,
            top_k=5,
            query="What is Alice's current level for project architecture and what is next?",
        )
        selected_ids = [item.memory.memory_id for item in selected]
        assert "progress_inferred" in selected_ids
        assert selected[0].memory.memory_id == "progress_1"
    finally:
        service.close()


def test_service_adds_inference_provenance_for_inferred_memories(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    try:
        created_at = datetime.now(UTC) - timedelta(minutes=3)
        record = MemoryRecord(
            memory_id="prov_1",
            event_id="event-prov-1",
            content=(
                "Inferred learning pattern: alice repeatedly struggles with list indexing."
            ),
            summary="alice repeatedly struggles with list indexing",
            intent="inferred_learning_pattern",
            entities=["alice"],
            relationships=[
                "inferred:true",
                "inference_type:recurring_failure_pattern",
                "derived_from:mem_a",
                "derived_from:mem_b",
                "signature:alice|recurring_failure_pattern|list indexing",
                "supersedes:old_mem_1",
            ],
            raw_embedding=[0.1, 0.2],
            semantic_embedding=[0.1, 0.2],
            semantic_key="key-prov-1",
            created_at=created_at,
            updated_at=created_at,
            retrieval_count=2,
            avg_outcome_signal=0.3,
            storage_tier=StorageTier.PERSISTENT,
            latest_importance=0.91,
        )
        memory = service._as_memory(record, rank_position=1, rank_score=0.92)
        serialized = memory.model_dump(mode="json")
        provenance = dict(serialized["metadata"]).get("inference_provenance", {})
        assert provenance.get("is_inferred") is True
        assert provenance.get("inference_type") == "recurring_failure_pattern"
        assert provenance.get("derived_from_memory_ids") == ["mem_a", "mem_b"]
        assert provenance.get("supersedes_memory_ids") == ["old_mem_1"]
        assert provenance.get("signature") == (
            "alice|recurring_failure_pattern|list indexing"
        )
        assert provenance.get("when") == created_at.isoformat()
        assert "Repeated failure/error signals" in str(provenance.get("why"))
    finally:
        service.close()


def test_service_adds_derived_from_for_inferred_preference_provenance(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    try:
        created_at = datetime.now(UTC) - timedelta(minutes=2)
        record = MemoryRecord(
            memory_id="prov_pref_1",
            event_id="event-prov-pref-1",
            content=(
                "Inferred preference: alice responds better to concise explanations."
            ),
            summary="alice prefers concise explanations",
            intent="inferred_preference",
            entities=["alice"],
            relationships=[
                "inferred:true",
                "inference_type:feedback_preference_shift",
                "derived_from:assistant_mem_1",
                "derived_from:assistant_mem_2",
                "signature:alice|feedback_preference_shift|concise",
            ],
            raw_embedding=[0.1, 0.2],
            semantic_embedding=[0.1, 0.2],
            semantic_key="key-prov-pref-1",
            created_at=created_at,
            updated_at=created_at,
            retrieval_count=1,
            avg_outcome_signal=0.2,
            storage_tier=StorageTier.PERSISTENT,
            latest_importance=0.89,
        )
        memory = service._as_memory(record, rank_position=1, rank_score=0.88)
        provenance = dict(memory.model_dump(mode="json")["metadata"]).get(
            "inference_provenance",
            {},
        )
        assert provenance.get("inference_type") == "feedback_preference_shift"
        assert provenance.get("derived_from_memory_ids") == [
            "assistant_mem_1",
            "assistant_mem_2",
        ]
    finally:
        service.close()


def test_service_adds_inference_provenance_defaults_for_regular_memories(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    try:
        now = datetime.now(UTC)
        record = MemoryRecord(
            memory_id="regular_1",
            event_id="event-regular-1",
            content="Alice prefers short explanations.",
            summary="Alice prefers short explanations.",
            intent="preference_stated",
            entities=["alice"],
            relationships=[],
            raw_embedding=[0.1, 0.2],
            semantic_embedding=[0.1, 0.2],
            semantic_key="key-regular-1",
            created_at=now,
            updated_at=now,
            retrieval_count=1,
            avg_outcome_signal=0.0,
            storage_tier=StorageTier.PERSISTENT,
            latest_importance=0.75,
        )
        memory = service._as_memory(record, rank_position=1, rank_score=0.7)
        serialized = memory.model_dump(mode="json")
        provenance = dict(serialized["metadata"]).get("inference_provenance", {})
        assert provenance.get("is_inferred") is False
        assert provenance.get("why") is None
        assert provenance.get("when") is None
        assert provenance.get("inference_type") is None
        assert provenance.get("signature") is None
        assert provenance.get("derived_from_memory_ids") == []
        assert provenance.get("supersedes_memory_ids") == []
    finally:
        service.close()


def test_service_health_degraded_on_storage_failure(tmp_path: Path) -> None:
    service = _service(tmp_path)
    try:
        def failing_memory_count() -> int:
            msg = "storage down"
            raise RuntimeError(msg)

        service._engine.memory_count = failing_memory_count  # type: ignore[method-assign]
        health = service.health()
        assert health["status"] == "degraded"
        assert health["storage"] == "error"
    finally:
        service.close()
