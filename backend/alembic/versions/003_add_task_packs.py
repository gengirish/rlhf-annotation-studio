"""add task_packs table

Revision ID: 003_add_task_packs
Revises: 002_add_password_hash
Create Date: 2026-03-25

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "003_add_task_packs"
down_revision: Union[str, None] = "002_add_password_hash"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "task_packs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("language", sa.String(64), server_default="general", nullable=False),
        sa.Column("task_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("tasks_json", JSONB(), server_default="[]", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_task_packs_slug"), "task_packs", ["slug"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_task_packs_slug"), table_name="task_packs")
    op.drop_table("task_packs")
