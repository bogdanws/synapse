"""slowapi Limiter and per-user rate-limit key function."""

from __future__ import annotations

import jwt
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.config import get_settings

# Captured once at import time; get_settings() is lru_cache'd so this is a single dict lookup on every subsequent call.
_jwt_secret = get_settings().jwt_secret

# fastapi-users sets aud=["fastapi-users:auth"] on every token it issues.
# Passing the same audience here lets PyJWT verify it rather than skip the check, so a token minted for a different purpose won't satisfy rate-limit key extraction
_JWT_AUDIENCE = ["fastapi-users:auth"]


def _user_id_from_request(request: Request) -> str:
    """Return the authenticated user's UUID as the rate-limit key.

    Falls back to the client IP for requests that carry no valid auth cookie (e.g. /api/auth/register, /api/auth/login), so those endpoints are still covered by IP-based limiting
    """
    token = request.cookies.get("synapse_auth")
    if token:
        try:
            payload = jwt.decode(
                token,
                _jwt_secret,
                algorithms=["HS256"],
                audience=_JWT_AUDIENCE,
            )
            raw_sub = payload.get("sub")
            if isinstance(raw_sub, str) and raw_sub:
                return raw_sub
        except jwt.PyJWTError:
            pass
    return get_remote_address(request)


limiter = Limiter(key_func=_user_id_from_request)
