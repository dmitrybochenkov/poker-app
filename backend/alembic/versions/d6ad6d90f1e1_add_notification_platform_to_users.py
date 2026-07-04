"""add notification_platform to users

Revision ID: d6ad6d90f1e1
Revises: b18da9959263
Create Date: 2026-05-03 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d6ad6d90f1e1"
down_revision: Union[str, Sequence[str], None] = "b18da9959263"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  op.add_column(
    "users",
    sa.Column("notification_platform", sa.String(length=2), nullable=True),
  )


def downgrade() -> None:
  op.drop_column("users", "notification_platform")
