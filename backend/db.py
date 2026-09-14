import os
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def now():
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    company: Mapped[str] = mapped_column(String(300), index=True)
    title: Mapped[str] = mapped_column(String(500))
    company_key: Mapped[str] = mapped_column(String(300), index=True)
    title_key: Mapped[str] = mapped_column(String(500), index=True)
    apply_key: Mapped[str] = mapped_column(Text, index=True)
    data: Mapped[dict] = mapped_column(JSON)
    analysis: Mapped[dict] = mapped_column(JSON, default=dict)
    ranking: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="new", index=True)
    preparation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SourceRecord(Base):
    __tablename__ = "source_records"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_source_external"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    source: Mapped[str] = mapped_column(String(200))
    external_id: Mapped[str] = mapped_column(String(500))
    source_url: Mapped[str] = mapped_column(Text)
    raw: Mapped[dict] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64))
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Snapshot(Base):
    __tablename__ = "snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_record_id: Mapped[int] = mapped_column(ForeignKey("source_records.id"), index=True)
    raw: Mapped[dict] = mapped_column(JSON)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


class StatusEvent(Base):
    __tablename__ = "status_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    previous: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30))
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Feedback(Base):
    __tablename__ = "feedback"
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), primary_key=True)
    outcome: Mapped[str] = mapped_column(String(30))
    features: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class IngestRun(Base):
    __tablename__ = "ingest_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(200), index=True)
    status: Mapped[str] = mapped_column(String(30))
    discovered: Mapped[int] = mapped_column(Integer, default=0)
    deduplicated: Mapped[int] = mapped_column(Integer, default=0)
    ranked: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(Text, default="")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


def make_engine(url=None):
    url = url or os.getenv("DATABASE_URL", "sqlite:///./jobs.db")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return create_engine(
        url, pool_pre_ping=True, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {}
    )


def session_factory(engine):
    return sessionmaker(engine, expire_on_commit=False)
