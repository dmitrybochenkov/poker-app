"""create buyin_data table

Revision ID: 2d91a6e4b1c3
Revises: 1c2b7d4e8aa1
Create Date: 2026-05-11 20:35:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2d91a6e4b1c3"
down_revision: Union[str, Sequence[str], None] = "1c2b7d4e8aa1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  op.create_table(
    "buyin_data",
    sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
    sa.Column("poker_date", sa.Date(), nullable=False),
    sa.Column("player_id", sa.BigInteger(), nullable=False),
    sa.Column("player_name", sa.String(length=255), nullable=False),
    sa.Column("buyins_count", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint("row_id"),
  )
  op.create_index(op.f("ix_buyin_data_poker_date"), "buyin_data", ["poker_date"], unique=False)
  op.create_index(op.f("ix_buyin_data_player_id"), "buyin_data", ["player_id"], unique=False)
  op.create_index(op.f("ix_buyin_data_created_at"), "buyin_data", ["created_at"], unique=False)


def downgrade() -> None:
  op.drop_index(op.f("ix_buyin_data_created_at"), table_name="buyin_data")
  op.drop_index(op.f("ix_buyin_data_player_id"), table_name="buyin_data")
  op.drop_index(op.f("ix_buyin_data_poker_date"), table_name="buyin_data")
  op.drop_table("buyin_data")
