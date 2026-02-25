"""extend dashboard user profile metadata for oauth providers

Revision ID: 20260225_0006
Revises: 20260224_0005
Create Date: 2026-02-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260225_0006"
down_revision = "20260224_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {
        column["name"] for column in inspector.get_columns("api_dashboard_users")
    }

    if "auth_provider" not in columns:
        op.add_column(
            "api_dashboard_users",
            sa.Column("auth_provider", sa.String(length=64), nullable=True),
        )
    if "display_name" not in columns:
        op.add_column(
            "api_dashboard_users",
            sa.Column("display_name", sa.String(length=255), nullable=True),
        )
    if "avatar_url" not in columns:
        op.add_column(
            "api_dashboard_users",
            sa.Column("avatar_url", sa.String(length=1024), nullable=True),
        )
    if "last_login_at" not in columns:
        op.add_column(
            "api_dashboard_users",
            sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {
        column["name"] for column in inspector.get_columns("api_dashboard_users")
    }

    with op.batch_alter_table("api_dashboard_users") as batch_op:
        if "last_login_at" in columns:
            batch_op.drop_column("last_login_at")
        if "avatar_url" in columns:
            batch_op.drop_column("avatar_url")
        if "display_name" in columns:
            batch_op.drop_column("display_name")
        if "auth_provider" in columns:
            batch_op.drop_column("auth_provider")
