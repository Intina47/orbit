from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class MemoryRow(Base):
    __tablename__ = "memories"

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
