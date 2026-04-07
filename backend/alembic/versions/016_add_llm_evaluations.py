"""add llm_evaluations table

Revision ID: 016_add_llm_evaluations
Revises: 015_add_quality_scores
Create Date: 2026-04-04

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "016_add_llm_evaluations"
down_revision: Union[str, None] = "015_add_quality_scores"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "llm_evaluations",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_pack_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", sa.String(255), nullable=False),
        sa.Column("judge_model", sa.String(255), nullable=False),
        sa.Column("judge_prompt_template", sa.Text(), nullable=False),
        sa.Column("evaluation_json", JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("human_override", JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("human_override_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["task_pack_id"], ["task_packs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["human_override_by"], ["annotators.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_llm_evaluations_task_pack_id"), "llm_evaluations", ["task_pack_id"], unique=False)
    op.create_index(
        "ix_llm_evaluations_task_pack_task_id",
        "llm_evaluations",
        ["task_pack_id", "task_id"],
        unique=False,
    )
    op.create_index(op.f("ix_llm_evaluations_status"), "llm_evaluations", ["status"], unique=False)
    op.create_index(op.f("ix_llm_evaluations_judge_model"), "llm_evaluations", ["judge_model"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_llm_evaluations_judge_model"), table_name="llm_evaluations")
    op.drop_index(op.f("ix_llm_evaluations_status"), table_name="llm_evaluations")
    op.drop_index("ix_llm_evaluations_task_pack_task_id", table_name="llm_evaluations")
    op.drop_index(op.f("ix_llm_evaluations_task_pack_id"), table_name="llm_evaluations")
    op.drop_table("llm_evaluations")
