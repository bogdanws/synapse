"""FastAPI application entry point."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app import __version__
from app.api.routes import router as api_router
from app.api.ws import register_ws_schemas
from app.api.ws import router as ws_router
from app.auth.routes import router as auth_router
from app.config import get_settings
from app.logging import RequestIDMiddleware, configure_logging
from app.middleware.ratelimit import limiter
from app.services import events as events_service
from app.tasks import broker


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: starts/stops the taskiq broker for the API process.

    The worker process manages its own broker lifecycle through the taskiq CLI, so we guard on `is_worker_process` to avoid double-start when this module is imported by `taskiq worker`.
    """
    if not broker.is_worker_process:
        await broker.startup()
    try:
        yield
    finally:
        if not broker.is_worker_process:
            await broker.shutdown()
        await events_service.close()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, settings.app_env, settings.log_format)
    app = FastAPI(
        title="Synapse API",
        description="AI-powered research & synthesis platform.",
        version=__version__,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # RequestIDMiddleware is added last so it wraps everything
    # it must run before CORS and route handlers to ensure request_id is in context for all log lines emitted during a request
    app.add_middleware(RequestIDMiddleware)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
    app.include_router(auth_router, prefix="/api/auth")
    app.include_router(api_router, prefix="/api")
    # WebSocket routes live under /ws/* (no /api prefix).
    app.include_router(ws_router)
    # OpenAPI itself doesn't model WS, but we surface the message-payload schemas in components so frontend codegen produces typed WS messages.
    register_ws_schemas(app)

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    return app


app = create_app()
