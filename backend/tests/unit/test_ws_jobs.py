"""Tests for the /ws/jobs/{job_id} WebSocket bridge."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from limits import parse
from starlette.websockets import WebSocketDisconnect

from app.api import ws as ws_api
from app.config import get_settings
from app.main import app
from app.models.events import (
    JobCompleted,
    ProgressEvent,
    SectionDrafted,
    SubQuestionsGenerated,
)
from app.models.research import JobStatus, ReportSection, ResearchJob
from app.services import events as events_service
from app.services.persistence import JobNotFoundError, JobRepository

JWT_AUDIENCE = "fastapi-users:auth"


def _mint_cookie(user_id: str | None = None) -> str:
    """Mint a token shaped like fastapi-users' so the WS handler accepts it."""
    return jwt.encode(
        {"sub": user_id or str(uuid4()), "aud": JWT_AUDIENCE},
        get_settings().jwt_secret,
        algorithm="HS256",
    )


@pytest.fixture(autouse=True)
def _stub_session_factory(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    session_events: list[str] = []

    class _FakeSessionContext:
        async def __aenter__(self) -> object:
            session_events.append("open")
            return object()

        async def __aexit__(self, *_exc: object) -> None:
            session_events.append("closed")

    monkeypatch.setattr(ws_api, "async_session_factory", _FakeSessionContext)
    yield session_events


def _patch_subscribe(
    monkeypatch: pytest.MonkeyPatch,
    live_events: list[tuple[int, ProgressEvent]],
) -> None:
    """Stub the live-stream side of `events_service.subscribe`.

    Yields `(id, event)` tuples just like the real implementation so the WS
    handler's dedupe-by-id branch is actually exercised.
    """

    @asynccontextmanager
    async def _fake_subscribe(
        _job_id: UUID,
    ) -> AsyncIterator[AsyncIterator[tuple[int, ProgressEvent]]]:
        async def _iter() -> AsyncIterator[tuple[int, ProgressEvent]]:
            for entry in live_events:
                yield entry

        yield _iter()

    monkeypatch.setattr(events_service, "subscribe", _fake_subscribe)


def _patch_load_history(
    monkeypatch: pytest.MonkeyPatch,
    history: list[tuple[int, ProgressEvent]],
) -> None:
    async def _fake_load_history(_job_id: UUID) -> list[tuple[int, ProgressEvent]]:
        return list(history)

    monkeypatch.setattr(events_service, "load_history", _fake_load_history)


def _patch_job(
    monkeypatch: pytest.MonkeyPatch,
    job: ResearchJob | None,
    seen: list[dict[str, UUID | None]] | None = None,
) -> None:
    async def _fake_get_job(
        _self: JobRepository,
        job_id: UUID,
        *,
        user_id: UUID | None = None,
    ) -> ResearchJob:
        if seen is not None:
            seen.append({"job_id": job_id, "user_id": user_id})
        if job is None:
            msg = f"research job {job_id} not found"
            raise JobNotFoundError(msg)
        return job

    monkeypatch.setattr(JobRepository, "get_job", _fake_get_job)


def test_ws_rejects_when_cookie_missing() -> None:
    client = TestClient(app)
    with (
        pytest.raises(WebSocketDisconnect) as excinfo,
        client.websocket_connect(f"/ws/jobs/{uuid4()}"),
    ):
        pass
    # 1008 = policy violation; what the handler emits on bad/missing auth.
    assert excinfo.value.code == 1008


def test_ws_rejects_invalid_jwt() -> None:
    client = TestClient(app)
    client.cookies.set("synapse_auth", "not-a-real-jwt")
    with (
        pytest.raises(WebSocketDisconnect) as excinfo,
        client.websocket_connect(f"/ws/jobs/{uuid4()}"),
    ):
        pass
    assert excinfo.value.code == 1008


def test_ws_rejects_jwt_with_wrong_audience() -> None:
    bad = jwt.encode(
        {"sub": str(uuid4()), "aud": "some-other-audience"},
        get_settings().jwt_secret,
        algorithm="HS256",
    )
    client = TestClient(app)
    client.cookies.set("synapse_auth", bad)
    with (
        pytest.raises(WebSocketDisconnect) as excinfo,
        client.websocket_connect(f"/ws/jobs/{uuid4()}"),
    ):
        pass
    assert excinfo.value.code == 1008


def test_ws_sends_snapshot_then_relays_events(monkeypatch: pytest.MonkeyPatch) -> None:
    job_id = uuid4()
    user_id = uuid4()
    job = ResearchJob(
        id=job_id,
        topic="Should cities ban cars downtown?",
        models={"scout": "m1", "scribe": "m2", "critic": "m3"},
        status=JobStatus.SCOUTING,
        progress=0.4,
    )
    seen: list[dict[str, UUID | None]] = []
    live_events: list[tuple[int, ProgressEvent]] = [
        (
            1,
            SubQuestionsGenerated(
                job_id=job_id,
                timestamp=datetime(2026, 1, 1, tzinfo=UTC),
                sub_questions=["q1", "q2"],
            ),
        ),
        (
            2,
            JobCompleted(
                job_id=job_id,
                timestamp=datetime(2026, 1, 1, tzinfo=UTC),
                overall_confidence=0.9,
            ),
        ),
    ]
    _patch_job(monkeypatch, job, seen)
    _patch_load_history(monkeypatch, [])
    _patch_subscribe(monkeypatch, live_events)

    client = TestClient(app)
    client.cookies.set("synapse_auth", _mint_cookie(str(user_id)))

    with client.websocket_connect(f"/ws/jobs/{job_id}") as ws:
        snapshot = json.loads(ws.receive_text())
        assert snapshot["type"] == "snapshot"
        assert snapshot["job_id"] == str(job_id)
        assert snapshot["job"]["id"] == str(job_id)
        assert snapshot["job"]["topic"] == "Should cities ban cars downtown?"
        assert snapshot["job"]["progress"] == 0.4
        assert seen == [{"job_id": job_id, "user_id": user_id}]

        first = json.loads(ws.receive_text())
        assert first["type"] == "sub_questions_generated"
        assert first["sub_questions"] == ["q1", "q2"]

        last = json.loads(ws.receive_text())
        assert last["type"] == "job_completed"
        assert last["overall_confidence"] == 0.9

        # Server hangs up after a terminal event so the client can move on.
        with pytest.raises(WebSocketDisconnect):
            ws.receive_text()


def test_ws_closes_auth_session_before_stream_work(
    monkeypatch: pytest.MonkeyPatch,
    _stub_session_factory: list[str],
) -> None:
    job_id = uuid4()
    job = ResearchJob(
        id=job_id,
        topic="Connection lifecycle test",
        models={"scout": "m1", "scribe": "m2", "critic": "m3"},
        status=JobStatus.SCOUTING,
    )
    _patch_job(monkeypatch, job)
    _patch_load_history(monkeypatch, [])

    @asynccontextmanager
    async def _fake_subscribe(
        _job_id: UUID,
    ) -> AsyncIterator[AsyncIterator[tuple[int, ProgressEvent]]]:
        assert _stub_session_factory == ["open", "closed"]

        async def _iter() -> AsyncIterator[tuple[int, ProgressEvent]]:
            yield (
                1,
                JobCompleted(
                    job_id=job_id,
                    timestamp=datetime(2026, 1, 1, tzinfo=UTC),
                    overall_confidence=0.8,
                ),
            )

        yield _iter()

    monkeypatch.setattr(events_service, "subscribe", _fake_subscribe)

    client = TestClient(app)
    client.cookies.set("synapse_auth", _mint_cookie())

    with client.websocket_connect(f"/ws/jobs/{job_id}") as ws:
        assert json.loads(ws.receive_text())["type"] == "snapshot"
        assert json.loads(ws.receive_text())["type"] == "job_completed"
        with pytest.raises(WebSocketDisconnect):
            ws.receive_text()


def test_ws_replays_persisted_history_before_attaching_to_live(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A client connecting mid-run must receive every prior event.

    This is the page-refresh use case: the user reloads while Scout is still
    running, and instead of an empty progress UI they should see every
    sub-question, source, and section that has been produced so far.
    """
    job_id = uuid4()
    job = ResearchJob(
        id=job_id,
        topic="Mid-run reconnect",
        models={"scout": "m1", "scribe": "m2", "critic": "m3"},
        status=JobStatus.SYNTHESIZING,
    )

    persisted: list[tuple[int, ProgressEvent]] = [
        (
            10,
            SubQuestionsGenerated(
                job_id=job_id,
                timestamp=datetime(2026, 1, 1, tzinfo=UTC),
                sub_questions=["sub-q-1", "sub-q-2"],
            ),
        ),
        (
            11,
            SectionDrafted(
                job_id=job_id,
                timestamp=datetime(2026, 1, 1, tzinfo=UTC),
                section=ReportSection(
                    id="sec-1",
                    heading="Background",
                    body_md="Lorem ipsum",
                ),
            ),
        ),
    ]
    live: list[tuple[int, ProgressEvent]] = [
        (
            12,
            SectionDrafted(
                job_id=job_id,
                timestamp=datetime(2026, 1, 1, tzinfo=UTC),
                section=ReportSection(
                    id="sec-2",
                    heading="Analysis",
                    body_md="More lorem",
                ),
            ),
        ),
        (
            13,
            JobCompleted(
                job_id=job_id,
                timestamp=datetime(2026, 1, 1, tzinfo=UTC),
                overall_confidence=0.8,
            ),
        ),
    ]
    _patch_job(monkeypatch, job)
    _patch_load_history(monkeypatch, persisted)
    _patch_subscribe(monkeypatch, live)

    client = TestClient(app)
    client.cookies.set("synapse_auth", _mint_cookie())

    with client.websocket_connect(f"/ws/jobs/{job_id}") as ws:
        assert json.loads(ws.receive_text())["type"] == "snapshot"

        # Replayed history (id=10, id=11) comes first, in order.
        replay_first = json.loads(ws.receive_text())
        assert replay_first["type"] == "sub_questions_generated"
        replay_second = json.loads(ws.receive_text())
        assert replay_second["type"] == "section_drafted"
        assert replay_second["section"]["id"] == "sec-1"

        # Then the live tail (id=12 then id=13).
        live_first = json.loads(ws.receive_text())
        assert live_first["type"] == "section_drafted"
        assert live_first["section"]["id"] == "sec-2"

        terminal = json.loads(ws.receive_text())
        assert terminal["type"] == "job_completed"

        with pytest.raises(WebSocketDisconnect):
            ws.receive_text()


def test_ws_drops_live_frames_already_seen_via_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Race window: a frame can land in both the DB replay and the live tail.

    redis-py pubsub starts buffering on `subscribe()`; if an event is
    published while the WS handler is still issuing the DB SELECT, that
    event appears both in the persisted history and in the pubsub buffer.
    The handler must drop the duplicate using the id watermark.
    """
    job_id = uuid4()
    job = ResearchJob(
        id=job_id,
        topic="Race window dedupe",
        models={"scout": "m1", "scribe": "m2", "critic": "m3"},
        status=JobStatus.SYNTHESIZING,
    )

    shared_event = SubQuestionsGenerated(
        job_id=job_id,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        sub_questions=["only-once"],
    )
    # Same id in both lists — the live frame must be suppressed.
    _patch_job(monkeypatch, job)
    _patch_load_history(monkeypatch, [(5, shared_event)])
    _patch_subscribe(
        monkeypatch,
        [
            (5, shared_event),
            (
                6,
                JobCompleted(
                    job_id=job_id,
                    timestamp=datetime(2026, 1, 1, tzinfo=UTC),
                    overall_confidence=0.5,
                ),
            ),
        ],
    )

    client = TestClient(app)
    client.cookies.set("synapse_auth", _mint_cookie())

    with client.websocket_connect(f"/ws/jobs/{job_id}") as ws:
        assert json.loads(ws.receive_text())["type"] == "snapshot"
        replay = json.loads(ws.receive_text())
        assert replay["type"] == "sub_questions_generated"
        # The live duplicate (id=5) must NOT be the next frame; the next
        # frame is the terminal event (id=6).
        terminal = json.loads(ws.receive_text())
        assert terminal["type"] == "job_completed"


def test_ws_closes_after_replaying_terminal_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A reconnect after a job ends sees the terminal event in the replay.

    The handler must stop after replaying it instead of falling through to
    the live tail, which would otherwise dispatch the events queued in the
    fake subscriber.
    """
    job_id = uuid4()
    job = ResearchJob(
        id=job_id,
        topic="Replay terminal",
        models={"scout": "m1", "scribe": "m2", "critic": "m3"},
        status=JobStatus.COMPLETED,
    )
    persisted: list[tuple[int, ProgressEvent]] = [
        (
            1,
            JobCompleted(
                job_id=job_id,
                timestamp=datetime(2026, 1, 1, tzinfo=UTC),
                overall_confidence=0.5,
            ),
        ),
    ]
    # If the live stream is consulted, this sentinel will reach the client —
    # which would mean the handler skipped the early-return after the
    # terminal replay.
    live: list[tuple[int, ProgressEvent]] = [
        (
            2,
            SubQuestionsGenerated(
                job_id=job_id,
                timestamp=datetime(2026, 1, 1, tzinfo=UTC),
                sub_questions=["should-not-arrive"],
            ),
        ),
    ]
    _patch_job(monkeypatch, job)
    _patch_load_history(monkeypatch, persisted)
    _patch_subscribe(monkeypatch, live)

    client = TestClient(app)
    client.cookies.set("synapse_auth", _mint_cookie())

    with client.websocket_connect(f"/ws/jobs/{job_id}") as ws:
        assert json.loads(ws.receive_text())["type"] == "snapshot"
        terminal = json.loads(ws.receive_text())
        assert terminal["type"] == "job_completed"
        with pytest.raises(WebSocketDisconnect):
            ws.receive_text()


def test_ws_closes_when_job_terminal_and_history_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reconnect after cleanup_for_job leaves the table empty.

    The user's chosen retention policy is "delete on completion": once the
    orchestrator publishes the terminal event it drops the persisted log.
    A client reconnecting after that should still get a clean snapshot and
    a prompt close — not hang forever waiting on a dead pubsub channel.
    """
    job_id = uuid4()
    job = ResearchJob(
        id=job_id,
        topic="Post-cleanup reconnect",
        models={"scout": "m1", "scribe": "m2", "critic": "m3"},
        status=JobStatus.COMPLETED,
        progress=1.0,
    )
    _patch_job(monkeypatch, job)
    _patch_load_history(monkeypatch, [])
    # Live stream contains nothing — Redis pub/sub is fire-and-forget; once
    # the publisher is gone there is nothing to receive.
    _patch_subscribe(monkeypatch, [])

    client = TestClient(app)
    client.cookies.set("synapse_auth", _mint_cookie())

    with client.websocket_connect(f"/ws/jobs/{job_id}") as ws:
        snapshot = json.loads(ws.receive_text())
        assert snapshot["type"] == "snapshot"
        assert snapshot["job"]["status"] == JobStatus.COMPLETED.value
        # Bridge must close on its own; the frontend's snapshot-based redirect
        # will take it from here.
        with pytest.raises(WebSocketDisconnect):
            ws.receive_text()


def test_openapi_includes_ws_message_schemas() -> None:
    """The frontend codegen pulls types from components.schemas.

    OpenAPI doesn't model WS routes, so we publish the payload schemas under components and let the existing pipeline produce TS types for them.
    """
    client = TestClient(app)
    schema = client.get("/openapi.json").json()
    components = schema["components"]["schemas"]
    assert "JobSnapshot" in components
    assert "ProgressEvent" in components
    # Spot-check that variant types come along too so `oneOf` refs resolve.
    assert "JobCompleted" in components
    assert "SubQuestionsGenerated" in components


def test_ws_stops_relaying_after_terminal_event(monkeypatch: pytest.MonkeyPatch) -> None:
    job_id = uuid4()
    user_id = uuid4()
    job = ResearchJob(
        id=job_id,
        topic="Terminal event test",
        models={"scout": "m1", "scribe": "m2", "critic": "m3"},
        status=JobStatus.SCOUTING,
    )
    live: list[tuple[int, ProgressEvent]] = [
        (
            1,
            JobCompleted(
                job_id=job_id,
                timestamp=datetime(2026, 1, 1, tzinfo=UTC),
                overall_confidence=0.5,
            ),
        ),
        # Sentinel that should never reach the wire because the prior event was terminal.
        (
            2,
            SubQuestionsGenerated(
                job_id=job_id,
                timestamp=datetime(2026, 1, 1, tzinfo=UTC),
                sub_questions=["should-not-arrive"],
            ),
        ),
    ]
    _patch_job(monkeypatch, job)
    _patch_load_history(monkeypatch, [])
    _patch_subscribe(monkeypatch, live)

    client = TestClient(app)
    client.cookies.set("synapse_auth", _mint_cookie(str(user_id)))

    with client.websocket_connect(f"/ws/jobs/{job_id}") as ws:
        ws.receive_text()  # snapshot
        terminal = json.loads(ws.receive_text())
        assert terminal["type"] == "job_completed"
        with pytest.raises(WebSocketDisconnect):
            ws.receive_text()


def test_ws_rejects_unknown_or_unauthorized_job(monkeypatch: pytest.MonkeyPatch) -> None:
    job_id = uuid4()
    _patch_job(monkeypatch, None)

    client = TestClient(app)
    client.cookies.set("synapse_auth", _mint_cookie(str(uuid4())))

    with (
        pytest.raises(WebSocketDisconnect) as excinfo,
        client.websocket_connect(f"/ws/jobs/{job_id}"),
    ):
        pass
    assert excinfo.value.code == 1008


def test_ws_rate_limits_connection_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    job_id = uuid4()
    user_id = uuid4()
    _patch_job(monkeypatch, None)
    monkeypatch.setattr(ws_api, "_WS_CONNECT_LIMIT", parse("1/minute"))

    client = TestClient(app)
    client.cookies.set("synapse_auth", _mint_cookie(str(user_id)))

    with (
        pytest.raises(WebSocketDisconnect) as first,
        client.websocket_connect(f"/ws/jobs/{job_id}"),
    ):
        pass
    assert first.value.code == 1008

    with (
        pytest.raises(WebSocketDisconnect) as second,
        client.websocket_connect(f"/ws/jobs/{job_id}"),
    ):
        pass
    assert second.value.code == 1013
