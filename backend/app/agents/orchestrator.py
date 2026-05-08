"""LangGraph pipeline coordinating Scout → Scribe → Critic.

Graph shape:

    ┌──────┐   continue   ┌────────┐   continue   ┌────────┐   continue   ┌─────┐
    │scout │ ───────────► │ scribe │ ───────────► │ critic │ ───────────► │ END │
    └──────┘              └────────┘              └────────┘              └─────┘
       │ fail                │ fail                  │ fail                ▲
       └─────────────────────┴───────────────────────┴────────────────────┘

Each node owns the side effects for its phase: status updates on the `research_jobs` row, persistence of the artifacts it produced, and the per-phase progress events (delegated to `run_scout` / `run_scribe` / `run_critic`). Nodes catch their own exceptions, write the error message into state, and the conditional edges route to `END` so the runner can publish `JobFailed` and persist the failure once.

`run_pipeline` is the top-level entrypoint the taskiq worker calls. It loads the job, builds the agents from `job.models`, owns the lifetime of the shared httpx client used by `ExaSearchClient`, and decides between `JobCompleted` and `JobFailed` based on the graph's final state.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Literal, NotRequired, TypedDict, cast
from uuid import UUID

import httpx
import structlog
from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.critic import CriticAgent
from app.agents.critic_graph import run_critic
from app.agents.scout import ScoutAgent
from app.agents.scout_graph import EventPublisher, run_scout
from app.agents.scribe import ScribeAgent
from app.agents.scribe_graph import run_scribe
from app.models.events import JobCompleted, JobFailed
from app.models.research import (
    CriticAnnotations,
    JobStatus,
    ScribeReport,
    Source,
)
from app.services.events import publish as default_publish
from app.services.persistence import JobRepository
from app.services.search import ExaSearchClient

_log = structlog.get_logger(__name__)

SessionFactory = async_sessionmaker[AsyncSession]


class GraphState(TypedDict):
    """Shared state passed between nodes.

    The fields produced by each node are `NotRequired` because they don't exist on entry; LangGraph merges the dict each node returns into the running state.
    """

    job_id: UUID
    topic: str
    sub_questions_override: NotRequired[list[str]]
    sub_questions: NotRequired[list[str]]
    sources: NotRequired[list[Source]]
    report: NotRequired[ScribeReport]
    annotations: NotRequired[CriticAnnotations]
    error: NotRequired[str]


def _build_graph(
    *,
    scout_agent: ScoutAgent,
    scribe_agent: ScribeAgent,
    critic_agent: CriticAgent,
    session_factory: SessionFactory,
    publish: EventPublisher,
) -> Callable[[GraphState], Awaitable[GraphState]]:
    """Compile the LangGraph pipeline. Returns a callable invoked with the initial state."""

    async def scout_node(state: GraphState) -> dict[str, object]:
        job_id = state["job_id"]
        try:
            await _set_status(session_factory, job_id, JobStatus.SCOUTING, progress=0.05)
            output = await run_scout(
                job_id=job_id,
                topic=state["topic"],
                agent=scout_agent,
                publish=publish,
                sub_questions_override=state.get("sub_questions_override") or None,
            )
            async with session_factory() as session:
                repo = JobRepository(session)
                await repo.replace_sources(job_id, output.sources)
                await session.commit()
        except Exception as exc:
            _log.exception("scout_node_failed", job_id=str(job_id))
            return {"error": f"scout failed: {exc}"}
        return {
            "sub_questions": output.sub_questions,
            "sources": output.sources,
        }

    async def scribe_node(state: GraphState) -> dict[str, object]:
        job_id = state["job_id"]
        try:
            await _set_status(session_factory, job_id, JobStatus.SYNTHESIZING, progress=0.4)
            report = await run_scribe(
                job_id=job_id,
                topic=state["topic"],
                sub_questions=state.get("sub_questions", []),
                sources=state["sources"],
                agent=scribe_agent,
                publish=publish,
            )
        except Exception as exc:
            _log.exception("scribe_node_failed", job_id=str(job_id))
            return {"error": f"scribe failed: {exc}"}
        return {"report": report}

    async def critic_node(state: GraphState) -> dict[str, object]:
        job_id = state["job_id"]
        try:
            await _set_status(session_factory, job_id, JobStatus.CRITIQUING, progress=0.75)
            annotations = await run_critic(
                job_id=job_id,
                report=state["report"],
                agent=critic_agent,
                publish=publish,
            )
        except Exception as exc:
            _log.exception("critic_node_failed", job_id=str(job_id))
            return {"error": f"critic failed: {exc}"}
        return {"annotations": annotations}

    def _route(state: GraphState) -> Literal["continue", "fail"]:
        return "fail" if state.get("error") else "continue"

    graph: StateGraph[GraphState, None, GraphState, GraphState] = StateGraph(GraphState)
    graph.add_node("scout", scout_node)
    graph.add_node("scribe", scribe_node)
    graph.add_node("critic", critic_node)
    graph.set_entry_point("scout")
    graph.add_conditional_edges("scout", _route, {"continue": "scribe", "fail": END})
    graph.add_conditional_edges("scribe", _route, {"continue": "critic", "fail": END})
    graph.add_edge("critic", END)

    compiled = graph.compile()

    async def _run(state: GraphState) -> GraphState:
        # `ainvoke` returns the merged final state as a plain dict; cast it back so downstream code keeps the structured `GraphState` view.
        result: GraphState = await compiled.ainvoke(state)  # type: ignore[assignment]
        return result

    return _run


async def run_pipeline(
    *,
    job_id: UUID,
    session_factory: SessionFactory,
    publish: EventPublisher = default_publish,
    http_client: httpx.AsyncClient | None = None,
) -> None:
    """Execute the full Scout → Scribe → Critic pipeline for a persisted job.

    Caller responsibilities:
      * The `research_jobs` row for `job_id` must already exist (created by the API on enqueue).
      * The function consumes one DB connection at a time via `session_factory`. Each commit boundary is its own transaction so a crash mid-pipeline leaves a coherent partial state.

    The shared `httpx.AsyncClient` for Exa is owned by this function unless the caller supplies one (used in tests to share a respx mount).
    """
    async with session_factory() as session:
        job = await JobRepository(session).get_job(job_id)

    owns_http = http_client is None
    http = http_client or httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0))
    try:
        scout_agent = ScoutAgent(
            model=job.models["scout"],
            search_client=ExaSearchClient(http_client=http),
        )
        scribe_agent = ScribeAgent(model=job.models["scribe"])
        critic_agent = CriticAgent(model=job.models["critic"])

        runner = _build_graph(
            scout_agent=scout_agent,
            scribe_agent=scribe_agent,
            critic_agent=critic_agent,
            session_factory=session_factory,
            publish=publish,
        )

        try:
            initial: GraphState = {"job_id": job_id, "topic": job.topic}
            if job.sub_questions:
                initial["sub_questions_override"] = job.sub_questions
            final_state = await runner(initial)
        except Exception as exc:
            # Defensive: an exception escaping a node means the node's own
            # try/except missed something. Treat it the same as a recorded
            # error so the job lands in `failed` rather than wedged in flight.
            _log.exception("pipeline_unhandled_exception", job_id=str(job_id))
            final_state = cast(
                GraphState,
                {"job_id": job_id, "topic": job.topic, "error": f"pipeline crashed: {exc}"},
            )

        if "error" in final_state and final_state["error"]:
            await _persist_failure(session_factory, job_id, final_state["error"])
            await publish(JobFailed(job_id=job_id, error=final_state["error"]))
            return

        report = final_state.get("report")
        annotations = final_state.get("annotations")
        if report is None or annotations is None:
            # Belt and braces: the graph reached the end without an error but
            # also without producing artifacts. Treat as failure rather than
            # publishing a misleading JobCompleted.
            error = "pipeline finished without producing a report"
            await _persist_failure(session_factory, job_id, error)
            await publish(JobFailed(job_id=job_id, error=error))
            return

        await _persist_success(session_factory, job_id, report=report, annotations=annotations)
        await publish(
            JobCompleted(
                job_id=job_id,
                overall_confidence=annotations.overall_confidence,
            )
        )
    finally:
        if owns_http:
            await http.aclose()


# ---- helpers ---------------------------------------------------------------


async def _set_status(
    session_factory: SessionFactory,
    job_id: UUID,
    status: JobStatus,
    *,
    progress: float | None = None,
) -> None:
    async with session_factory() as session:
        await JobRepository(session).set_status(job_id, status=status, progress=progress)
        await session.commit()


async def _persist_failure(session_factory: SessionFactory, job_id: UUID, error: str) -> None:
    async with session_factory() as session:
        await JobRepository(session).mark_failed(job_id, error)
        await session.commit()


async def _persist_success(
    session_factory: SessionFactory,
    job_id: UUID,
    *,
    report: ScribeReport,
    annotations: CriticAnnotations,
) -> None:
    async with session_factory() as session:
        repo = JobRepository(session)
        report_id = await repo.save_report(job_id, report)
        await repo.save_annotations(report_id, annotations)
        await repo.mark_completed(job_id)
        await session.commit()
