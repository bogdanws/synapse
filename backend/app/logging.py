"""Structlog configuration and request-ID middleware."""

from __future__ import annotations

import logging
import sys
import uuid
from typing import Any

import structlog
import structlog.contextvars
import structlog.dev
import structlog.processors
import structlog.stdlib
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


def configure_logging(log_level: str, app_env: str, log_format: str) -> None:
    """Configure structlog and the stdlib logging bridge.

    LOG_LEVEL controls verbosity; LOG_FORMAT controls renderer;
    LOG_FORMAT=json forces JSON everywhere; LOG_FORMAT=console forces console output everywhere;
    LOG_FORMAT=auto chooses console for development/test and JSON for production.
    All stdlib loggers (uvicorn, SQLAlchemy, fastapi-users) are routed through the same processor chain so format and context propagation are consistent across all log sources
    """
    level: int = logging.getLevelNamesMapping().get(log_level.upper(), logging.INFO)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if log_format == "json":
        renderer: Any = structlog.processors.JSONRenderer()
    elif log_format == "console":
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = (
            structlog.dev.ConsoleRenderer()
            if app_env in {"development", "test"}
            else structlog.processors.JSONRenderer()
        )

    structlog.configure(
        processors=shared_processors + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Binds a request ID to the structlog context for every request.

    Reads X-Request-ID from incoming headers when present (useful when a reverse proxy sets it for distributed tracing), otherwise generates a fresh UUID
    The ID is echoed back in the response headers
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
