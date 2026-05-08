"""SQLAlchemy ORM table definitions for the research domain.

The User table is managed by fastapi-users (app/auth/models.py) and is
referenced here only via a ForeignKey string to avoid a circular import.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import TIMESTAMP, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ResearchJob(Base):
    __tablename__ = "research_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), index=True
    )
    topic: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(server_default="en")
    depth: Mapped[str] = mapped_column(server_default="standard")
    # {"scout": "<model-id>", "scribe": "<model-id>", "critic": "<model-id>"}
    models: Mapped[dict[str, Any]] = mapped_column(JSONB)
    # When the caller supplies sub-questions from the preview screen we store them here and
    # skip Scout's decompose phase, so the run honours the user's approved plan exactly.
    sub_questions_override: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(server_default="pending", index=True)
    progress: Mapped[float] = mapped_column(server_default="0")
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    sources: Mapped[list[Source]] = relationship(back_populates="job", cascade="all, delete-orphan")
    report: Mapped[Report | None] = relationship(
        back_populates="job",
        uselist=False,
        cascade="all, delete-orphan",
    )
    follow_ups_as_parent: Mapped[list[FollowUp]] = relationship(
        foreign_keys="FollowUp.parent_job_id",
        back_populates="parent_job",
    )
    follow_ups_as_child: Mapped[list[FollowUp]] = relationship(
        foreign_keys="FollowUp.child_job_id",
        back_populates="child_job",
    )


class Source(Base):
    __tablename__ = "sources"
    __table_args__ = (
        # Explicit names required: both constraints share job_id as column_0,
        # so the default naming convention would generate the same name twice.
        UniqueConstraint("job_id", "short_id", name="uq_sources_job_id_short_id"),
        UniqueConstraint("job_id", "url", name="uq_sources_job_id_url"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_jobs.id", ondelete="CASCADE"), index=True
    )
    short_id: Mapped[str]  # "s1", "s2", ... unique within job
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    snippet: Mapped[str] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)
    credibility: Mapped[float]
    relevance: Mapped[float]

    job: Mapped[ResearchJob] = relationship(back_populates="sources")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_jobs.id", ondelete="CASCADE"), unique=True
    )
    title: Mapped[str] = mapped_column(Text)
    summary_md: Mapped[str] = mapped_column(Text)
    # Stores ScribeReport sections, contradictions, follow_ups as JSONB; validated
    # at the Pydantic layer before write and after read.
    body: Mapped[dict[str, Any]] = mapped_column(JSONB)
    model: Mapped[str]
    generated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))

    job: Mapped[ResearchJob] = relationship(back_populates="report")
    critic_annotation: Mapped[CriticAnnotation | None] = relationship(
        back_populates="report",
        uselist=False,
        cascade="all, delete-orphan",
    )


class CriticAnnotation(Base):
    __tablename__ = "critic_annotations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), unique=True
    )
    # Stores CriticAnnotations (section_confidence + claim_flags) as JSONB.
    body: Mapped[dict[str, Any]] = mapped_column(JSONB)
    overall_confidence: Mapped[float]
    model: Mapped[str]
    generated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))

    report: Mapped[Report] = relationship(back_populates="critic_annotation")


class FollowUp(Base):
    __tablename__ = "follow_ups"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    parent_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_jobs.id", ondelete="CASCADE"), index=True
    )
    child_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_jobs.id", ondelete="CASCADE"), index=True
    )
    question: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    parent_job: Mapped[ResearchJob] = relationship(
        foreign_keys=[parent_job_id],
        back_populates="follow_ups_as_parent",
    )
    child_job: Mapped[ResearchJob] = relationship(
        foreign_keys=[child_job_id],
        back_populates="follow_ups_as_child",
    )
