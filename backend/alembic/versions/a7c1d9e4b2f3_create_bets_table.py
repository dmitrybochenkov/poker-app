"""create bets table

Revision ID: a7c1d9e4b2f3
Revises: f4a6c2e9d1b8
Create Date: 2026-05-11 23:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a7c1d9e4b2f3"
down_revision: Union[str, Sequence[str], None] = "f4a6c2e9d1b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  op.create_table(
    "bets",
    sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
    sa.Column("poker_id", sa.Integer(), nullable=False),
    sa.Column("better_id", sa.Integer(), nullable=False),
    sa.Column("better_name", sa.String(length=255), nullable=False),
    sa.Column("tournament_type", sa.String(length=16), nullable=False),
    sa.Column("amount_kopecks", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(["poker_id"], ["pokers.row_id"], ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("row_id"),
    sa.UniqueConstraint("poker_id", "better_id", "tournament_type", name="uq_bets_poker_better_tournament"),
  )
  op.create_index(op.f("ix_bets_better_id"), "bets", ["better_id"], unique=False)
  op.create_index(op.f("ix_bets_poker_id"), "bets", ["poker_id"], unique=False)


def downgrade() -> None:
  op.drop_index(op.f("ix_bets_poker_id"), table_name="bets")
  op.drop_index(op.f("ix_bets_better_id"), table_name="bets")
  op.drop_table("bets")
