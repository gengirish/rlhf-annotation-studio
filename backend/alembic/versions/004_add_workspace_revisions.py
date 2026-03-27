"""add workspace_revisions table

Revision ID: 004_add_workspace_revisions
Revises: 003_add_task_packs
Create Date: 2026-03-27

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "004_add_workspace_revisions"
down_revision: Union[str, None] = "003_add_task_packs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workspace_revisions",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("annotator_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column(
            "annotations_snapshot",
            JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "task_times_snapshot",
            JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["work_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["annotator_id"], ["annotators.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_workspace_revisions_session_id"), "workspace_revisions", ["session_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_workspace_revisions_session_id"), table_name="workspace_revisions")
    op.drop_table("workspace_revisions")
