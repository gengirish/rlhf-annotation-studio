"""add annotator quality scores and calibration tables

Revision ID: 015_add_quality_scores
Revises: 014_add_iaa_results
Create Date: 2026-04-04

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "015_add_quality_scores"
down_revision: str | None = "014_add_iaa_results"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "annotator_quality_scores",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("annotator_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_pack_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("gold_accuracy", sa.Float(), nullable=True),
        sa.Column("agreement_with_experts", sa.Float(), nullable=True),
        sa.Column("agreement_with_peers", sa.Float(), nullable=True),
        sa.Column("consistency_score", sa.Float(), nullable=True),
        sa.Column("speed_percentile", sa.Float(), nullable=True),
        sa.Column("overall_trust_score", sa.Float(), nullable=True),
        sa.Column("tasks_completed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("calibration_passed", sa.Boolean(), nullable=True),
        sa.Column("details_json", JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["annotator_id"], ["annotators.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_pack_id"], ["task_packs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_annotator_quality_scores_annotator_id"),
        "annotator_quality_scores",
        ["annotator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_annotator_quality_scores_task_pack_id"),
        "annotator_quality_scores",
        ["task_pack_id"],
        unique=False,
    )

    op.create_table(
        "calibration_tests",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("task_pack_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("passing_threshold", sa.Float(), server_default="0.7", nullable=False),
        sa.Column("is_required", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_pack_id"], ["task_packs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["annotators.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_calibration_tests_org_id"),
        "calibration_tests",
        ["org_id"],
        unique=False,
    )

    op.create_table(
        "calibration_attempts",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("test_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("annotator_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("details_json", JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("attempted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["annotator_id"], ["annotators.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["test_id"], ["calibration_tests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_calibration_attempts_test_id"),
        "calibration_attempts",
        ["test_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_calibration_attempts_annotator_id"),
        "calibration_attempts",
        ["annotator_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_calibration_attempts_annotator_id"), table_name="calibration_attempts")
    op.drop_index(op.f("ix_calibration_attempts_test_id"), table_name="calibration_attempts")
    op.drop_table("calibration_attempts")
    op.drop_index(op.f("ix_calibration_tests_org_id"), table_name="calibration_tests")
    op.drop_table("calibration_tests")
    op.drop_index(op.f("ix_annotator_quality_scores_task_pack_id"), table_name="annotator_quality_scores")
    op.drop_index(op.f("ix_annotator_quality_scores_annotator_id"), table_name="annotator_quality_scores")
    op.drop_table("annotator_quality_scores")
