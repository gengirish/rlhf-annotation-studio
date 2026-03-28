"""Add role column to annotators table.

Revision ID: 007
Revises: 006
Create Date: 2026-03-28
"""

from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "annotators",
        sa.Column("role", sa.String(32), server_default="annotator", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("annotators", "role")
