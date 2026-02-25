"""create pilot pro request state table

Revision ID: 20260225_0007
Revises: 20260225_0006
Create Date: 2026-02-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260225_0007"
down_revision = "20260225_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "api_pilot_pro_requests" in existing_tables:
        return

    op.create_table(
        "api_pilot_pro_requests",
        sa.Column("account_key", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("requested_by_subject", sa.String(length=255), nullable=True),
        sa.Column("requested_by_email", sa.String(length=320), nullable=True),
        sa.Column("requested_by_name", sa.String(length=255), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("email_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_delivery_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("account_key"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "api_pilot_pro_requests" in existing_tables:
        op.drop_table("api_pilot_pro_requests")
