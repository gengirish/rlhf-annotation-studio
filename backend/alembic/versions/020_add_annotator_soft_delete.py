"""add is_active and deactivated_at to annotators for soft delete

Revision ID: 020_add_annotator_soft_delete
Revises: 019_exam_review_rubric_scores
Create Date: 2026-04-14

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "020_add_annotator_soft_delete"
down_revision: str | None = "019_exam_review_rubric_scores"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "annotators",
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
    )
    op.add_column(
        "annotators",
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("annotators", "deactivated_at")
    op.drop_column("annotators", "is_active")
