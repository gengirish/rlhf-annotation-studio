"""add clerk_user_id to annotators for the Clerk auth migration

Nullable on purpose: during the dual-auth window, accounts that have not yet
been imported into Clerk still authenticate with legacy HS256 tokens.

Revision ID: 022_add_annotator_clerk_user_id
Revises: 021_add_certificates
Create Date: 2026-07-30

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "022_add_annotator_clerk_user_id"
down_revision: str | None = "021_add_certificates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "annotators",
        sa.Column("clerk_user_id", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_annotators_clerk_user_id",
        "annotators",
        ["clerk_user_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_annotators_clerk_user_id", table_name="annotators")
    op.drop_column("annotators", "clerk_user_id")
