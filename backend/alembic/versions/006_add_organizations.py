"""add organizations table and annotators.org_id

Revision ID: 006_add_organizations
Revises: 005_add_review_assignments
Create Date: 2026-03-27

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006_add_organizations"
down_revision: Union[str, None] = "005_add_review_assignments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("plan_tier", sa.String(32), server_default="free", nullable=False),
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
        sa.Column("max_seats", sa.Integer(), server_default="5", nullable=False),
        sa.Column("max_packs", sa.Integer(), server_default="3", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_organizations_slug"), "organizations", ["slug"], unique=True)
    op.add_column(
        "annotators",
        sa.Column("org_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(op.f("ix_annotators_org_id"), "annotators", ["org_id"], unique=False)
    op.create_foreign_key(
        "annotators_org_id_fkey",
        "annotators",
        "organizations",
        ["org_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("annotators_org_id_fkey", "annotators", type_="foreignkey")
    op.drop_index(op.f("ix_annotators_org_id"), table_name="annotators")
    op.drop_column("annotators", "org_id")
    op.drop_index(op.f("ix_organizations_slug"), table_name="organizations")
    op.drop_table("organizations")
