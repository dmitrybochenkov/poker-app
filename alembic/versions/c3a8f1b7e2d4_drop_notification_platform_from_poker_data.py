"""drop notification_platform from poker_data

Revision ID: c3a8f1b7e2d4
Revises: 9f4c1d2a7b0e
Create Date: 2026-05-11 21:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3a8f1b7e2d4"
down_revision: Union[str, Sequence[str], None] = "9f4c1d2a7b0e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  op.drop_column("poker_data", "notification_platform")


def downgrade() -> None:
  op.add_column("poker_data", sa.Column("notification_platform", sa.String(length=2), nullable=True))
