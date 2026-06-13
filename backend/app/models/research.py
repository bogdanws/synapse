"""Pydantic models for the research domain.

These are the canonical API/agent boundary types.
The matching SQLAlchemy ORM tables live in app/models/orm.py; keep the two in sync when adding fields.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, model_validator

REQUIRED_MODEL_AGENTS = ("scout", "scribe", "critic")

# Footnote refs of the form `[^sX]`, with `[sX]` accepted for model outputs that omit the caret. Used to derive `ReportSection.cited_source_ids` from prose. Definitions (`[^sX]: ...`) match the same pattern; deduplication below means the trailing colon variant is harmless.
_FOOTNOTE_REF_RE = re.compile(r"\[\^?(s\d+)\]")


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
    # Per-agent model IDs keyed by agent name. Each `REQUIRED_MODEL_AGENTS` entry must be present and non-empty: the orchestrator looks up `job.models[agent]` per phase, and a missing key would fail mid-run rather than at request time.
    models: dict[str, str] = Field(...)
    # Optional list of sub-questions from the preview screen. When present, Scout skips its
    # decompose LLM call and uses these directly, so the run honours the user's approved plan.
    sub_questions: list[str] | None = None

    @model_validator(mode="after")
    def _require_all_agent_models(self) -> ResearchRequest:
        missing = [a for a in REQUIRED_MODEL_AGENTS if not self.models.get(a)]
        if missing:
            msg = f"models must include non-empty entries for: {', '.join(missing)}"
            raise ValueError(msg)
        return self


class ResearchJob(BaseModel):
    """Job descriptor returned to the client on creation and status queries."""

    id: UUID
    topic: str
    language: str = "en"
    depth: Depth = Depth.STANDARD
    models: dict[str, str] = Field(default_factory=dict)
    sub_questions: list[str] | None = None
    status: JobStatus = JobStatus.PENDING
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None


class Source(BaseModel):
    """A single source gathered by Scout, referenced by Scribe and Critic."""

    id: str  # short form: "s1", "s2", ... unique within a job
    url: HttpUrl
    title: str
    author: str | None = None
    published_at: datetime | None = None
    credibility: float = Field(ge=0.0, le=1.0)
    relevance: float = Field(ge=0.0, le=1.0)
    snippet: str  # quoted excerpt used for inline citation


class ReportSection(BaseModel):
    id: str  # "sec1", "sec2", ... sequential, unique within report
    heading: str
    # GFM markdown; factual claims wrapped in <span data-claim="secN.cM">.
    body_md: str
    # Always derived from `body_md` — see `_derive_cited_source_ids`. Kept on the model so consumers can read it without parsing markdown, but the LLM never produces it: asking a model to maintain a list redundant with the prose just gave us a steady stream of validation retries when the two disagreed.
    cited_source_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _derive_cited_source_ids(self) -> ReportSection:
        # Overwrite whatever was supplied at construction time. The single source of truth is `body_md`; any caller-provided value (LLM output, deserialized JSONB, test fixture) is ignored on purpose so the field can never drift from the prose. Order is first-appearance for stable rendering and reproducible diffs.
        seen: set[str] = set()
        ordered: list[str] = []
        for ref in _FOOTNOTE_REF_RE.findall(self.body_md):
            if ref not in seen:
                seen.add(ref)
                ordered.append(ref)
        self.cited_source_ids = ordered
        return self


class Contradiction(BaseModel):
    description: str
    source_ids: list[str]


class ScribeReport(BaseModel):
    id: UUID
    job_id: UUID
    topic: str
    title: str
    summary_md: str
    sections: list[ReportSection]
    sources: list[Source]
    contradictions: list[Contradiction]
    follow_ups: list[str]
    generated_at: datetime
    model: str  # which OpenRouter model produced this (audit trail)


class Verdict(StrEnum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"


class ClaimFlag(BaseModel):
    claim_id: str  # matches data-claim="secN.cM" in body_md
    section_id: str  # redundant with claim_id prefix; kept for fast lookup
    verdict: Verdict
    rationale: str
    supporting_source_ids: list[str]  # empty when verdict is unsupported


class SectionConfidence(BaseModel):
    section_id: str
    score: float = Field(ge=0.0, le=1.0)
    reasoning: str


class CriticAnnotations(BaseModel):
    id: UUID
    report_id: UUID
    section_confidence: list[SectionConfidence]
    claim_flags: list[ClaimFlag]
    overall_confidence: float = Field(ge=0.0, le=1.0)
    model: str
    generated_at: datetime


class VerifiedReport(BaseModel):
    """Full response returned to the frontend once a job has completed."""

    job: ResearchJob
    report: ScribeReport
    annotations: CriticAnnotations


class PreviewResponse(BaseModel):
    """Response body for POST /api/research/preview."""

    sub_questions: list[str]


class FollowUpRequest(BaseModel):
    """Inbound body for POST /api/research/{job_id}/follow-up.

    The child job inherits language, depth, and per-agent models from the parent, so the only thing the caller supplies is the new question.
    """

    question: str = Field(..., min_length=3, max_length=500)


class FollowUpLink(BaseModel):
    """One edge in a job's follow-up lineage.

    `job_id` / `topic` / `status` describe the job on the *other* end of the edge (the parent when this link is a job's parent, a child when it is one of a job's children); `question` is the follow-up question recorded on the edge itself.
    """

    job_id: UUID
    question: str
    topic: str
    status: JobStatus
    created_at: datetime


class JobLineage(BaseModel):
    """Response body for GET /api/research/{job_id}/lineage."""

    parent: FollowUpLink | None
    children: list[FollowUpLink]
