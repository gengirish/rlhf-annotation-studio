"""add review_assignments table

Revision ID: 005_add_review_assignments
Revises: 004_add_workspace_revisions
Create Date: 2026-03-27

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "005_add_review_assignments"
down_revision: Union[str, None] = "004_add_workspace_revisions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "review_assignments",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_pack_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", sa.String(255), nullable=False),
        sa.Column("annotator_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(32), server_default="assigned", nullable=False),
        sa.Column("annotation_json", JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reviewer_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["task_pack_id"], ["task_packs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["annotator_id"], ["annotators.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["annotators.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_review_assignments_task_pack_id"), "review_assignments", ["task_pack_id"], unique=False)
    op.create_index(op.f("ix_review_assignments_annotator_id"), "review_assignments", ["annotator_id"], unique=False)
    op.create_index(op.f("ix_review_assignments_status"), "review_assignments", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_review_assignments_status"), table_name="review_assignments")
    op.drop_index(op.f("ix_review_assignments_annotator_id"), table_name="review_assignments")
    op.drop_index(op.f("ix_review_assignments_task_pack_id"), table_name="review_assignments")
    op.drop_table("review_assignments")
