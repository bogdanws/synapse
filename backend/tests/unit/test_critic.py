"""Unit tests for `CriticAgent` and the `run_critic` LangGraph node."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx
import pytest
import respx

from app.agents.critic import CriticAgent, _CriticSectionOutput
from app.agents.critic_graph import run_critic
from app.models.events import ClaimVerified, ProgressEvent
from app.models.research import (
    ClaimFlag,
    ReportSection,
    ScribeReport,
    SectionConfidence,
    Source,
    Verdict,
)
from app.services.llm import OPENROUTER_BASE_URL
from app.services.validation import CriticValidationError

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


def _section(section_id: str, claim_count: int = 1) -> ReportSection:
    spans = " ".join(
        f'<span data-claim="{section_id}.c{i + 1}">claim {i + 1}[^s1]</span>'
        for i in range(claim_count)
    )
    return ReportSection(
        id=section_id,
        heading=f"H{section_id}",
        body_md=spans,
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


def _report(sections: list[ReportSection]) -> ScribeReport:
    return ScribeReport(
        id=uuid4(),
        job_id=uuid4(),
        topic="topic",
        title="T",
        summary_md="s",
        sections=sections,
        sources=[_source("s1")],
        contradictions=[],
        follow_ups=[],
        generated_at=datetime.now(UTC),
        model="test/model",
    )


def _section_output_json(
    section_id: str,
    *,
    claim_ids: list[str],
    score: float = 0.8,
    verdict: Verdict = Verdict.SUPPORTED,
    extra_section_id: str | None = None,
) -> str:
    """Build a `_CriticSectionOutput`-shaped JSON payload."""
    confidence_section_id = extra_section_id or section_id
    payload = {
        "section_confidence": {
            "section_id": confidence_section_id,
            "score": score,
            "reasoning": "ok",
        },
        "claim_flags": [
            {
                "claim_id": cid,
                "section_id": section_id,
                "verdict": verdict.value,
                "rationale": "ok",
                "supporting_source_ids": ["s1"],
            }
            for cid in claim_ids
        ],
    }
    return json.dumps(payload)


# ---- agent: verify_section -------------------------------------------------


@pytest.mark.respx(base_url=OPENROUTER_BASE_URL)
async def test_verify_section_returns_parsed_output(respx_mock: respx.MockRouter) -> None:
    respx_mock.post("/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json=_openrouter_completion(_section_output_json("sec1", claim_ids=["sec1.c1"])),
        )
    )
    agent = CriticAgent(model="test/model")
    output = await agent.verify_section(
        topic="t",
        section=_section("sec1"),
        sources=[_source("s1")],
    )
    assert isinstance(output, _CriticSectionOutput)
    assert output.section_confidence.section_id == "sec1"
    assert [f.claim_id for f in output.claim_flags] == ["sec1.c1"]


@pytest.mark.respx(base_url=OPENROUTER_BASE_URL)
async def test_verify_section_skips_llm_for_section_without_claims(
    respx_mock: respx.MockRouter,
) -> None:
    """A section with no `<span data-claim>` has nothing to verify.

    The agent must short-circuit rather than call the model, which previously
    invented flags for non-existent claims and failed validation as
    "unknown claim_flags".
    """
    agent = CriticAgent(model="test/model")
    output = await agent.verify_section(
        topic="t",
        section=_section("sec4", claim_count=0),
        sources=[_source("s1")],
    )
    # No route is registered: any HTTP call would raise. Belt-and-braces, assert
    # the mock router saw zero requests.
    assert respx_mock.calls.call_count == 0
    assert output.section_confidence.section_id == "sec4"
    assert output.claim_flags == []


@pytest.mark.respx(base_url=OPENROUTER_BASE_URL)
async def test_verify_section_retries_on_missing_claim_flag(
    respx_mock: respx.MockRouter,
) -> None:
    bad = _section_output_json("sec1", claim_ids=[])  # no flags for the one claim
    good = _section_output_json("sec1", claim_ids=["sec1.c1"])
    route = respx_mock.post("/chat/completions").mock(
        side_effect=[
            httpx.Response(200, json=_openrouter_completion(bad)),
            httpx.Response(200, json=_openrouter_completion(good)),
        ]
    )
    agent = CriticAgent(model="test/model")
    output = await agent.verify_section(
        topic="t",
        section=_section("sec1"),
        sources=[_source("s1")],
    )
    assert route.call_count == 2
    assert [f.claim_id for f in output.claim_flags] == ["sec1.c1"]

    # The retry must replay the model's previous (bad) JSON as an assistant
    # turn followed by a corrective user turn so the model can edit its
    # mistake instead of regenerating from scratch.
    second_request = route.calls[1].request
    body = json.loads(second_request.content)
    roles = [m["role"] for m in body["messages"]]
    assert roles == ["system", "user", "assistant", "user"], roles
    # Assistant turn replays the bad payload (empty claim_flags array).
    assistant_content = body["messages"][-2]["content"]
    assert '"claim_flags": []' in assistant_content
    # Final user turn carries the targeted validation feedback.
    user_msg = body["messages"][-1]["content"]
    assert "missing claim_flags" in user_msg


@pytest.mark.respx(base_url=OPENROUTER_BASE_URL)
async def test_verify_section_gives_up_after_max_retries(
    respx_mock: respx.MockRouter,
) -> None:
    bad = _section_output_json("sec1", claim_ids=[])
    respx_mock.post("/chat/completions").mock(
        return_value=httpx.Response(200, json=_openrouter_completion(bad))
    )
    agent = CriticAgent(model="test/model")
    with pytest.raises(CriticValidationError, match="failed validation"):
        await agent.verify_section(
            topic="t",
            section=_section("sec1"),
            sources=[_source("s1")],
        )


@pytest.mark.respx(base_url=OPENROUTER_BASE_URL)
async def test_verify_section_rejects_unknown_supporting_source(
    respx_mock: respx.MockRouter,
) -> None:
    payload = json.dumps(
        {
            "section_confidence": {
                "section_id": "sec1",
                "score": 0.8,
                "reasoning": "ok",
            },
            "claim_flags": [
                {
                    "claim_id": "sec1.c1",
                    "section_id": "sec1",
                    "verdict": "supported",
                    "rationale": "ok",
                    "supporting_source_ids": ["s99"],
                }
            ],
        }
    )
    respx_mock.post("/chat/completions").mock(
        return_value=httpx.Response(200, json=_openrouter_completion(payload))
    )
    agent = CriticAgent(model="test/model")
    with pytest.raises(CriticValidationError, match="unknown sources"):
        await agent.verify_section(
            topic="t",
            section=_section("sec1"),
            sources=[_source("s1")],
        )


# ---- agent: aggregate ------------------------------------------------------


def test_aggregate_orders_results_by_section_index_regardless_of_input_order() -> None:
    report = _report([_section("sec1"), _section("sec2"), _section("sec3")])
    # Provide outputs in scrambled order; aggregation should sort them.
    outputs = [
        _CriticSectionOutput(
            section_confidence=SectionConfidence(section_id="sec3", score=0.9, reasoning="r"),
            claim_flags=[
                ClaimFlag(
                    claim_id="sec3.c1",
                    section_id="sec3",
                    verdict=Verdict.SUPPORTED,
                    rationale="r",
                    supporting_source_ids=["s1"],
                )
            ],
        ),
        _CriticSectionOutput(
            section_confidence=SectionConfidence(section_id="sec1", score=0.7, reasoning="r"),
            claim_flags=[
                ClaimFlag(
                    claim_id="sec1.c1",
                    section_id="sec1",
                    verdict=Verdict.SUPPORTED,
                    rationale="r",
                    supporting_source_ids=["s1"],
                )
            ],
        ),
        _CriticSectionOutput(
            section_confidence=SectionConfidence(section_id="sec2", score=0.8, reasoning="r"),
            claim_flags=[
                ClaimFlag(
                    claim_id="sec2.c1",
                    section_id="sec2",
                    verdict=Verdict.SUPPORTED,
                    rationale="r",
                    supporting_source_ids=["s1"],
                )
            ],
        ),
    ]
    agent = CriticAgent(model="test/model")
    annotations = agent.aggregate(report, outputs)
    assert [c.section_id for c in annotations.section_confidence] == [
        "sec1",
        "sec2",
        "sec3",
    ]
    assert [f.claim_id for f in annotations.claim_flags] == [
        "sec1.c1",
        "sec2.c1",
        "sec3.c1",
    ]
    # Mean of 0.7, 0.8, 0.9 = 0.8.
    assert annotations.overall_confidence == pytest.approx(0.8)


def test_aggregate_runs_global_validator() -> None:
    report = _report([_section("sec1")])
    # Section confidence references a section the report doesn't have — global
    # validator must catch this even when per-section validation passed earlier.
    bad_output = _CriticSectionOutput(
        section_confidence=SectionConfidence(section_id="sec99", score=0.9, reasoning="r"),
        claim_flags=[
            ClaimFlag(
                claim_id="sec1.c1",
                section_id="sec1",
                verdict=Verdict.SUPPORTED,
                rationale="r",
                supporting_source_ids=["s1"],
            )
        ],
    )
    agent = CriticAgent(model="test/model")
    with pytest.raises(CriticValidationError):
        agent.aggregate(report, [bad_output])


# ---- node: events ----------------------------------------------------------


class _StubAgent:
    """Records inputs and returns canned per-section outputs."""

    model = "test/model"

    def __init__(self, outputs_by_section: dict[str, _CriticSectionOutput]) -> None:
        self._outputs = outputs_by_section
        self.calls: list[str] = []

    async def verify_section(
        self,
        *,
        topic: str,
        section: ReportSection,
        sources: list[Source],
    ) -> _CriticSectionOutput:
        self.calls.append(section.id)
        return self._outputs[section.id]

    def aggregate(
        self,
        report: ScribeReport,
        section_outputs: list[_CriticSectionOutput],
    ) -> Any:
        # Delegate to the real agent for aggregation so the global validator
        # still runs end-to-end in the node test.
        return CriticAgent(self.model).aggregate(report, section_outputs)


def _output(section_id: str, claim_count: int = 1) -> _CriticSectionOutput:
    return _CriticSectionOutput(
        section_confidence=SectionConfidence(section_id=section_id, score=0.8, reasoning="r"),
        claim_flags=[
            ClaimFlag(
                claim_id=f"{section_id}.c{i + 1}",
                section_id=section_id,
                verdict=Verdict.SUPPORTED,
                rationale="r",
                supporting_source_ids=["s1"],
            )
            for i in range(claim_count)
        ],
    )


async def test_run_critic_emits_claim_verified_for_every_flag() -> None:
    job_id = uuid4()
    report = _report([_section("sec1", 2), _section("sec2", 1)])
    agent = _StubAgent(
        {
            "sec1": _output("sec1", 2),
            "sec2": _output("sec2", 1),
        }
    )

    captured: list[ProgressEvent] = []

    async def capture(event: ProgressEvent) -> None:
        captured.append(event)

    annotations = await run_critic(
        job_id=job_id,
        report=report,
        agent=agent,  # type: ignore[arg-type]
        publish=capture,
    )

    flag_events = [e for e in captured if isinstance(e, ClaimVerified)]
    assert len(flag_events) == 3
    assert {e.flag.claim_id for e in flag_events} == {"sec1.c1", "sec1.c2", "sec2.c1"}
    assert len(annotations.claim_flags) == 3
    assert annotations.overall_confidence == pytest.approx(0.8)


async def test_run_critic_streams_events_as_sections_complete() -> None:
    """Faster-completing sections should yield ClaimVerified events before slower ones."""
    job_id = uuid4()
    report = _report([_section("sec1"), _section("sec2")])

    class _SlowFastAgent:
        model = "test/model"

        async def verify_section(
            self,
            *,
            topic: str,
            section: ReportSection,
            sources: list[Source],
        ) -> _CriticSectionOutput:
            if section.id == "sec1":
                # Long enough to ensure sec2 completes first under any
                # reasonable scheduler.
                await asyncio.sleep(0.05)
            return _output(section.id)

        def aggregate(
            self, report: ScribeReport, section_outputs: list[_CriticSectionOutput]
        ) -> Any:
            return CriticAgent(self.model).aggregate(report, section_outputs)

    captured: list[ProgressEvent] = []

    async def capture(event: ProgressEvent) -> None:
        captured.append(event)

    await run_critic(
        job_id=job_id,
        report=report,
        agent=_SlowFastAgent(),  # type: ignore[arg-type]
        publish=capture,
    )

    flag_events = [e for e in captured if isinstance(e, ClaimVerified)]
    # sec2 completes first because sec1 sleeps. The streaming behaviour is the
    # whole point of using as_completed in the node, so this regression test
    # is worth the small sleep.
    assert flag_events[0].flag.claim_id == "sec2.c1"
    assert flag_events[1].flag.claim_id == "sec1.c1"


async def test_run_critic_cancels_pending_sections_on_failure() -> None:
    """If one section fails, in-flight siblings should be cancelled rather than leaked."""
    job_id = uuid4()
    report = _report([_section("sec1"), _section("sec2")])
    sec2_started = asyncio.Event()
    sec2_cancelled = asyncio.Event()

    class _FailingAgent:
        model = "test/model"

        async def verify_section(
            self,
            *,
            topic: str,
            section: ReportSection,
            sources: list[Source],
        ) -> _CriticSectionOutput:
            if section.id == "sec1":
                raise RuntimeError("boom")
            sec2_started.set()
            try:
                await asyncio.sleep(5.0)
            except asyncio.CancelledError:
                sec2_cancelled.set()
                raise
            return _output(section.id)

        def aggregate(
            self, report: ScribeReport, section_outputs: list[_CriticSectionOutput]
        ) -> Any:
            raise AssertionError("aggregate should not run when a section fails")

    with pytest.raises(RuntimeError, match="boom"):
        await run_critic(
            job_id=job_id,
            report=report,
            agent=_FailingAgent(),  # type: ignore[arg-type]
            publish=_noop,
        )

    assert sec2_started.is_set()
    assert sec2_cancelled.is_set()


async def _noop(_event: ProgressEvent) -> None:
    return None
