from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import jwt

from memory_engine.config import EngineConfig
from orbit import AsyncMemoryEngine, Config
from orbit_api.app import create_app
from orbit_api.config import ApiConfig

JWT_SECRET = "integration-secret"
JWT_ISSUER = "orbit-tests"
JWT_AUDIENCE = "orbit-tests-api"


def _build_app(tmp_path: Path):
    db_path = tmp_path / "orbit_api.db"
    api_config = ApiConfig(
        database_url=f"sqlite:///{db_path}",
        sqlite_fallback_path=str(db_path),
        free_events_per_day=100,
        free_queries_per_day=500,
        free_events_per_month=100,
        free_queries_per_month=500,
        jwt_secret=JWT_SECRET,
        jwt_issuer=JWT_ISSUER,
        jwt_audience=JWT_AUDIENCE,
    )
    engine_config = EngineConfig(
        sqlite_path=str(db_path),
        database_url=f"sqlite:///{db_path}",
        embedding_dim=32,
        persistent_confidence_prior=0.0,
        ephemeral_confidence_prior=0.0,
        ranker_min_training_samples=2,
        ranker_training_batch_size=2,
    )
    return create_app(api_config=api_config, engine_config=engine_config)


def _jwt_token(
    subject: str = "integration-user",
    *,
    scopes: list[str] | None = None,
    account_key: str | None = None,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
        "scopes": scopes or ["read", "write", "feedback"],
    }
    if account_key is not None:
        payload["account_key"] = account_key
    return str(jwt.encode(payload, JWT_SECRET, algorithm="HS256"))


def test_api_end_to_end_flow(tmp_path: Path) -> None:
    async def _run() -> None:
        app = _build_app(tmp_path)
        transport = httpx.ASGITransport(app=app)
        headers = {"Authorization": f"Bearer {_jwt_token()}"}

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            ingest = await client.post(
                "/v1/ingest",
                headers=headers,
                json={
                    "content": "Alice is learning loops and likes short explanations",
                    "event_type": "user_question",
                    "entity_id": "alice",
                    "metadata": {"topic": "loops"},
                },
            )
            assert ingest.status_code == 201
            assert ingest.json()["stored"] is True
            memory_id = ingest.json()["memory_id"]
            assert "100" in ingest.headers["X-RateLimit-Limit"]

            retrieve = await client.get(
                "/v1/retrieve",
                headers=headers,
                params={
                    "query": "What does Alice need help with?",
                    "entity_id": "alice",
                    "limit": 5,
                },
            )
            assert retrieve.status_code == 200
            body = retrieve.json()
            assert body["total_candidates"] >= 1
            assert len(body["memories"]) >= 1
            assert "500" in retrieve.headers["X-RateLimit-Limit"]

            feedback = await client.post(
                "/v1/feedback",
                headers=headers,
                json={"memory_id": memory_id, "helpful": True, "outcome_value": 1.0},
            )
            assert feedback.status_code == 200
            assert feedback.json()["recorded"] is True

            status = await client.get("/v1/status", headers=headers)
            assert status.status_code == 200
            assert status.json()["connected"] is True

            health = await client.get("/v1/health")
            assert health.status_code == 200
            assert health.json()["status"] == "ok"

            metrics = await client.get("/v1/metrics")
            assert metrics.status_code == 200
            assert "orbit_ingest_requests_total" in metrics.text
            assert 'orbit_http_responses_total{status_code="201"}' in metrics.text
            assert 'orbit_http_responses_total{status_code="200"}' in metrics.text

    asyncio.run(_run())


def test_async_sdk_against_fastapi_app(tmp_path: Path) -> None:
    async def _run() -> None:
        app = _build_app(tmp_path)
        transport = httpx.ASGITransport(app=app)

        engine = AsyncMemoryEngine(
            config=Config(
                api_key=_jwt_token(),
                base_url="http://testserver",
                timeout_seconds=10.0,
                max_retries=0,
            ),
            transport=transport,
        )
        try:
            ingest_response = await engine.ingest(
                content="Alice completed lesson 10 and now asks architecture questions",
                event_type="learning_progress",
                entity_id="alice",
            )
            assert ingest_response.stored is True

            retrieve_response = await engine.retrieve(
                query="What should I know about alice?",
                entity_id="alice",
                limit=5,
            )
            assert retrieve_response.total_candidates >= 1
            assert retrieve_response.memories
        finally:
            await engine.aclose()

    asyncio.run(_run())


def test_api_exposes_fact_inference_and_conflict_metadata(tmp_path: Path) -> None:
    async def _run() -> None:
        app = _build_app(tmp_path)
        transport = httpx.ASGITransport(app=app)
        headers = {"Authorization": f"Bearer {_jwt_token()}"}

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            first = await client.post(
                "/v1/ingest",
                headers=headers,
                json={
                    "content": "I am allergic to pineapple.",
                    "event_type": "user_question",
                    "entity_id": "alice",
                },
            )
            assert first.status_code == 201

            second = await client.post(
                "/v1/ingest",
                headers=headers,
                json={
                    "content": "I am not allergic to pineapple anymore.",
                    "event_type": "user_question",
                    "entity_id": "alice",
                },
            )
            assert second.status_code == 201

            listed = await client.get(
                "/v1/memories",
                headers=headers,
                params={"limit": 50},
            )
            assert listed.status_code == 200
            data = listed.json()["data"]
            allergy_facts = [
                item
                for item in data
                if (item["metadata"].get("fact_inference") or {}).get("fact_key")
                == "allergy:pineapple"
            ]
            assert len(allergy_facts) >= 2

            conflict_guards = [
                item
                for item in data
                if item["metadata"].get("intent") == "inferred_user_fact_conflict"
            ]
            assert len(conflict_guards) >= 1
            guard = conflict_guards[0]
            provenance = guard["metadata"]["inference_provenance"]
            assert provenance["clarification_required"] is True
            assert len(provenance["conflicts_with_memory_ids"]) >= 1
            assert (
                guard["metadata"]["fact_inference"]["clarification_required"] is True
            )

    asyncio.run(_run())


def test_status_metadata_summary_reflects_user_fact_conflicts(tmp_path: Path) -> None:
    async def _run() -> None:
        app = _build_app(tmp_path)
        transport = httpx.ASGITransport(app=app)
        headers = {"Authorization": f"Bearer {_jwt_token()}"}

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            await client.post(
                "/v1/ingest",
                headers=headers,
                json={
                    "content": "I am allergic to pineapple.",
                    "event_type": "user_question",
                    "entity_id": "alice",
                },
            )
            await client.post(
                "/v1/ingest",
                headers=headers,
                json={
                    "content": "I am not allergic to pineapple anymore.",
                    "event_type": "user_question",
                    "entity_id": "alice",
                },
            )

            status = await client.get("/v1/status", headers=headers)
            assert status.status_code == 200
            summary = status.json()["metadata_summary"]
            assert summary["total_inferred_facts"] >= 2
            assert summary["contested_facts"] >= 1
            assert summary["conflict_guards"] >= 1
            assert summary["contested_ratio"] > 0.0
            assert "fact_family_coverage" in summary
            assert "fact_family_counts" in summary
            assert "fact_conflict_count" in summary
            assert "superseded_fact_references" in summary
            assert "mutable_numeric_facts" in summary

    asyncio.run(_run())


def test_tenant_metrics_endpoint_is_account_scoped(tmp_path: Path) -> None:
    async def _run() -> None:
        app = _build_app(tmp_path)
        transport = httpx.ASGITransport(app=app)
        headers_a = {
            "Authorization": f"Bearer {_jwt_token(subject='user-a', account_key='acct_a')}"
        }
        headers_b = {
            "Authorization": f"Bearer {_jwt_token(subject='user-b', account_key='acct_b')}"
        }

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            ingest_a = await client.post(
                "/v1/ingest",
                headers=headers_a,
                json={
                    "content": "Tenant A profile note",
                    "event_type": "user_question",
                    "entity_id": "alice",
                },
            )
            assert ingest_a.status_code == 201

            retrieve_a = await client.get(
                "/v1/retrieve",
                headers=headers_a,
                params={
                    "query": "what should i know about alice?",
                    "entity_id": "alice",
                    "limit": 5,
                },
            )
            assert retrieve_a.status_code == 200

            ingest_b = await client.post(
                "/v1/ingest",
                headers=headers_b,
                json={
                    "content": "Tenant B private note",
                    "event_type": "user_question",
                    "entity_id": "bob",
                },
            )
            assert ingest_b.status_code == 201

            tenant_metrics_a = await client.get("/v1/tenant-metrics", headers=headers_a)
            assert tenant_metrics_a.status_code == 200
            tenant_metrics_a_json = tenant_metrics_a.json()
            assert tenant_metrics_a_json["ingest"]["used"] == 1
            assert tenant_metrics_a_json["retrieve"]["used"] == 1

            tenant_metrics_b = await client.get("/v1/tenant-metrics", headers=headers_b)
            assert tenant_metrics_b.status_code == 200
            tenant_metrics_b_json = tenant_metrics_b.json()
            assert tenant_metrics_b_json["ingest"]["used"] == 1
            assert tenant_metrics_b_json["retrieve"]["used"] == 0

            memory_quality_a = await client.get(
                "/v1/dashboard/memory-quality",
                headers=headers_a,
            )
            assert memory_quality_a.status_code == 200
            quality_a_json = memory_quality_a.json()
            assert quality_a_json["window_7d"]["total_inferred_facts"] >= 0
            assert quality_a_json["window_30d"]["total_inferred_facts"] >= 0

            memory_quality_b = await client.get(
                "/v1/dashboard/memory-quality",
                headers=headers_b,
            )
            assert memory_quality_b.status_code == 200
            quality_b_json = memory_quality_b.json()
            assert quality_b_json["window_7d"]["total_inferred_facts"] >= 0
            assert quality_b_json["window_30d"]["total_inferred_facts"] >= 0

    asyncio.run(_run())


def test_api_retrieves_atomic_facts_from_long_ingest_without_storage_blowup(
    tmp_path: Path,
) -> None:
    async def _run() -> None:
        db_path = tmp_path / "long_fact_capture.db"
        api_config = ApiConfig(
            database_url=f"sqlite:///{db_path}",
            sqlite_fallback_path=str(db_path),
            free_events_per_day=100,
            free_queries_per_day=500,
            free_events_per_month=100,
            free_queries_per_month=500,
            jwt_secret=JWT_SECRET,
            jwt_issuer=JWT_ISSUER,
            jwt_audience=JWT_AUDIENCE,
            max_ingest_content_chars=4000,
        )
        engine_config = EngineConfig(
            sqlite_path=str(db_path),
            database_url=f"sqlite:///{db_path}",
            embedding_dim=32,
            max_content_chars=180,
            assistant_max_content_chars=180,
            persistent_confidence_prior=0.0,
            ephemeral_confidence_prior=0.0,
            ranker_min_training_samples=2,
            ranker_training_batch_size=2,
        )
        app = create_app(api_config=api_config, engine_config=engine_config)
        transport = httpx.ASGITransport(app=app)
        headers = {"Authorization": f"Bearer {_jwt_token(account_key='acct-long')}"}

        filler = " ".join(f"filler{i}" for i in range(220))
        long_prompt = (
            f"{filler}. "
            "I am allergic to pineapple. "
            "I am currently at 58 and I need to be at 64 by end of month for army medical interview."
        )

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            ingest = await client.post(
                "/v1/ingest",
                headers=headers,
                json={
                    "content": long_prompt,
                    "event_type": "user_question",
                    "entity_id": "alice",
                },
            )
            assert ingest.status_code == 201

            memories = await client.get("/v1/memories", headers=headers, params={"limit": 50})
            assert memories.status_code == 200
            source = next(
                item
                for item in memories.json()["data"]
                if item["memory_id"] == ingest.json()["memory_id"]
            )
            assert "truncated" in source["content"].lower()
            assert len(source["content"]) < len(long_prompt)

            retrieve = await client.get(
                "/v1/retrieve",
                headers=headers,
                params={
                    "query": "What weight am I currently at, what target do I need, and why?",
                    "entity_id": "alice",
                    "limit": 5,
                },
            )
            assert retrieve.status_code == 200
            returned = retrieve.json()["memories"]
            returned_text = " ".join(item["content"].lower() for item in returned)
            assert "58" in returned_text
            assert "64" in returned_text
            assert "army medical interview" in returned_text

            allergy_retrieve = await client.get(
                "/v1/retrieve",
                headers=headers,
                params={
                    "query": "What allergy should I avoid?",
                    "entity_id": "alice",
                    "limit": 5,
                },
            )
            assert allergy_retrieve.status_code == 200
            allergy_text = " ".join(
                item["content"].lower()
                for item in allergy_retrieve.json()["memories"]
            )
            assert "allergic to pineapple" in allergy_text

            status = await client.get("/v1/status", headers=headers)
            assert status.status_code == 200
            metadata_summary = status.json()["metadata_summary"]
            assert metadata_summary["fact_family_coverage"] >= 3
            assert metadata_summary["fact_family_counts"].get("allergy", 0) >= 1
            assert metadata_summary["fact_family_counts"].get("weight_current", 0) >= 1
            assert metadata_summary["fact_family_counts"].get("weight_target", 0) >= 1

    asyncio.run(_run())


def test_api_enforces_cross_tenant_memory_isolation(tmp_path: Path) -> None:
    async def _run() -> None:
        app = _build_app(tmp_path)
        transport = httpx.ASGITransport(app=app)
        headers_a = {"Authorization": f"Bearer {_jwt_token(subject='tenant-a')}"}
        headers_b = {"Authorization": f"Bearer {_jwt_token(subject='tenant-b')}"}

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            ingest_a = await client.post(
                "/v1/ingest",
                headers=headers_a,
                json={
                    "content": "Tenant A private memory: prefers Python loops examples.",
                    "event_type": "user_profile",
                    "entity_id": "shared-user",
                },
            )
            assert ingest_a.status_code == 201
            memory_id_a = str(ingest_a.json()["memory_id"])

            ingest_b = await client.post(
                "/v1/ingest",
                headers=headers_b,
                json={
                    "content": "Tenant B private memory: prefers JavaScript examples.",
                    "event_type": "user_profile",
                    "entity_id": "shared-user",
                },
            )
            assert ingest_b.status_code == 201
            memory_id_b = str(ingest_b.json()["memory_id"])

            retrieve_a = await client.get(
                "/v1/retrieve",
                headers=headers_a,
                params={
                    "query": "What do I know about shared-user preferences?",
                    "entity_id": "shared-user",
                    "limit": 5,
                },
            )
            assert retrieve_a.status_code == 200
            memories_a = retrieve_a.json()["memories"]
            assert memories_a
            ids_a = {str(item["memory_id"]) for item in memories_a}
            contents_a = {str(item["content"]) for item in memories_a}
            assert memory_id_a in ids_a
            assert memory_id_b not in ids_a
            assert all("Tenant B private memory" not in content for content in contents_a)

            retrieve_b = await client.get(
                "/v1/retrieve",
                headers=headers_b,
                params={
                    "query": "What do I know about shared-user preferences?",
                    "entity_id": "shared-user",
                    "limit": 5,
                },
            )
            assert retrieve_b.status_code == 200
            memories_b = retrieve_b.json()["memories"]
            assert memories_b
            ids_b = {str(item["memory_id"]) for item in memories_b}
            contents_b = {str(item["content"]) for item in memories_b}
            assert memory_id_b in ids_b
            assert memory_id_a not in ids_b
            assert all("Tenant A private memory" not in content for content in contents_b)

            list_a = await client.get("/v1/memories", headers=headers_a, params={"limit": 20})
            assert list_a.status_code == 200
            listed_a = {str(item["memory_id"]) for item in list_a.json()["data"]}
            assert memory_id_a in listed_a
            assert memory_id_b not in listed_a

            forbidden_feedback = await client.post(
                "/v1/feedback",
                headers=headers_b,
                json={"memory_id": memory_id_a, "helpful": True, "outcome_value": 1.0},
            )
            assert forbidden_feedback.status_code == 404

    asyncio.run(_run())


def test_api_dashboard_keys_issue_revoke_and_authenticate(tmp_path: Path) -> None:
    async def _run() -> None:
        app = _build_app(tmp_path)
        transport = httpx.ASGITransport(app=app)
        jwt_headers = {
            "Authorization": f"Bearer {_jwt_token(subject='dashboard-user')}",
        }

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            issue = await client.post(
                "/v1/dashboard/keys",
                headers=jwt_headers,
                json={
                    "name": "sdk-prod",
                    "scopes": ["read", "write", "read"],
                },
            )
            assert issue.status_code == 201
            issue_body = issue.json()
            assert issue_body["key"].startswith("orbit_pk_")
            assert issue_body["status"] == "active"
            assert issue_body["scopes"] == ["read", "write"]
            key_id = str(issue_body["key_id"])
            plaintext_key = str(issue_body["key"])

            list_before = await client.get("/v1/dashboard/keys", headers=jwt_headers)
            assert list_before.status_code == 200
            assert len(list_before.json()["data"]) == 1
            assert list_before.json()["data"][0]["key_id"] == key_id
            assert list_before.json()["has_more"] is False
            assert list_before.json()["cursor"] is None

            api_key_headers = {"Authorization": f"Bearer {plaintext_key}"}
            ingest = await client.post(
                "/v1/ingest",
                headers=api_key_headers,
                json={
                    "content": "Orbit API key auth memory",
                    "event_type": "user_profile",
                    "entity_id": "dashboard-user",
                },
            )
            assert ingest.status_code == 201

            list_after = await client.get("/v1/dashboard/keys", headers=jwt_headers)
            assert list_after.status_code == 200
            assert list_after.json()["data"][0]["last_used_at"] is not None
            assert list_after.json()["data"][0]["last_used_source"] == "POST /v1/ingest"

            revoke = await client.post(
                f"/v1/dashboard/keys/{key_id}/revoke",
                headers=jwt_headers,
            )
            assert revoke.status_code == 200
            assert revoke.json()["revoked"] is True

            rejected = await client.get("/v1/status", headers=api_key_headers)
            assert rejected.status_code == 401

    asyncio.run(_run())


def test_api_dashboard_keys_rotate_and_paginate(tmp_path: Path) -> None:
    async def _run() -> None:
        app = _build_app(tmp_path)
        transport = httpx.ASGITransport(app=app)
        jwt_headers = {
            "Authorization": f"Bearer {_jwt_token(subject='rotate-user')}",
        }

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            issue_ids: list[str] = []
            issue_keys: list[str] = []
            for idx in range(3):
                issued = await client.post(
                    "/v1/dashboard/keys",
                    headers=jwt_headers,
                    json={"name": f"k{idx}", "scopes": ["read", "write", "feedback"]},
                )
                assert issued.status_code == 201
                body = issued.json()
                issue_ids.append(str(body["key_id"]))
                issue_keys.append(str(body["key"]))

            first_page = await client.get(
                "/v1/dashboard/keys",
                headers=jwt_headers,
                params={"limit": 2},
            )
            assert first_page.status_code == 200
            first_body = first_page.json()
            assert len(first_body["data"]) == 2
            assert first_body["has_more"] is True
            assert first_body["cursor"] is not None

            second_page = await client.get(
                "/v1/dashboard/keys",
                headers=jwt_headers,
                params={"limit": 2, "cursor": first_body["cursor"]},
            )
            assert second_page.status_code == 200
            second_body = second_page.json()
            assert len(second_body["data"]) == 1
            assert second_body["has_more"] is False

            rotate = await client.post(
                f"/v1/dashboard/keys/{issue_ids[0]}/rotate",
                headers=jwt_headers,
                json={"name": "k0-rotated", "scopes": ["read", "write", "feedback"]},
            )
            assert rotate.status_code == 201
            rotate_body = rotate.json()
            assert rotate_body["revoked_key_id"] == issue_ids[0]
            assert rotate_body["new_key"]["name"] == "k0-rotated"
            assert str(rotate_body["new_key"]["key"]).startswith("orbit_pk_")

            old_key_headers = {"Authorization": f"Bearer {issue_keys[0]}"}
            old_key_rejected = await client.get("/v1/status", headers=old_key_headers)
            assert old_key_rejected.status_code == 401

            new_key_headers = {
                "Authorization": f"Bearer {rotate_body['new_key']['key']}",
            }
            new_key_status = await client.get("/v1/status", headers=new_key_headers)
            assert new_key_status.status_code == 200

    asyncio.run(_run())


def test_api_dashboard_keys_enforce_plan_key_cap(tmp_path: Path) -> None:
    async def _run() -> None:
        db_path = tmp_path / "orbit_api_key_cap.db"
        api_config = ApiConfig(
            database_url=f"sqlite:///{db_path}",
            sqlite_fallback_path=str(db_path),
            free_events_per_month=100,
            free_queries_per_month=100,
            free_api_keys=1,
            jwt_secret=JWT_SECRET,
            jwt_issuer=JWT_ISSUER,
            jwt_audience=JWT_AUDIENCE,
        )
        engine_config = EngineConfig(
            sqlite_path=str(db_path),
            database_url=f"sqlite:///{db_path}",
            embedding_dim=32,
            persistent_confidence_prior=0.0,
            ephemeral_confidence_prior=0.0,
        )
        app = create_app(api_config=api_config, engine_config=engine_config)
        transport = httpx.ASGITransport(app=app)
        jwt_headers = {
            "Authorization": f"Bearer {_jwt_token(subject='cap-user')}",
        }

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            first = await client.post(
                "/v1/dashboard/keys",
                headers=jwt_headers,
                json={"name": "cap-1", "scopes": ["read", "write"]},
            )
            assert first.status_code == 201

            second = await client.post(
                "/v1/dashboard/keys",
                headers=jwt_headers,
                json={"name": "cap-2", "scopes": ["read", "write"]},
            )
            assert second.status_code == 429
            detail = second.json()["detail"]
            assert detail["error_code"] == "quota_api_keys_exceeded"

    asyncio.run(_run())


def test_api_dashboard_pilot_pro_request_persists_in_status(tmp_path: Path) -> None:
    async def _run() -> None:
        app = _build_app(tmp_path)
        transport = httpx.ASGITransport(app=app)
        jwt_headers = {
            "Authorization": f"Bearer {_jwt_token(subject='pilot-user')}",
        }

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            requested = await client.post(
                "/v1/dashboard/pilot-pro/request",
                headers=jwt_headers,
            )
            assert requested.status_code == 200
            requested_body = requested.json()
            assert requested_body["created"] is True
            assert requested_body["email_sent"] is False
            assert requested_body["request"]["requested"] is True
            assert requested_body["request"]["status"] == "requested"

            requested_again = await client.post(
                "/v1/dashboard/pilot-pro/request",
                headers=jwt_headers,
            )
            assert requested_again.status_code == 200
            assert requested_again.json()["created"] is False

            status = await client.get("/v1/status", headers=jwt_headers)
            assert status.status_code == 200
            status_body = status.json()
            assert status_body["pilot_pro_request"]["requested"] is True
            assert status_body["pilot_pro_request"]["status"] == "requested"

    asyncio.run(_run())


def test_api_dashboard_account_claim_mapping_shares_account(tmp_path: Path) -> None:
    async def _run() -> None:
        app = _build_app(tmp_path)
        transport = httpx.ASGITransport(app=app)
        headers_a = {
            "Authorization": (
                f"Bearer {_jwt_token(subject='user-a', account_key='acct_shared')}"
            ),
        }
        headers_b = {
            "Authorization": (
                f"Bearer {_jwt_token(subject='user-b', account_key='acct_shared')}"
            ),
        }

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            issue = await client.post(
                "/v1/dashboard/keys",
                headers=headers_a,
                json={"name": "shared-account-key", "scopes": ["read", "write"]},
            )
            assert issue.status_code == 201
            key_id = str(issue.json()["key_id"])

            listed = await client.get("/v1/dashboard/keys", headers=headers_b)
            assert listed.status_code == 200
            ids = {str(item["key_id"]) for item in listed.json()["data"]}
            assert key_id in ids

    asyncio.run(_run())
