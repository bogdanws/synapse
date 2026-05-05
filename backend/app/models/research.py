"""Pydantic models for the research domain."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class JobStatus(StrEnum):
    PENDING = "pending"
    SCOUTING = "scouting"
    SYNTHESIZING = "synthesizing"
    CRITIQUING = "critiquing"
    COMPLETED = "completed"
    FAILED = "failed"


class Depth(StrEnum):
    SHALLOW = "shallow"
    STANDARD = "standard"
    DEEP = "deep"


class ResearchRequest(BaseModel):
    """Inbound request body for POST /api/research."""

    topic: str = Field(..., min_length=3, max_length=500)
    language: str = Field(default="en", min_length=2, max_length=8)
    depth: Depth = Depth.STANDARD


class ResearchJobResponse(BaseModel):
    """Job descriptor returned to the client."""

    id: UUID
    topic: str
    status: JobStatus
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SourceData(BaseModel):
    url: HttpUrl
    title: str
    content: str
    credibility: float = Field(ge=0.0, le=1.0)
    relevance: float = Field(ge=0.0, le=1.0)


class ReportSection(BaseModel):
    heading: str
    body: str
    citations: list[HttpUrl] = []
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class Report(BaseModel):
    id: UUID
    title: str
    summary: str
    sections: list[ReportSection]
    sources: list[SourceData]
    contradictions: list[str] = []
    follow_ups: list[str] = []


class VerifiedReport(BaseModel):
    report: Report
    confidence: dict[str, float] = Field(default_factory=dict)
    flags: list[str] = []
    annotations: list[str] = []
