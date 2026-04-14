"""add review_rubric_scores_json to exam_attempts

Revision ID: 019_exam_review_rubric_scores
Revises: 018_add_course_content
Create Date: 2026-04-14

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "019_exam_review_rubric_scores"
down_revision: str | None = "018_add_course_content"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "exam_attempts",
        sa.Column(
            "review_rubric_scores_json",
            JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("exam_attempts", "review_rubric_scores_json")
