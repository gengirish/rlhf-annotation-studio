"""add certificates table

Revision ID: 021_add_certificates
Revises: 020_add_annotator_soft_delete
Create Date: 2026-04-15

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "021_add_certificates"
down_revision: str | None = "020_add_annotator_soft_delete"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "certificates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "annotator_id",
            UUID(as_uuid=True),
            sa.ForeignKey("annotators.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("certificate_type", sa.String(64), nullable=False, server_default="course_completion"),
        sa.Column("source_id", sa.String(255), nullable=True),
        sa.Column("recipient_name", sa.String(512), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "issued_by",
            UUID(as_uuid=True),
            sa.ForeignKey("annotators.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("certificates")
