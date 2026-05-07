"""User ORM model, managed by fastapi-users."""

from __future__ import annotations

from fastapi_users.db import SQLAlchemyBaseUserTableUUID

from app.db.base import Base


class User(SQLAlchemyBaseUserTableUUID, Base):
    """Extends the fastapi-users UUID user table with our declarative Base.

    All standard columns (id, email, hashed_password, is_active, is_superuser,
    is_verified, created_at) are inherited from SQLAlchemyBaseUserTableUUID.
    Add app-specific profile columns here when needed.
    """
