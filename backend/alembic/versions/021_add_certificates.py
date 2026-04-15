"""placeholder for previously applied certificates migration

Revision ID: 021_add_certificates
Revises: 020_add_annotator_soft_delete
Create Date: 2026-04-15

"""

from collections.abc import Sequence

from alembic import op  # noqa: F401


revision: str = "021_add_certificates"
down_revision: str | None = "020_add_annotator_soft_delete"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
