"""create memories table

Revision ID: 20260221_0001
Revises:
Create Date: 2026-02-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260221_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "memories",
        sa.Column("memory_id", sa.String(length=64), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("intent", sa.String(length=128), nullable=False),
        sa.Column("entities_json", sa.Text(), nullable=False),
        sa.Column("relationships_json", sa.Text(), nullable=False),
        sa.Column("raw_embedding_json", sa.Text(), nullable=False),
        sa.Column("semantic_embedding_json", sa.Text(), nullable=False),
        sa.Column("semantic_key", sa.String(length=64), nullable=False),
        sa.Column("retrieval_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "avg_outcome_signal",
            sa.Float(),
            nullable=False,
            server_default="0.0",
        ),
        sa.Column("outcome_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("storage_tier", sa.String(length=16), nullable=False),
        sa.Column("latest_importance", sa.Float(), nullable=False),
        sa.Column(
            "is_compressed",
            sa.Boolean(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("original_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("memory_id"),
    )
    op.create_index("ix_memories_semantic_key", "memories", ["semantic_key"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_memories_semantic_key", table_name="memories")
    op.drop_table("memories")
