"""WebSocket bridge between Redis pubsub and connected clients.

Authentication piggybacks on the same `synapse_auth` cookie used for HTTP:
the browser forwards it on the WS handshake, the handler decodes the JWT
with `JWT_SECRET`, and rejects the connection on missing/expired/forged
tokens. There is no bearer transport for WebSockets.
"""

from __future__ import annotations

from contextlib import suppress
from typing import Any
from uuid import UUID

import jwt
import structlog
from fastapi import APIRouter, FastAPI, WebSocket, WebSocketDisconnect, status
from fastapi.openapi.utils import get_openapi
from limits import parse
from pydantic import TypeAdapter

from app.config import get_settings
from app.db.session import async_session_factory
from app.middleware.ratelimit import limiter
from app.models.events import JobSnapshot, ProgressEvent
from app.models.research import JobStatus, ResearchJob
from app.services import events as events_service
from app.services.persistence import JobNotFoundError, JobRepository

router = APIRouter()

_settings = get_settings()
_log = structlog.get_logger(__name__)

# fastapi-users mints tokens with this audience; matching here means a token issued for a different purpose (e.g. password reset) cannot authenticate the WebSocket.
_JWT_AUDIENCE = ["fastapi-users:auth"]

# Event types after which the server hangs up cleanly. Letting the client know "no more events are coming" is more useful than a silent idle connection.
_TERMINAL_EVENT_TYPES = frozenset({"job_completed", "job_failed"})

# Job statuses for which no further events will ever be published. A client
# reconnecting after `cleanup_for_job` has run sees an empty replay; rather
# than blocking forever on a dead pub/sub channel, the bridge closes after
# the snapshot so the redirect-to-report logic in the frontend can fire.
_TERMINAL_JOB_STATUSES = frozenset({JobStatus.COMPLETED, JobStatus.FAILED})

_WS_CONNECT_LIMIT = parse("30/minute")


def _user_id_from_cookie(token: str | None) -> UUID | None:
    if not token:
        return None
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            _settings.jwt_secret,
            algorithms=["HS256"],
            audience=_JWT_AUDIENCE,
        )
    except jwt.PyJWTError:
        return None
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        return None
    try:
        return UUID(sub)
    except ValueError:
        return None


def _rate_limit_key(websocket: WebSocket, user_id: UUID | None) -> str:
    if user_id is not None:
        return f"user:{user_id}"
    if websocket.client is not None:
        return f"ip:{websocket.client.host}"
    return "ip:unknown"


def _ws_rate_limit_exceeded(websocket: WebSocket, user_id: UUID | None) -> bool:
    if not limiter.enabled:
        return False
    return not limiter.limiter.hit(
        _WS_CONNECT_LIMIT, "ws.jobs", _rate_limit_key(websocket, user_id)
    )


@router.websocket("/ws/jobs/{job_id}")
async def jobs_ws(
    websocket: WebSocket,
    job_id: UUID,
) -> None:
    user_id = _user_id_from_cookie(websocket.cookies.get("synapse_auth"))
    if _ws_rate_limit_exceeded(websocket, user_id):
        await websocket.close(code=status.WS_1013_TRY_AGAIN_LATER)
        return
    if user_id is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    job = await _get_authorized_job(job_id, user_id)
    if job is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    log = _log.bind(job_id=str(job_id), user_id=user_id)

    try:
        # Snapshot first so a client that connected mid-pipeline has context.
        await websocket.send_text(JobSnapshot(job_id=job_id, job=job).model_dump_json())

        # Subscribe to the live channel *before* querying persisted history.
        # redis-py buffers messages received on a subscribed pubsub object,
        # so any event published while we read the DB will be delivered
        # below once we drain the iterator. We then dedupe replayed-vs-live
        # frames by id so neither path can double-deliver.
        async with events_service.subscribe(job_id) as live_stream:
            max_replayed_id = 0
            replayed_terminal = False
            for event_id, event in await events_service.load_history(job_id):
                await websocket.send_text(event.model_dump_json())
                max_replayed_id = event_id
                if event.type in _TERMINAL_EVENT_TYPES:
                    replayed_terminal = True
                    break

            if replayed_terminal:
                return

            # If the job has already terminated but cleanup_for_job removed
            # the terminal event, no further events will ever arrive on the
            # pubsub channel. Closing here lets the frontend's snapshot-based
            # redirect take over instead of hanging on a dead stream.
            if job.status in _TERMINAL_JOB_STATUSES:
                return

            async for event_id, event in live_stream:
                if event_id <= max_replayed_id:
                    # Already delivered via the DB replay; drop the duplicate.
                    continue
                await websocket.send_text(event.model_dump_json())
                if event.type in _TERMINAL_EVENT_TYPES:
                    break
    except WebSocketDisconnect:
        log.info("jobs_ws_client_disconnect")
    finally:
        # Best-effort close; ignored if the socket is already gone.
        with suppress(RuntimeError):
            await websocket.close()


async def _get_authorized_job(job_id: UUID, user_id: UUID) -> ResearchJob | None:
    async with async_session_factory() as session:
        try:
            return await JobRepository(session).get_job(job_id, user_id=user_id)
        except JobNotFoundError:
            return None


def _ws_payload_schemas() -> dict[str, dict[str, Any]]:
    """Render the WS message types as JSON Schema with components-style refs.

    Pydantic always emits the discriminator (`type`) on the wire — it has a default value, so in standard JSON Schema generation it appears as a non-required property. That weakens the generated TS union (every variant's `type` becomes optional), which in turn defeats exhaustiveness checks on the consumer side. We post-process each variant schema to mark `type` required wherever it has a `const`.
    """
    out: dict[str, dict[str, Any]] = {}
    for name, root in (
        (
            "ProgressEvent",
            TypeAdapter(ProgressEvent).json_schema(
                ref_template="#/components/schemas/{model}",
            ),
        ),
        (
            "JobSnapshot",
            JobSnapshot.model_json_schema(
                ref_template="#/components/schemas/{model}",
            ),
        ),
    ):
        _force_const_type_required(root)
        for nested_name, nested_schema in root.pop("$defs", {}).items():
            _force_const_type_required(nested_schema)
            out.setdefault(nested_name, nested_schema)
        out[name] = root
    return out


def _force_const_type_required(schema: dict[str, Any]) -> None:
    """Mark a schema's `type` discriminator required when it's a const value."""
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return
    type_prop = properties.get("type")
    if not isinstance(type_prop, dict) or "const" not in type_prop:
        return
    required = schema.setdefault("required", [])
    if "type" not in required:
        required.append("type")


def register_ws_schemas(app: FastAPI) -> None:
    """Surface WS message schemas in the OpenAPI components store.

    OpenAPI 3.x doesn't describe WebSocket routes. We publish the message types under `components.schemas` so the frontend's codegen produces typed WS payloads with no drift risk.
    The server only sends on this socket; inbound validation (Redis -> Pydantic) happens inside `events_service.subscribe`.
    """

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        components = schema.setdefault("components", {}).setdefault("schemas", {})
        for name, defn in _ws_payload_schemas().items():
            components.setdefault(name, defn)
        app.openapi_schema = schema
        return schema

    # FastAPI documents overriding `app.openapi` for spec customisation. mypy flags reassigning a bound method; the override is the supported pattern.
    app.openapi = custom_openapi  # type: ignore[method-assign]
