"""WebSocket progress event models.

All events published to Redis pubsub (channel `job:{job_id}:events`) and forwarded to connected WebSocket clients must conform to one of the variants in `ProgressEvent`.
The discriminator field `type` lets the frontend (and any Python consumer) deserialise without a manual if-chain.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.research import ClaimFlag, ReportSection, ResearchJob, Source


class EventBase(BaseModel):
    job_id: UUID
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SubQuestionsGenerated(EventBase):
    type: Literal["sub_questions_generated"] = "sub_questions_generated"
    sub_questions: list[str]


class SourceFound(EventBase):
    type: Literal["source_found"] = "source_found"
    source: Source  # streams as Scout finds each source


class SourceScored(EventBase):
    type: Literal["source_scored"] = "source_scored"
    source_id: str
    credibility: float
    relevance: float


class ScoutComplete(EventBase):
    type: Literal["scout_complete"] = "scout_complete"
    source_count: int


class SectionDrafted(EventBase):
    type: Literal["section_drafted"] = "section_drafted"
    section: ReportSection  # streams as Scribe writes each section


class ScribeComplete(EventBase):
    type: Literal["scribe_complete"] = "scribe_complete"


class ClaimVerified(EventBase):
    type: Literal["claim_verified"] = "claim_verified"
    flag: ClaimFlag  # streams as Critic verifies each claim


class JobCompleted(EventBase):
    type: Literal["job_completed"] = "job_completed"
    overall_confidence: float


class JobFailed(EventBase):
    type: Literal["job_failed"] = "job_failed"
    error: str


ProgressEvent = Annotated[
    SubQuestionsGenerated
    | SourceFound
    | SourceScored
    | ScoutComplete
    | SectionDrafted
    | ScribeComplete
    | ClaimVerified
    | JobCompleted
    | JobFailed,
    Field(discriminator="type"),
]


class JobSnapshot(BaseModel):
    """First message sent on a WebSocket connection.

    Lets a client that connected mid-pipeline render the current state instead of waiting for the next event.
    `job` is optional so callers can still emit an identity-only snapshot when no persisted job state is available.
    """

    type: Literal["snapshot"] = "snapshot"
    job_id: UUID
    job: ResearchJob | None = None
