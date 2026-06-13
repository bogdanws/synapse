"""Unit tests for the Scout → Scribe → Critic LangGraph orchestrator.

These tests exercise the pipeline's control flow — state transitions, error routing, persistence call order, terminal events — with the heavy I/O (LLM calls, HTTP, real SQL) replaced by stubs. The DB-bound behaviour of `JobRepository` is integration-test territory and is not duplicated here.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.agents import orchestrator as orch
from app.agents.scout_graph import ScoutOutput
from app.models.events import (
    ClaimVerified,
    JobCompleted,
    JobFailed,
    ProgressEvent,
    ScoutComplete,
    ScribeComplete,
    SectionDrafted,
)
from app.models.research import (
    ClaimFlag,
    CriticAnnotations,
    Depth,
    JobStatus,
    ReportSection,
    ResearchJob,
    ScribeReport,
    SectionConfidence,
    Source,
    Verdict,
)

# ---- fixtures / fakes ------------------------------------------------------


def _make_job(job_id: UUID) -> ResearchJob:
    return ResearchJob(
        id=job_id,
        topic="Quantum",
        language="en",
        depth=Depth.STANDARD,
        models={"scout": "scout/m", "scribe": "scribe/m", "critic": "critic/m"},
        status=JobStatus.PENDING,
        progress=0.0,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _source(short_id: str = "s1") -> Source:
    return Source(
        id=short_id,
        url="https://example.com/x",  # type: ignore[arg-type]
        title=f"Source {short_id}",
        credibility=0.7,
        relevance=0.8,
        snippet="snippet",
    )


def _report(job_id: UUID, sources: list[Source]) -> ScribeReport:
    return ScribeReport(
        id=uuid4(),
        job_id=job_id,
        topic="Quantum",
        title="T",
        summary_md="s",
        sections=[
            ReportSection(
                id="sec1",
                heading="H",
                body_md='<span data-claim="sec1.c1">a[^s1]</span>',
            )
        ],
        sources=sources,
        contradictions=[],
        follow_ups=[],
        generated_at=datetime.now(UTC),
        model="scribe/m",
    )


def _annotations(report: ScribeReport) -> CriticAnnotations:
    return CriticAnnotations(
        id=uuid4(),
        report_id=report.id,
        section_confidence=[SectionConfidence(section_id="sec1", score=0.9, reasoning="r")],
        claim_flags=[
            ClaimFlag(
                claim_id="sec1.c1",
                section_id="sec1",
                verdict=Verdict.SUPPORTED,
                rationale="r",
                supporting_source_ids=["s1"],
            )
        ],
        overall_confidence=0.9,
        model="critic/m",
        generated_at=datetime.now(UTC),
    )


class _FakeRepo:
    """Records every JobRepository call without touching a database."""

    instances: list[_FakeRepo] = []

    def __init__(self, session: object) -> None:
        self._session = session
        self.status_calls: list[tuple[JobStatus, float | None]] = []
        self.replace_sources_calls: list[tuple[UUID, list[Source]]] = []
        self.save_report_calls: list[tuple[UUID, ScribeReport]] = []
        self.save_annotations_calls: list[tuple[UUID, CriticAnnotations]] = []
        self.completed_for: list[UUID] = []
        self.failed_for: list[tuple[UUID, str]] = []
        _FakeRepo.instances.append(self)

    async def get_job(self, job_id: UUID) -> ResearchJob:
        return self._session.job  # type: ignore[no-any-return,attr-defined]

    async def get_follow_up_parent_id(self, job_id: UUID) -> UUID | None:
        return self._session.parent_id  # type: ignore[no-any-return,attr-defined]

    async def set_status(
        self, job_id: UUID, *, status: JobStatus, progress: float | None = None
    ) -> None:
        self.status_calls.append((status, progress))

    async def mark_completed(self, job_id: UUID) -> None:
        self.completed_for.append(job_id)

    async def mark_failed(self, job_id: UUID, error: str) -> None:
        self.failed_for.append((job_id, error))

    async def replace_sources(self, job_id: UUID, sources: list[Source]) -> None:
        self.replace_sources_calls.append((job_id, list(sources)))

    async def save_report(self, job_id: UUID, report: ScribeReport) -> UUID:
        self.save_report_calls.append((job_id, report))
        return report.id

    async def save_annotations(self, report_id: UUID, annotations: CriticAnnotations) -> UUID:
        self.save_annotations_calls.append((report_id, annotations))
        return annotations.id


class _FakeSession:
    """Minimal stand-in matching the bits of AsyncSession the orchestrator uses."""

    def __init__(
        self,
        job: ResearchJob,
        *,
        parent_id: UUID | None = None,
        parent_sources: list[Source] | None = None,
    ) -> None:
        self.job = job
        self.parent_id = parent_id
        self.parent_sources = parent_sources or []
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


def _make_session_factory(
    job: ResearchJob,
    *,
    parent_id: UUID | None = None,
    parent_sources: list[Source] | None = None,
) -> Callable[[], Any]:
    @asynccontextmanager
    async def _factory() -> Any:
        yield _FakeSession(job, parent_id=parent_id, parent_sources=parent_sources)

    return _factory


def _aggregate_repo_calls() -> dict[str, list[Any]]:
    """Flatten every repo call across `_FakeRepo.instances` into one dict.

    The orchestrator opens a fresh session (and so a fresh repo) per write boundary; collapsing across instances gives tests the same view they'd have with a single repo.
    """
    aggregated: dict[str, list[Any]] = {
        "status": [],
        "replace_sources": [],
        "save_report": [],
        "save_annotations": [],
        "completed": [],
        "failed": [],
    }
    for repo in _FakeRepo.instances:
        aggregated["status"].extend(repo.status_calls)
        aggregated["replace_sources"].extend(repo.replace_sources_calls)
        aggregated["save_report"].extend(repo.save_report_calls)
        aggregated["save_annotations"].extend(repo.save_annotations_calls)
        aggregated["completed"].extend(repo.completed_for)
        aggregated["failed"].extend(repo.failed_for)
    return aggregated


@pytest.fixture(autouse=True)
def _reset_fake_repo_instances() -> None:
    _FakeRepo.instances.clear()


@pytest.fixture
def patched_orchestrator(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Patch the orchestrator's collaborators with controllable stubs.

    Returns a mutable dict the test populates with the values each agent's run helper should produce. Helpers raise if the test left an entry as `None`.
    """
    job_id = uuid4()
    job = _make_job(job_id)
    sources = [_source("s1")]
    report = _report(job_id, sources)
    annotations = _annotations(report)

    config: dict[str, Any] = {
        "job_id": job_id,
        "job": job,
        "scout_output": ScoutOutput(sub_questions=["q1"], sources=sources),
        "report": report,
        "annotations": annotations,
        "scout_error": None,
        "scribe_error": None,
        "critic_error": None,
        "scout_seed_received": None,
    }

    async def fake_run_scout(
        *,
        job_id: UUID,
        topic: str,
        agent: object,
        publish: Callable[..., Awaitable[None]],
        sub_questions_override: list[str] | None = None,
        seed_sources: list[Source] | None = None,
    ) -> ScoutOutput:
        config["scout_seed_received"] = seed_sources
        if config["scout_error"]:
            raise RuntimeError(config["scout_error"])
        await publish(
            ScoutComplete(job_id=job_id, source_count=len(config["scout_output"].sources))
        )
        return config["scout_output"]

    async def fake_load_sources(session: Any, job_id: UUID) -> list[Source]:
        return list(session.parent_sources)

    async def fake_run_scribe(
        *,
        job_id: UUID,
        topic: str,
        sub_questions: list[str],
        sources: list[Source],
        agent: object,
        publish: Callable[..., Awaitable[None]],
    ) -> ScribeReport:
        if config["scribe_error"]:
            raise RuntimeError(config["scribe_error"])
        for section in config["report"].sections:
            await publish(SectionDrafted(job_id=job_id, section=section))
        await publish(ScribeComplete(job_id=job_id))
        return config["report"]

    async def fake_run_critic(
        *,
        job_id: UUID,
        report: ScribeReport,
        agent: object,
        publish: Callable[..., Awaitable[None]],
    ) -> CriticAnnotations:
        if config["critic_error"]:
            raise RuntimeError(config["critic_error"])
        for flag in config["annotations"].claim_flags:
            await publish(ClaimVerified(job_id=job_id, flag=flag))
        return config["annotations"]

    # Stub the agent constructors so we don't try to talk to OpenRouter or Exa.
    class _StubAgent:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.model = kwargs.get("model") or (args[0] if args else "stub")

    monkeypatch.setattr(orch, "JobRepository", _FakeRepo)
    monkeypatch.setattr(orch, "ScoutAgent", _StubAgent)
    monkeypatch.setattr(orch, "ScribeAgent", _StubAgent)
    monkeypatch.setattr(orch, "CriticAgent", _StubAgent)
    monkeypatch.setattr(orch, "ExaSearchClient", _StubAgent)
    monkeypatch.setattr(orch, "run_scout", fake_run_scout)
    monkeypatch.setattr(orch, "run_scribe", fake_run_scribe)
    monkeypatch.setattr(orch, "run_critic", fake_run_critic)
    monkeypatch.setattr(orch, "load_sources", fake_load_sources)

    return config


# ---- tests -----------------------------------------------------------------


async def test_pipeline_happy_path_persists_in_phase_order_and_publishes_completion(
    patched_orchestrator: dict[str, Any],
) -> None:
    job_id: UUID = patched_orchestrator["job_id"]
    captured: list[ProgressEvent] = []

    async def capture(event: ProgressEvent) -> None:
        captured.append(event)

    cleaned: list[UUID] = []

    async def _cleanup(jid: UUID) -> None:
        cleaned.append(jid)

    await orch.run_pipeline(
        job_id=job_id,
        session_factory=_make_session_factory(patched_orchestrator["job"]),
        publish=capture,
        cleanup=_cleanup,
    )

    # Cleanup runs once, after the terminal event, with the right job id.
    assert cleaned == [job_id]

    repo = _aggregate_repo_calls()
    # Status moves scouting → synthesizing → critiquing during the run, then
    # mark_completed at the end (which is its own dedicated call, not a status update).
    statuses = [s for s, _ in repo["status"]]
    assert statuses == [
        JobStatus.SCOUTING,
        JobStatus.SYNTHESIZING,
        JobStatus.CRITIQUING,
    ]

    # Sources persisted from inside the scout node (mid-pipeline), report and
    # annotations at the end.
    assert len(repo["replace_sources"]) == 1
    assert len(repo["save_report"]) == 1
    assert len(repo["save_annotations"]) == 1
    assert repo["completed"] == [job_id]
    assert repo["failed"] == []

    # The terminal event is JobCompleted carrying the annotation's confidence.
    assert isinstance(captured[-1], JobCompleted)
    assert captured[-1].overall_confidence == pytest.approx(0.9)


async def test_pipeline_scout_failure_publishes_job_failed_and_skips_downstream_writes(
    patched_orchestrator: dict[str, Any],
) -> None:
    patched_orchestrator["scout_error"] = "exa unreachable"
    captured: list[ProgressEvent] = []

    async def capture(event: ProgressEvent) -> None:
        captured.append(event)

    cleaned: list[UUID] = []

    async def _cleanup(jid: UUID) -> None:
        cleaned.append(jid)

    await orch.run_pipeline(
        job_id=patched_orchestrator["job_id"],
        session_factory=_make_session_factory(patched_orchestrator["job"]),
        publish=capture,
        cleanup=_cleanup,
    )

    # Cleanup must also fire on the failure path so the persisted event log
    # doesn't leak for jobs that never reach `done`.
    assert cleaned == [patched_orchestrator["job_id"]]

    repo = _aggregate_repo_calls()
    # Only the scouting status update fires; scribe/critic never run.
    assert [s for s, _ in repo["status"]] == [JobStatus.SCOUTING]
    assert repo["replace_sources"] == []
    assert repo["save_report"] == []
    assert repo["save_annotations"] == []
    assert repo["completed"] == []
    assert len(repo["failed"]) == 1
    assert "exa unreachable" in repo["failed"][0][1]

    failure_events = [e for e in captured if isinstance(e, JobFailed)]
    assert len(failure_events) == 1
    assert "exa unreachable" in failure_events[0].error


async def test_pipeline_scribe_failure_keeps_sources_but_skips_critic(
    patched_orchestrator: dict[str, Any],
) -> None:
    patched_orchestrator["scribe_error"] = "model returned junk"

    await orch.run_pipeline(
        job_id=patched_orchestrator["job_id"],
        session_factory=_make_session_factory(patched_orchestrator["job"]),
        publish=_noop,
        cleanup=_noop_cleanup,
    )

    repo = _aggregate_repo_calls()
    assert [s for s, _ in repo["status"]] == [
        JobStatus.SCOUTING,
        JobStatus.SYNTHESIZING,
    ]
    # Scout's sources were written before scribe failed.
    assert len(repo["replace_sources"]) == 1
    # Critic never ran; report and annotations were not written.
    assert repo["save_report"] == []
    assert repo["save_annotations"] == []
    assert len(repo["failed"]) == 1
    assert "model returned junk" in repo["failed"][0][1]


async def test_pipeline_critic_failure_does_not_persist_report(
    patched_orchestrator: dict[str, Any],
) -> None:
    """If Critic fails, the (orphan) Scribe report stays out of the DB.

    Persisting only on full success keeps the GET /research/{id} endpoint's
    invariants simple: if a report row exists, an annotations row also does.
    """
    patched_orchestrator["critic_error"] = "validation exhausted"

    await orch.run_pipeline(
        job_id=patched_orchestrator["job_id"],
        session_factory=_make_session_factory(patched_orchestrator["job"]),
        publish=_noop,
        cleanup=_noop_cleanup,
    )

    repo = _aggregate_repo_calls()
    assert repo["save_report"] == []
    assert repo["save_annotations"] == []
    assert len(repo["failed"]) == 1
    assert "validation exhausted" in repo["failed"][0][1]


async def test_pipeline_publishes_intermediate_events_from_all_three_phases(
    patched_orchestrator: dict[str, Any],
) -> None:
    captured: list[ProgressEvent] = []

    async def capture(event: ProgressEvent) -> None:
        captured.append(event)

    await orch.run_pipeline(
        job_id=patched_orchestrator["job_id"],
        session_factory=_make_session_factory(patched_orchestrator["job"]),
        publish=capture,
        cleanup=_noop_cleanup,
    )

    types_in_order = [type(e).__name__ for e in captured]
    # ScoutComplete must precede SectionDrafted, which must precede ScribeComplete,
    # which must precede ClaimVerified, which must precede JobCompleted.
    expected_first = types_in_order.index("ScoutComplete")
    expected_second = types_in_order.index("SectionDrafted")
    expected_third = types_in_order.index("ScribeComplete")
    expected_fourth = types_in_order.index("ClaimVerified")
    expected_fifth = types_in_order.index("JobCompleted")
    assert expected_first < expected_second < expected_third < expected_fourth < expected_fifth


async def test_pipeline_seeds_scout_with_parent_sources_for_follow_up_child(
    patched_orchestrator: dict[str, Any],
) -> None:
    """A child job whose id has a FollowUp parent edge passes the parent's sources to Scout."""
    parent_sources = [_source("s1"), _source("s2")]

    await orch.run_pipeline(
        job_id=patched_orchestrator["job_id"],
        session_factory=_make_session_factory(
            patched_orchestrator["job"],
            parent_id=uuid4(),
            parent_sources=parent_sources,
        ),
        publish=_noop,
        cleanup=_noop_cleanup,
    )

    assert patched_orchestrator["scout_seed_received"] == parent_sources


async def test_pipeline_does_not_seed_scout_for_a_root_job(
    patched_orchestrator: dict[str, Any],
) -> None:
    """A job with no parent edge runs Scout without seed sources (fresh research)."""
    await orch.run_pipeline(
        job_id=patched_orchestrator["job_id"],
        session_factory=_make_session_factory(patched_orchestrator["job"]),
        publish=_noop,
        cleanup=_noop_cleanup,
    )

    assert patched_orchestrator["scout_seed_received"] is None


async def _noop(_event: ProgressEvent) -> None:
    return None


async def _noop_cleanup(_job_id: UUID) -> None:
    return None
