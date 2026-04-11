"""add course_modules and course_sessions tables, link task_packs

Revision ID: 018_add_course_content
Revises: 017_add_exams
Create Date: 2026-04-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "018_add_course_content"
down_revision: str | None = "017_add_exams"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "course_modules",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("overview_md", sa.Text(), server_default="", nullable=False),
        sa.Column("prerequisites", sa.Text(), nullable=True),
        sa.Column("estimated_time", sa.String(64), server_default="", nullable=False),
        sa.Column("skills_json", JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("bridge_text", sa.Text(), nullable=True),
        sa.Column("session_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("number"),
    )
    op.create_index(op.f("ix_course_modules_number"), "course_modules", ["number"], unique=True)

    op.create_table(
        "course_sessions",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("module_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("overview_md", sa.Text(), server_default="", nullable=False),
        sa.Column("rubric_md", sa.Text(), nullable=True),
        sa.Column("questions_md", sa.Text(), nullable=True),
        sa.Column("exercises_md", sa.Text(), nullable=True),
        sa.Column("ai_tasks_md", sa.Text(), nullable=True),
        sa.Column("resources_md", sa.Text(), nullable=True),
        sa.Column("duration", sa.String(64), server_default="90-120 minutes", nullable=False),
        sa.Column(
            "objectives_json", JSONB(astext_type=sa.Text()), server_default="[]", nullable=False
        ),
        sa.Column(
            "outline_json", JSONB(astext_type=sa.Text()), server_default="[]", nullable=False
        ),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["module_id"], ["course_modules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("number"),
    )
    op.create_index(op.f("ix_course_sessions_number"), "course_sessions", ["number"], unique=True)
    op.create_index(op.f("ix_course_sessions_module_id"), "course_sessions", ["module_id"])

    # Add session_id FK to task_packs
    op.add_column(
        "task_packs",
        sa.Column("session_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_task_packs_session_id",
        "task_packs",
        "course_sessions",
        ["session_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_task_packs_session_id"), "task_packs", ["session_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_task_packs_session_id"), table_name="task_packs")
    op.drop_constraint("fk_task_packs_session_id", "task_packs", type_="foreignkey")
    op.drop_column("task_packs", "session_id")
    op.drop_index(op.f("ix_course_sessions_module_id"), table_name="course_sessions")
    op.drop_index(op.f("ix_course_sessions_number"), table_name="course_sessions")
    op.drop_table("course_sessions")
    op.drop_index(op.f("ix_course_modules_number"), table_name="course_modules")
    op.drop_table("course_modules")
