"""add job_events table for resumable streaming

Revision ID: 8c41a3b7e2d1
Revises: 0523aa9e53ea
Create Date: 2026-05-12 02:11:42.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8c41a3b7e2d1"
down_revision: str | Sequence[str] | None = "0523aa9e53ea"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "job_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("event", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["research_jobs.id"],
            name=op.f("fk_job_events_job_id_research_jobs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_events")),
    )
    # Compound index supports the hot-path replay query
    # `WHERE job_id = $1 ORDER BY id ASC` in a single index scan.
    op.create_index(op.f("ix_job_events_job_id_id"), "job_events", ["job_id", "id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_job_events_job_id_id"), table_name="job_events")
    op.drop_table("job_events")
