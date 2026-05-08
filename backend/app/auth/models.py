"""User ORM model, managed by fastapi-users."""

from __future__ import annotations

from datetime import datetime

# Direct import: the `fastapi_users.db` re-export shim swallows ImportErrors and breaks under alembic's import order
from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID
from sqlalchemy import TIMESTAMP, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(SQLAlchemyBaseUserTableUUID, Base):
    """Extends the fastapi-users UUID user table with our declarative Base.

    Inherited columns: id, email, hashed_password, is_active, is_superuser,
    is_verified. We add created_at because SQLAlchemyBaseUserTableUUID does
    not supply it.
    """

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
