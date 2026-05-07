"""Auth backends, FastAPIUsers instance, and request-scoped user dependencies."""

from __future__ import annotations

import uuid

from fastapi_users import FastAPIUsers
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    CookieTransport,
    JWTStrategy,
)

from app.auth.manager import get_user_manager
from app.auth.models import User
from app.config import get_settings

_settings = get_settings()

# Cookie transport for browser clients; token stored in an httpOnly cookie so
# it is never accessible to JavaScript.
cookie_transport = CookieTransport(
    cookie_name="synapse_auth",
    cookie_max_age=86400,
    cookie_httponly=True,
    cookie_samesite="lax",
)

# Bearer transport for WebSocket connections and non-browser clients. The WS
# handler validates the token manually via the query string (httpOnly cookies
# are not reliably forwarded during the WS handshake in dev).
bearer_transport = BearerTransport(tokenUrl="/api/auth/jwt/login")


def _get_jwt_strategy() -> JWTStrategy[User, uuid.UUID]:
    return JWTStrategy(secret=_settings.jwt_secret, lifetime_seconds=86400)


cookie_backend = AuthenticationBackend(
    name="cookie",
    transport=cookie_transport,
    get_strategy=_get_jwt_strategy,
)

jwt_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=_get_jwt_strategy,
)

_auth_app: FastAPIUsers[User, uuid.UUID] = FastAPIUsers(
    get_user_manager,
    [cookie_backend, jwt_backend],
)

current_active_user = _auth_app.current_user(active=True)
current_superuser = _auth_app.current_user(active=True, superuser=True)
