"""initial annotators and work_sessions

Revision ID: 001_initial
Revises:
Create Date: 2026-03-21

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "annotators",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_annotators_email"), "annotators", ["email"], unique=False)

    op.create_table(
        "work_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("annotator_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tasks_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "annotations_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "task_times_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("active_pack_file", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["annotator_id"], ["annotators.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_work_sessions_annotator_id"), "work_sessions", ["annotator_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_work_sessions_annotator_id"), table_name="work_sessions")
    op.drop_table("work_sessions")
    op.drop_index(op.f("ix_annotators_email"), table_name="annotators")
    op.drop_table("annotators")
