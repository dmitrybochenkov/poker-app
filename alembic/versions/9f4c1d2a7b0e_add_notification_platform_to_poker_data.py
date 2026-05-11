"""add notification_platform to poker_data

Revision ID: 9f4c1d2a7b0e
Revises: 2d91a6e4b1c3
Create Date: 2026-05-11 21:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9f4c1d2a7b0e"
down_revision: Union[str, Sequence[str], None] = "2d91a6e4b1c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  op.add_column("poker_data", sa.Column("notification_platform", sa.String(length=2), nullable=True))


def downgrade() -> None:
  op.drop_column("poker_data", "notification_platform")
