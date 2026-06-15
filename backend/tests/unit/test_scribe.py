"""Unit tests for `ScribeAgent` and the `run_scribe` LangGraph node."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
import respx

from app.agents.scribe import ScribeAgent
from app.agents.scribe_graph import run_scribe
from app.models.events import (
    ProgressEvent,
    ScribeComplete,
    SectionDrafted,
)
from app.models.research import Source
from app.services.llm import OPENROUTER_BASE_URL
from app.services.validation import ScribeValidationError

# ---- helpers ---------------------------------------------------------------


def _openrouter_completion(json_content: str) -> dict[str, Any]:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 0,
        "model": "test-model",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": json_content},
                "finish_reason": "stop",
            }
        ],
    }


def _source(short_id: str, url: str = "https://example.com/x") -> Source:
    return Source(
        id=short_id,
        url=url,  # type: ignore[arg-type]
        title=f"Source {short_id}",
        credibility=0.7,
        relevance=0.8,
        snippet="snippet",
    )


def _llm_payload(*, sections: list[dict[str, Any]] | None = None) -> str:
    """Build a valid `_ScribeLLMOutput` JSON payload.

    Sections deliberately omit `cited_source_ids`: the LLM no longer emits it; `ReportSection` derives it from `body_md` after parsing.
    """
    if sections is None:
        sections = [
            {
                "id": "sec1",
                "heading": "Background",
                "body_md": '<span data-claim="sec1.c1">first claim[^s1]</span>',
            }
        ]
    return json.dumps(
        {
            "title": "Quantum Title",
            "summary_md": "Short summary.",
            "sections": sections,
            "contradictions": [],
            "follow_ups": ["What about X?"],
        }
    )


# ---- agent: happy path -----------------------------------------------------


@pytest.mark.respx(base_url=OPENROUTER_BASE_URL)
async def test_synthesize_returns_validated_report(
    respx_mock: respx.MockRouter,
) -> None:
    respx_mock.post("/chat/completions").mock(
        return_value=httpx.Response(200, json=_openrouter_completion(_llm_payload()))
    )
    agent = ScribeAgent(model="test/model")
    job_id = uuid4()
    report = await agent.synthesize(
        job_id=job_id,
        topic="Quantum",
        sub_questions=["What is X?"],
        sources=[_source("s1")],
    )
    assert report.title == "Quantum Title"
    assert report.job_id == job_id
    # Sources are pinned by the system, not the model: they always match
    # exactly what was passed in.
    assert [s.id for s in report.sources] == ["s1"]
    assert report.model == "test/model"
    assert isinstance(report.id, UUID)
    assert report.sections[0].id == "sec1"
    # `cited_source_ids` is derived server-side from body_md footnote refs even though the LLM did not produce it.
    assert report.sections[0].cited_source_ids == ["s1"]


@pytest.mark.respx(base_url=OPENROUTER_BASE_URL)
async def test_synthesize_repairs_orphan_citations_without_retry(
    respx_mock: respx.MockRouter,
) -> None:
    """Regression: the production failure mode (bare `[^sX]`, no span) now self-heals.

    The model emits a citation it forgot to wrap. Previously this exhausted the
    retry budget and failed the job; the server-side repair pass wraps it, so a
    single LLM call yields a valid report.
    """
    payload = _llm_payload(
        sections=[
            {
                "id": "sec1",
                "heading": "Background",
                "body_md": "Romania's prime minister is Ilie Bolojan[^s1].",
            }
        ]
    )
    route = respx_mock.post("/chat/completions").mock(
        return_value=httpx.Response(200, json=_openrouter_completion(payload))
    )
    agent = ScribeAgent(model="test/model")
    report = await agent.synthesize(
        job_id=uuid4(),
        topic="Romania PM",
        sub_questions=[],
        sources=[_source("s1")],
    )
    assert route.call_count == 1  # repaired in place, no retry needed
    body = report.sections[0].body_md
    assert '<span data-claim="sec1.c1">' in body
    assert "[^s1]" in body
    assert report.sections[0].cited_source_ids == ["s1"]


@pytest.mark.respx(base_url=OPENROUTER_BASE_URL)
async def test_synthesize_strips_markup_from_summary(
    respx_mock: respx.MockRouter,
) -> None:
    """The summary renders as plain text, so claim spans / citations are stripped."""
    payload = json.dumps(
        {
            "title": "T",
            "summary_md": (
                '<span data-claim="summary.c1">Veștea was designated PM[^s1]</span>. '
                "Parliament has not yet invested the government."
            ),
            "sections": [
                {
                    "id": "sec1",
                    "heading": "Background",
                    "body_md": '<span data-claim="sec1.c1">a[^s1]</span>',
                }
            ],
            "contradictions": [],
            "follow_ups": [],
        }
    )
    respx_mock.post("/chat/completions").mock(
        return_value=httpx.Response(200, json=_openrouter_completion(payload))
    )
    agent = ScribeAgent(model="test/model")
    report = await agent.synthesize(
        job_id=uuid4(),
        topic="Romania PM",
        sub_questions=[],
        sources=[_source("s1")],
    )
    assert "<span" not in report.summary_md
    assert "[^s1]" not in report.summary_md
    assert report.summary_md == (
        "Veștea was designated PM. Parliament has not yet invested the government."
    )
    # The section body keeps its claim markup — only the summary is stripped.
    assert "data-claim" in report.sections[0].body_md


# ---- agent: empty source list ----------------------------------------------


async def test_synthesize_rejects_empty_sources() -> None:
    agent = ScribeAgent(model="test/model")
    with pytest.raises(ScribeValidationError, match="no sources"):
        await agent.synthesize(job_id=uuid4(), topic="t", sub_questions=[], sources=[])


# ---- agent: retry on validation failure ------------------------------------


@pytest.mark.respx(base_url=OPENROUTER_BASE_URL)
async def test_synthesize_retries_with_feedback_on_validation_failure(
    respx_mock: respx.MockRouter,
) -> None:
    """First attempt has a non-sequential claim; the agent should retry once and succeed."""
    bad_payload = _llm_payload(
        sections=[
            {
                "id": "sec1",
                "heading": "Background",
                "body_md": (
                    '<span data-claim="sec1.c1">a[^s1]</span> '
                    '<span data-claim="sec1.c3">b[^s1]</span>'  # gap -> invalid
                ),
            }
        ]
    )
    good_payload = _llm_payload()
    route = respx_mock.post("/chat/completions").mock(
        side_effect=[
            httpx.Response(200, json=_openrouter_completion(bad_payload)),
            httpx.Response(200, json=_openrouter_completion(good_payload)),
        ]
    )

    agent = ScribeAgent(model="test/model")
    report = await agent.synthesize(
        job_id=uuid4(),
        topic="t",
        sub_questions=[],
        sources=[_source("s1")],
    )
    assert route.call_count == 2
    assert report.sections[0].id == "sec1"

    # The retry call must show the model its previous (bad) JSON in an
    # assistant turn followed by a corrective user turn, so the model can
    # edit its mistake instead of regenerating from scratch. Without this,
    # the model has no way to know what "your previous response" refers to.
    second_request = route.calls[1].request
    body = json.loads(second_request.content)
    roles = [m["role"] for m in body["messages"]]
    assert roles == ["system", "user", "assistant", "user"], roles
    # Assistant turn replays the bad JSON so the model sees its own mistake.
    assistant_content = body["messages"][-2]["content"]
    assert "sec1.c3" in assistant_content
    # Final user turn carries the targeted validation feedback.
    user_msg = body["messages"][-1]["content"]
    assert "failed validation" in user_msg
    assert "expected next claim 'c2'" in user_msg


@pytest.mark.respx(base_url=OPENROUTER_BASE_URL)
async def test_synthesize_gives_up_after_max_retries(respx_mock: respx.MockRouter) -> None:
    bad_payload = _llm_payload(
        sections=[
            {
                "id": "sec99",  # wrong section id
                "heading": "X",
                "body_md": "",
            }
        ]
    )
    respx_mock.post("/chat/completions").mock(
        return_value=httpx.Response(200, json=_openrouter_completion(bad_payload))
    )
    agent = ScribeAgent(model="test/model")
    with pytest.raises(ScribeValidationError, match="failed validation"):
        await agent.synthesize(
            job_id=uuid4(),
            topic="t",
            sub_questions=[],
            sources=[_source("s1")],
        )


# ---- node: events ----------------------------------------------------------


async def test_run_scribe_emits_section_drafted_then_complete() -> None:
    job_id = uuid4()
    sources = [_source("s1")]
    sections_payload = [
        {
            "id": "sec1",
            "heading": "A",
            "body_md": '<span data-claim="sec1.c1">x[^s1]</span>',
        },
        {
            "id": "sec2",
            "heading": "B",
            "body_md": '<span data-claim="sec2.c1">y[^s1]</span>',
        },
    ]

    class _StubAgent:
        model = "test/model"

        async def synthesize(
            self,
            *,
            job_id: UUID,
            topic: str,
            sub_questions: list[str],
            sources: list[Source],
        ) -> Any:
            from datetime import UTC, datetime

            from app.models.research import (
                ReportSection,
                ScribeReport,
            )

            return ScribeReport(
                id=uuid4(),
                job_id=job_id,
                topic=topic,
                title="t",
                summary_md="s",
                sections=[ReportSection(**sec) for sec in sections_payload],
                sources=sources,
                contradictions=[],
                follow_ups=[],
                generated_at=datetime.now(UTC),
                model="test/model",
            )

    captured: list[ProgressEvent] = []

    async def capture(event: ProgressEvent) -> None:
        captured.append(event)

    report = await run_scribe(
        job_id=job_id,
        topic="t",
        sub_questions=[],
        sources=sources,
        agent=_StubAgent(),  # type: ignore[arg-type]
        publish=capture,
    )

    assert len(report.sections) == 2
    section_events = [e for e in captured if isinstance(e, SectionDrafted)]
    assert [e.section.id for e in section_events] == ["sec1", "sec2"]
    assert isinstance(captured[-1], ScribeComplete)
    # SectionDrafted events come strictly before ScribeComplete.
    assert all(isinstance(e, SectionDrafted) for e in captured[:-1]), (
        f"unexpected event order: {[type(e).__name__ for e in captured]}"
    )
