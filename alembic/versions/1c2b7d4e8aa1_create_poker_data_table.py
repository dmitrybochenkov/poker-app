"""create poker_data table

Revision ID: 1c2b7d4e8aa1
Revises: 0f3d2a1c9b7e
Create Date: 2026-05-11 00:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "1c2b7d4e8aa1"
down_revision: Union[str, Sequence[str], None] = "0f3d2a1c9b7e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  op.create_table(
    "poker_data",
    sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
    sa.Column("date", sa.Date(), nullable=False),
    sa.Column("player_name", sa.String(length=255), nullable=False),
    sa.Column("player_id", sa.BigInteger(), nullable=False),
    sa.Column("is_prev_winner", sa.Boolean(), server_default=sa.text("0"), nullable=False),
    sa.Column("buyins", sa.Integer(), server_default=sa.text("0"), nullable=False),
    sa.Column("big_buyin_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
    sa.Column("super_buyin_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
    sa.Column("chips", sa.Integer(), server_default=sa.text("0"), nullable=False),
    sa.Column("money_rub", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
    sa.PrimaryKeyConstraint("row_id"),
    sa.UniqueConstraint("date", "player_id", name="uq_poker_data_date_player"),
  )
  op.create_index(op.f("ix_poker_data_date"), "poker_data", ["date"], unique=False)


def downgrade() -> None:
  op.drop_index(op.f("ix_poker_data_date"), table_name="poker_data")
  op.drop_table("poker_data")
