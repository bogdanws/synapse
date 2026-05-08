"""Tests for the /ws/jobs/{job_id} WebSocket bridge."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.config import get_settings
from app.main import app
from app.models.events import JobCompleted, ProgressEvent, SubQuestionsGenerated
from app.services import events as events_service

JWT_AUDIENCE = "fastapi-users:auth"


def _mint_cookie(user_id: str | None = None) -> str:
    """Mint a token shaped like fastapi-users' so the WS handler accepts it."""
    return jwt.encode(
        {"sub": user_id or str(uuid4()), "aud": JWT_AUDIENCE},
        get_settings().jwt_secret,
        algorithm="HS256",
    )


def _patch_subscribe(monkeypatch: pytest.MonkeyPatch, events: list[ProgressEvent]) -> None:
    @asynccontextmanager
    async def _fake_subscribe(_job_id: UUID) -> AsyncIterator[AsyncIterator[ProgressEvent]]:
        async def _iter() -> AsyncIterator[ProgressEvent]:
            for event in events:
                yield event

        yield _iter()

    monkeypatch.setattr(events_service, "subscribe", _fake_subscribe)


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
    user_id = str(uuid4())
    events: list[ProgressEvent] = [
        SubQuestionsGenerated(
            job_id=job_id,
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            sub_questions=["q1", "q2"],
        ),
        JobCompleted(
            job_id=job_id,
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            overall_confidence=0.9,
        ),
    ]
    _patch_subscribe(monkeypatch, events)

    client = TestClient(app)
    client.cookies.set("synapse_auth", _mint_cookie(user_id))

    with client.websocket_connect(f"/ws/jobs/{job_id}") as ws:
        snapshot = json.loads(ws.receive_text())
        assert snapshot == {
            "type": "snapshot",
            "job_id": str(job_id),
            "job": None,
        }

        first = json.loads(ws.receive_text())
        assert first["type"] == "sub_questions_generated"
        assert first["sub_questions"] == ["q1", "q2"]

        last = json.loads(ws.receive_text())
        assert last["type"] == "job_completed"
        assert last["overall_confidence"] == 0.9

        # Server hangs up after a terminal event so the client can move on.
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
    user_id = str(uuid4())
    events: list[ProgressEvent] = [
        JobCompleted(
            job_id=job_id,
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            overall_confidence=0.5,
        ),
        # Sentinel that should never reach the wire because the prior event was terminal.
        SubQuestionsGenerated(
            job_id=job_id,
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            sub_questions=["should-not-arrive"],
        ),
    ]
    _patch_subscribe(monkeypatch, events)

    client = TestClient(app)
    client.cookies.set("synapse_auth", _mint_cookie(user_id))

    with client.websocket_connect(f"/ws/jobs/{job_id}") as ws:
        ws.receive_text()  # snapshot
        terminal = json.loads(ws.receive_text())
        assert terminal["type"] == "job_completed"
        with pytest.raises(WebSocketDisconnect):
            ws.receive_text()
