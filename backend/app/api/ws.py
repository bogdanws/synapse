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
from pydantic import TypeAdapter

from app.config import get_settings
from app.models.events import JobSnapshot, ProgressEvent
from app.services import events as events_service

router = APIRouter()

_settings = get_settings()
_log = structlog.get_logger(__name__)

# fastapi-users mints tokens with this audience; matching here means a token issued for a different purpose (e.g. password reset) cannot authenticate the WebSocket.
_JWT_AUDIENCE = ["fastapi-users:auth"]

# Event types after which the server hangs up cleanly. Letting the client know "no more events are coming" is more useful than a silent idle connection.
_TERMINAL_EVENT_TYPES = frozenset({"job_completed", "job_failed"})


def _user_id_from_cookie(token: str | None) -> str | None:
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
    return sub if isinstance(sub, str) and sub else None


@router.websocket("/ws/jobs/{job_id}")
async def jobs_ws(websocket: WebSocket, job_id: UUID) -> None:
    user_id = _user_id_from_cookie(websocket.cookies.get("synapse_auth"))
    if user_id is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    log = _log.bind(job_id=str(job_id), user_id=user_id)

    try:
        # Snapshot first so a client that connected mid-pipeline has context.
        await websocket.send_text(JobSnapshot(job_id=job_id).model_dump_json())
        async with events_service.subscribe(job_id) as stream:
            async for event in stream:
                await websocket.send_text(event.model_dump_json())
                if event.type in _TERMINAL_EVENT_TYPES:
                    break
    except WebSocketDisconnect:
        log.info("jobs_ws_client_disconnect")
    finally:
        # Best-effort close; ignored if the socket is already gone.
        with suppress(RuntimeError):
            await websocket.close()


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

    OpenAPI 3.x doesn't describe WebSocket routes;
    Instead we publish the message types under `components.schemas` so the frontend's codegen produces typed WS payloads with no drift risk.
    The runtime WS handler still validates incoming JSON via the same Pydantic models, so the boundary stays guarded
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
