"""add unique constraint on review_assignments (task_pack_id, task_id, annotator_id)

Revision ID: 008_unique_review_assignment
Revises: 007
Create Date: 2026-03-31

"""

from typing import Sequence, Union

from alembic import op

revision: str = "008_unique_review_assignment"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_review_assignment_task_annotator",
        "review_assignments",
        ["task_pack_id", "task_id", "annotator_id"],
    )
    op.create_index(
        "ix_review_assignments_updated_at",
        "review_assignments",
        ["updated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_review_assignments_updated_at", table_name="review_assignments")
    op.drop_constraint("uq_review_assignment_task_annotator", "review_assignments", type_="unique")
