"""add account_key column to memories for tenant isolation

Revision ID: 20260224_0003
Revises: 20260223_0002
Create Date: 2026-02-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260224_0003"
down_revision = "20260223_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("memories")}
    if "account_key" not in columns:
        op.add_column(
            "memories",
            sa.Column(
                "account_key",
                sa.String(length=128),
                nullable=False,
                server_default="default",
            ),
        )
        op.execute(
            sa.text(
                "UPDATE memories SET account_key = 'default' "
                "WHERE account_key IS NULL OR account_key = ''"
            )
        )
    indexes = {index["name"] for index in inspector.get_indexes("memories")}
    if "ix_memories_account_key" not in indexes:
        op.create_index(
            "ix_memories_account_key",
            "memories",
            ["account_key"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes("memories")}
    if "ix_memories_account_key" in indexes:
        op.drop_index("ix_memories_account_key", table_name="memories")
    columns = {column["name"] for column in inspector.get_columns("memories")}
    if "account_key" not in columns:
        return
    with op.batch_alter_table("memories") as batch_op:
        batch_op.drop_column("account_key")
