from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class MemoryRow(Base):
    __tablename__ = "memories"

    account_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    memory_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str] = mapped_column(String(128), nullable=False)
    entities_json: Mapped[str] = mapped_column(Text, nullable=False)
    relationships_json: Mapped[str] = mapped_column(Text, nullable=False)
    raw_embedding_json: Mapped[str] = mapped_column(Text, nullable=False)
    semantic_embedding_json: Mapped[str] = mapped_column(Text, nullable=False)
    semantic_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    retrieval_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_outcome_signal: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    outcome_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    storage_tier: Mapped[str] = mapped_column(String(16), nullable=False)
    latest_importance: Mapped[float] = mapped_column(Float, nullable=False)
    is_compressed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    original_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class ApiAccountUsageRow(Base):
    __tablename__ = "api_account_usage"

    account_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    day_bucket: Mapped[date] = mapped_column(Date, nullable=False)
    month_year: Mapped[int] = mapped_column(Integer, nullable=False)
    month_value: Mapped[int] = mapped_column(Integer, nullable=False)
    events_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    queries_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    events_month: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    queries_month: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class ApiIdempotencyRow(Base):
    __tablename__ = "api_idempotency"
    __table_args__ = (
        UniqueConstraint(
            "account_key",
            "operation",
            "idempotency_key",
            name="uq_api_idempotency_scope",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    operation: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class ApiKeyRow(Base):
    __tablename__ = "api_keys"
    __table_args__ = (
        UniqueConstraint("key_prefix", name="uq_api_keys_key_prefix"),
    )

    key_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    secret_salt: Mapped[str] = mapped_column(String(64), nullable=False)
    secret_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    hash_iterations: Mapped[int] = mapped_column(Integer, nullable=False)
    scopes_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_used_source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ApiDashboardUserRow(Base):
    __tablename__ = "api_dashboard_users"
    __table_args__ = (
        UniqueConstraint(
            "auth_issuer",
            "auth_subject",
            name="uq_api_dashboard_users_auth_identity",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    auth_issuer: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class ApiAuditLogRow(Base):
    __tablename__ = "api_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    actor_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class ApiPilotProRequestRow(Base):
    __tablename__ = "api_pilot_pro_requests"

    account_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="requested")
    requested_by_subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    requested_by_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    requested_by_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    email_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    email_last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    email_delivery_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


def initialize_database(database_url: str) -> sessionmaker[Session]:
    connect_args = (
        {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    )
    engine = create_engine(
        database_url,
        future=True,
        pool_pre_ping=True,
        connect_args=connect_args,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def initialize_sqlite_db(path: str) -> sessionmaker[Session]:
    return initialize_database(f"sqlite:///{path}")
