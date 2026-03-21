"""add password_hash and unique annotators.email

Revision ID: 002_add_password_hash
Revises: 001_initial
Create Date: 2026-03-21

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_add_password_hash"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(op.f("ix_annotators_email"), table_name="annotators")
    op.add_column("annotators", sa.Column("password_hash", sa.String(length=255), nullable=True))
    op.create_index(op.f("ix_annotators_email"), "annotators", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_annotators_email"), table_name="annotators")
    op.drop_column("annotators", "password_hash")
    op.create_index(op.f("ix_annotators_email"), "annotators", ["email"], unique=False)
