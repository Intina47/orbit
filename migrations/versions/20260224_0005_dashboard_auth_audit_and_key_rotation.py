"""add dashboard auth mapping, audit logs, and api key usage source

Revision ID: 20260224_0005
Revises: 20260224_0004
Create Date: 2026-02-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260224_0005"
down_revision = "20260224_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    api_keys_columns = {column["name"] for column in inspector.get_columns("api_keys")}
    if "last_used_source" not in api_keys_columns:
        op.add_column(
            "api_keys",
            sa.Column("last_used_source", sa.String(length=128), nullable=True),
        )

    tables = set(inspector.get_table_names())
    if "api_dashboard_users" not in tables:
        op.create_table(
            "api_dashboard_users",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("account_key", sa.String(length=128), nullable=False),
            sa.Column("auth_issuer", sa.String(length=255), nullable=False),
            sa.Column("auth_subject", sa.String(length=255), nullable=False),
            sa.Column("email", sa.String(length=320), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "auth_issuer",
                "auth_subject",
                name="uq_api_dashboard_users_auth_identity",
            ),
        )
        op.create_index(
            "ix_api_dashboard_users_account_key",
            "api_dashboard_users",
            ["account_key"],
            unique=False,
        )

    if "api_audit_logs" not in tables:
        op.create_table(
            "api_audit_logs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("account_key", sa.String(length=128), nullable=False),
            sa.Column("actor_subject", sa.String(length=255), nullable=False),
            sa.Column("actor_type", sa.String(length=32), nullable=False),
            sa.Column("action", sa.String(length=64), nullable=False),
            sa.Column("target_type", sa.String(length=32), nullable=False),
            sa.Column("target_id", sa.String(length=128), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_api_audit_logs_account_key",
            "api_audit_logs",
            ["account_key"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "api_audit_logs" in tables:
        indexes = {index["name"] for index in inspector.get_indexes("api_audit_logs")}
        if "ix_api_audit_logs_account_key" in indexes:
            op.drop_index("ix_api_audit_logs_account_key", table_name="api_audit_logs")
        op.drop_table("api_audit_logs")

    if "api_dashboard_users" in tables:
        indexes = {
            index["name"] for index in inspector.get_indexes("api_dashboard_users")
        }
        if "ix_api_dashboard_users_account_key" in indexes:
            op.drop_index(
                "ix_api_dashboard_users_account_key",
                table_name="api_dashboard_users",
            )
        op.drop_table("api_dashboard_users")

    api_keys_columns = {column["name"] for column in inspector.get_columns("api_keys")}
    if "last_used_source" in api_keys_columns:
        with op.batch_alter_table("api_keys") as batch_op:
            batch_op.drop_column("last_used_source")
