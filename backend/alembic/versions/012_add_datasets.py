"""add datasets and dataset_versions tables

Revision ID: 012_add_datasets
Revises: 011_add_webhooks
Create Date: 2026-04-04

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "012_add_datasets"
down_revision: Union[str, None] = "011_add_webhooks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "datasets",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("task_type", sa.String(32), nullable=False),
        sa.Column("tags", JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["annotators.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "name", name="uq_datasets_org_id_name"),
    )
    op.create_index(op.f("ix_datasets_org_id"), "datasets", ["org_id"], unique=False)
    op.create_index(op.f("ix_datasets_created_by"), "datasets", ["created_by"], unique=False)

    op.create_table(
        "dataset_versions",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("source_pack_ids", JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("snapshot_json", JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("stats_json", JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("export_formats", JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["annotators.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dataset_versions_dataset_id"), "dataset_versions", ["dataset_id"], unique=False)
    op.create_index(op.f("ix_dataset_versions_created_by"), "dataset_versions", ["created_by"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_dataset_versions_created_by"), table_name="dataset_versions")
    op.drop_index(op.f("ix_dataset_versions_dataset_id"), table_name="dataset_versions")
    op.drop_table("dataset_versions")
    op.drop_index(op.f("ix_datasets_created_by"), table_name="datasets")
    op.drop_index(op.f("ix_datasets_org_id"), table_name="datasets")
    op.drop_table("datasets")
