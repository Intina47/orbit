from __future__ import annotations

import json
from pathlib import Path

from memory_engine.storage.db import ApiKeyRow, MemoryRow, initialize_sqlite_db


def test_sqlalchemy_db_initialization_and_insert(tmp_path: Path) -> None:
    session_factory = initialize_sqlite_db(str(tmp_path / "sqlalchemy.db"))
    with session_factory() as session:
        row = MemoryRow(
            account_key="acct_test",
            memory_id="m1",
            event_id="e1",
            content="content",
            summary="summary",
            intent="interaction",
            entities_json=json.dumps(["user_1"]),
            relationships_json=json.dumps(["user_1->repo_1"]),
            raw_embedding_json=json.dumps([0.1, 0.2]),
            semantic_embedding_json=json.dumps([0.2, 0.3]),
            semantic_key="key_1",
            retrieval_count=0,
            avg_outcome_signal=0.0,
            outcome_count=0,
            storage_tier="persistent",
            latest_importance=0.8,
            is_compressed=False,
            original_count=1,
        )
        session.add(row)
        session.commit()
        saved = session.get(MemoryRow, "m1")
        assert saved is not None
        assert saved.intent == "interaction"

        key_row = ApiKeyRow(
            key_id="9d801f73-b6f6-4a43-80fd-6a7a7b3fbab7",
            account_key="acct_test",
            name="sdk-key",
            key_prefix="orbit_pk_abc123abc123",
            secret_salt="00" * 16,
            secret_hash="11" * 32,
            hash_iterations=1,
            scopes_json=json.dumps(["read"]),
            status="active",
        )
        session.add(key_row)
        session.commit()
        saved_key = session.get(ApiKeyRow, "9d801f73-b6f6-4a43-80fd-6a7a7b3fbab7")
        assert saved_key is not None
        assert saved_key.status == "active"
