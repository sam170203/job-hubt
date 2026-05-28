"""SQLAlchemy ORM models. Schema per spec §6."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_source_external"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255))
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    jd_text: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(255))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    role_tag: Mapped[str | None] = mapped_column(String(32))
    seniority_tag: Mapped[str | None] = mapped_column(String(32))
    tech_tags: Mapped[list[str] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="new")
    notes: Mapped[str | None] = mapped_column(Text)

    applications: Mapped[list[Application]] = relationship(back_populates="job")


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    applied_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    resume_variant: Mapped[str | None] = mapped_column(String(64))
    cover_note_path: Mapped[str | None] = mapped_column(Text)
    channel: Mapped[str | None] = mapped_column(String(32))

    job: Mapped[Job] = relationship(back_populates="applications")
    events: Mapped[list[Event]] = relationship(back_populates="application")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    happened_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    source: Mapped[str | None] = mapped_column(String(32))
    raw_text: Mapped[str | None] = mapped_column(Text)

    application: Mapped[Application] = relationship(back_populates="events")


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str | None] = mapped_column(String(255))
    company: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str | None] = mapped_column(String(255))
    x_handle: Mapped[str | None] = mapped_column(String(64))
    linkedin_url: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(String(255))
    last_touched_at: Mapped[datetime | None] = mapped_column(DateTime)
    notes: Mapped[str | None] = mapped_column(Text)


class GmailMessage(Base):
    __tablename__ = "gmail_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    msg_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    from_addr: Mapped[str | None] = mapped_column(String(255))
    subject: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime | None] = mapped_column(DateTime)
    job_id_match: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"))
    parsed_signal: Mapped[str | None] = mapped_column(String(32))


class StagingRaw(Base):
    __tablename__ = "staging_raw"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    promoted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
