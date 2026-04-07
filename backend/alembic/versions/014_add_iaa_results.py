"""add iaa_results table for cached inter-annotator agreement

Revision ID: 014_add_iaa_results
Revises: 013_add_consensus
Create Date: 2026-04-04

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "014_add_iaa_results"
down_revision: Union[str, None] = "013_add_consensus"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "iaa_results",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_pack_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("result_json", JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("n_annotators", sa.Integer(), nullable=False),
        sa.Column("overall_kappa", sa.Float(), nullable=True),
        sa.Column("overall_alpha", sa.Float(), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["task_pack_id"], ["task_packs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_iaa_results_task_pack_id"), "iaa_results", ["task_pack_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_iaa_results_task_pack_id"), table_name="iaa_results")
    op.drop_table("iaa_results")
