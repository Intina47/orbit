"""create api usage and idempotency tables

Revision ID: 20260223_0002
Revises: 20260221_0001
Create Date: 2026-02-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260223_0002"
down_revision = "20260221_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_account_usage",
        sa.Column("account_key", sa.String(length=128), nullable=False),
        sa.Column("day_bucket", sa.Date(), nullable=False),
        sa.Column("month_year", sa.Integer(), nullable=False),
        sa.Column("month_value", sa.Integer(), nullable=False),
        sa.Column("events_today", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("queries_today", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("events_month", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("queries_month", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("account_key"),
    )

    op.create_table(
        "api_idempotency",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_key", sa.String(length=128), nullable=False),
        sa.Column("operation", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_json", sa.Text(), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_key",
            "operation",
            "idempotency_key",
            name="uq_api_idempotency_scope",
        ),
    )
    op.create_index(
        "ix_api_idempotency_account_key", "api_idempotency", ["account_key"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_api_idempotency_account_key", table_name="api_idempotency")
    op.drop_table("api_idempotency")
    op.drop_table("api_account_usage")
