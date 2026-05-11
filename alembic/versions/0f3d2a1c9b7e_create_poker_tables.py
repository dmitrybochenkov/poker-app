"""create poker tables

Revision ID: 0f3d2a1c9b7e
Revises: d6ad6d90f1e1
Create Date: 2026-05-11 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0f3d2a1c9b7e"
down_revision: Union[str, Sequence[str], None] = "d6ad6d90f1e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  op.create_table(
    "poker_params",
    sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
    sa.Column("buyin_size_chips", sa.Integer(), nullable=False),
    sa.Column("buyin_size_rub", sa.BigInteger(), nullable=False),
    sa.Column("bb_size_chips", sa.Integer(), nullable=False),
    sa.Column("max_buyins", sa.Integer(), nullable=False),
    sa.Column("big_buyin", sa.Integer(), nullable=True),
    sa.Column("big_buyin_pic", sa.String(length=16), nullable=True),
    sa.Column("super_buyin", sa.Integer(), nullable=True),
    sa.Column("super_buyin_pic", sa.String(length=16), nullable=True),
    sa.PrimaryKeyConstraint("row_id"),
  )

  op.create_table(
    "pokers",
    sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
    sa.Column("params_id", sa.Integer(), nullable=False),
    sa.Column("date", sa.Date(), server_default=sa.text("CURRENT_DATE"), nullable=False),
    sa.Column("cashier_id", sa.Integer(), nullable=True),
    sa.Column("is_going", sa.Boolean(), server_default=sa.text("1"), nullable=False),
    sa.Column("is_bettable", sa.Boolean(), server_default=sa.text("0"), nullable=False),
    sa.Column("is_ready_for_chips_entering", sa.Boolean(), server_default=sa.text("0"), nullable=False),
    sa.ForeignKeyConstraint(["params_id"], ["poker_params.row_id"], ondelete="RESTRICT"),
    sa.PrimaryKeyConstraint("row_id"),
  )


def downgrade() -> None:
  op.drop_table("pokers")
  op.drop_table("poker_params")
