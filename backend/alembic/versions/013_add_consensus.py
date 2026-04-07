"""add consensus_configs and consensus_tasks

Revision ID: 013_add_consensus
Revises: 012_add_datasets
Create Date: 2026-04-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "013_add_consensus"
down_revision: Union[str, None] = "012_add_datasets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "consensus_configs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_pack_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("annotators_per_task", sa.Integer(), nullable=False),
        sa.Column("agreement_threshold", sa.Float(), nullable=False),
        sa.Column("auto_resolve", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["task_pack_id"], ["task_packs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["annotators.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_pack_id", name="uq_consensus_config_task_pack"),
    )
    op.create_index(op.f("ix_consensus_configs_task_pack_id"), "consensus_configs", ["task_pack_id"], unique=False)

    op.create_table(
        "consensus_tasks",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("config_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_pack_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("assigned_annotators", JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("annotations_json", JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("resolved_annotation", JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("resolved_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("agreement_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["config_id"], ["consensus_configs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_pack_id"], ["task_packs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resolved_by"], ["annotators.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_consensus_tasks_config_id"), "consensus_tasks", ["config_id"], unique=False)
    op.create_index(op.f("ix_consensus_tasks_task_pack_id"), "consensus_tasks", ["task_pack_id"], unique=False)
    op.create_index(op.f("ix_consensus_tasks_status"), "consensus_tasks", ["status"], unique=False)
    op.create_index(
        "ix_consensus_tasks_pack_task",
        "consensus_tasks",
        ["task_pack_id", "task_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_consensus_tasks_pack_task", table_name="consensus_tasks")
    op.drop_index(op.f("ix_consensus_tasks_status"), table_name="consensus_tasks")
    op.drop_index(op.f("ix_consensus_tasks_task_pack_id"), table_name="consensus_tasks")
    op.drop_index(op.f("ix_consensus_tasks_config_id"), table_name="consensus_tasks")
    op.drop_table("consensus_tasks")
    op.drop_index(op.f("ix_consensus_configs_task_pack_id"), table_name="consensus_configs")
    op.drop_table("consensus_configs")
