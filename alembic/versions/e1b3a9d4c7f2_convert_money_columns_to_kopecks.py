"""convert money columns to kopecks

Revision ID: e1b3a9d4c7f2
Revises: c3a8f1b7e2d4
Create Date: 2026-05-11 23:20:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "e1b3a9d4c7f2"
down_revision: Union[str, Sequence[str], None] = "c3a8f1b7e2d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  op.execute("ALTER TABLE poker_params RENAME COLUMN buyin_size_rub TO buyin_size_kopecks")
  op.execute("ALTER TABLE poker_data RENAME COLUMN money_rub TO money_kopecks")

  op.execute("UPDATE poker_params SET buyin_size_kopecks = buyin_size_kopecks * 100")
  op.execute("UPDATE poker_data SET money_kopecks = money_kopecks * 100")


def downgrade() -> None:
  op.execute("UPDATE poker_params SET buyin_size_kopecks = buyin_size_kopecks / 100")
  op.execute("UPDATE poker_data SET money_kopecks = money_kopecks / 100")

  op.execute("ALTER TABLE poker_params RENAME COLUMN buyin_size_kopecks TO buyin_size_rub")
  op.execute("ALTER TABLE poker_data RENAME COLUMN money_kopecks TO money_rub")
