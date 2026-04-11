"""add exams, exam_attempts, exam_integrity_events

Revision ID: 017_add_exams
Revises: 016_add_llm_evaluations
Create Date: 2026-04-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "017_add_exams"
down_revision: Union[str, None] = "016_add_llm_evaluations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "exams",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("task_pack_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("pass_threshold", sa.Float(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("is_published", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["annotators.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_pack_id"], ["task_packs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_exams_task_pack_id"), "exams", ["task_pack_id"], unique=False)
    op.create_index(op.f("ix_exams_created_by"), "exams", ["created_by"], unique=False)
    op.create_index("ix_exams_is_published", "exams", ["is_published"], unique=False)

    op.create_table(
        "exam_attempts",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exam_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("annotator_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("answers_json", JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("task_times_json", JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("integrity_score", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["annotator_id"], ["annotators.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["exam_id"], ["exams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["released_by"], ["annotators.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_exam_attempts_exam_id"), "exam_attempts", ["exam_id"], unique=False)
    op.create_index(op.f("ix_exam_attempts_annotator_id"), "exam_attempts", ["annotator_id"], unique=False)
    op.create_index(
        "ix_exam_attempts_exam_annotator_status",
        "exam_attempts",
        ["exam_id", "annotator_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_exam_attempts_review_queue",
        "exam_attempts",
        ["status", "released_at"],
        unique=False,
    )

    op.create_table(
        "exam_integrity_events",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("payload_json", JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["attempt_id"], ["exam_attempts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_exam_integrity_events_attempt_id"), "exam_integrity_events", ["attempt_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_exam_integrity_events_attempt_id"), table_name="exam_integrity_events")
    op.drop_table("exam_integrity_events")
    op.drop_index("ix_exam_attempts_review_queue", table_name="exam_attempts")
    op.drop_index("ix_exam_attempts_exam_annotator_status", table_name="exam_attempts")
    op.drop_index(op.f("ix_exam_attempts_annotator_id"), table_name="exam_attempts")
    op.drop_index(op.f("ix_exam_attempts_exam_id"), table_name="exam_attempts")
    op.drop_table("exam_attempts")
    op.drop_index("ix_exams_is_published", table_name="exams")
    op.drop_index(op.f("ix_exams_created_by"), table_name="exams")
    op.drop_index(op.f("ix_exams_task_pack_id"), table_name="exams")
    op.drop_table("exams")
