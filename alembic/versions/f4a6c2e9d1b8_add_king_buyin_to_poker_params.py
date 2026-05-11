"""add king_buyin columns to poker_params

Revision ID: f4a6c2e9d1b8
Revises: e1b3a9d4c7f2
Create Date: 2026-05-11 23:45:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f4a6c2e9d1b8"
down_revision: Union[str, Sequence[str], None] = "e1b3a9d4c7f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  op.add_column("poker_params", sa.Column("king_buyin", sa.Integer(), nullable=True))
  op.add_column("poker_params", sa.Column("king_buyin_pic", sa.String(length=16), nullable=True))


def downgrade() -> None:
  op.drop_column("poker_params", "king_buyin_pic")
  op.drop_column("poker_params", "king_buyin")
